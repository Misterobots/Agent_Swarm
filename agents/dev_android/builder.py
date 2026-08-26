"""Run bounded Android builds in a disposable, dedicated builder container.

The normal dev sandbox intentionally remains toolchain-free.  This module
copies one owner-scoped project into an isolated Android builder, runs Gradle
with a hard wall-clock limit, and copies only the resulting APK back into the
runtime's signed artifact directory.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
import re
import tarfile
import tempfile
import time
import uuid

BUILDER_IMAGE = os.getenv("ANDROID_BUILDER_IMAGE", "home-ai-lab/android-builder:latest")
BUILD_TIMEOUT_SECONDS = int(os.getenv("ANDROID_BUILD_TIMEOUT_SECONDS", "900"))
MAX_APK_BYTES = int(os.getenv("ANDROID_BUILD_MAX_APK_BYTES", str(100 * 1024 * 1024)))
MAX_SOURCE_BYTES = int(os.getenv("ANDROID_BUILD_MAX_SOURCE_BYTES", str(500 * 1024 * 1024)))
ARTIFACT_SIGNING_SECRET = os.getenv(
    "ARTIFACT_SIGNING_SECRET", os.getenv("FRIDAY_IMAGE_SIGNING_SECRET", "")
)


class AndroidBuildError(RuntimeError):
    """A user-actionable Android build failure."""


def _safe_component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", value or "") or value in {".", ".."}:
        raise AndroidBuildError("Invalid project identifier")
    return value


def _container_client():
    try:
        import docker
    except ImportError as exc:
        raise AndroidBuildError("Docker SDK is unavailable in agent_runtime") from exc
    try:
        return docker, docker.from_env()
    except Exception as exc:
        raise AndroidBuildError(f"Cannot connect to Docker for Android build: {exc}") from exc


def _archive_bytes(source_container, source_path: str) -> bytes:
    try:
        code, output = source_container.exec_run(
            ["bash", "-lc", f"test -d {__import__('shlex').quote(source_path)} && tar -C {__import__('shlex').quote(source_path)} -cf - ."],
            demux=False,
        )
        if code != 0:
            raise AndroidBuildError("Android project directory was not found in the sandbox")
        data = bytes(output or b"")
        if len(data) > MAX_SOURCE_BYTES:
            raise AndroidBuildError("Android project exceeds the source-size limit")
        return data
    except AndroidBuildError:
        raise
    except Exception as exc:
        raise AndroidBuildError(f"Could not snapshot Android project: {exc}") from exc


def _copy_apk_from_builder(builder, apk_path: str, destination: str) -> int:
    stream, _stat = builder.get_archive(apk_path)
    data = bytearray()
    for chunk in stream:
        data.extend(chunk)
        if len(data) > MAX_APK_BYTES * 2:
            raise AndroidBuildError("APK archive exceeds the transfer limit")

    with tarfile.open(fileobj=io.BytesIO(bytes(data)), mode="r:*") as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        if len(members) != 1:
            raise AndroidBuildError("Builder returned an invalid APK archive")
        member = members[0]
        if member.size <= 0 or member.size > MAX_APK_BYTES:
            raise AndroidBuildError("APK exceeds the artifact-size limit")
        source = archive.extractfile(member)
        if source is None:
            raise AndroidBuildError("Builder returned an unreadable APK")
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="android-", suffix=".apk", dir=os.path.dirname(destination))
        try:
            with os.fdopen(fd, "wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            os.replace(temp_path, destination)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        return member.size


def _signed_artifact_url(filename: str, base_path: str = "/v1/public-artifacts") -> str | None:
    if not ARTIFACT_SIGNING_SECRET:
        return None
    expiry = int(time.time()) + 24 * 60 * 60
    payload = f"{filename}:{expiry}".encode("utf-8")
    signature = hmac.new(ARTIFACT_SIGNING_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{base_path}/{filename}?exp={expiry}&sig={signature}"


def build_android_project(uid: str, project_id: str, source_container_name: str = "dev_sandbox") -> dict:
    """Build one project and return metadata for its signed APK artifact."""
    if not ARTIFACT_SIGNING_SECRET:
        raise AndroidBuildError(
            "Android artifact delivery is not configured; set ARTIFACT_SIGNING_SECRET"
        )
    uid = _safe_component(uid)
    project_id = _safe_component(project_id)
    docker, client = _container_client()
    source = None
    builder = None
    job_id = uuid.uuid4().hex[:16]
    artifact_name = f"android-{job_id}.apk"
    artifact_path = f"/workspace/delivered_artifacts/{artifact_name}"
    started = time.monotonic()
    try:
        source = client.containers.get(source_container_name)
        if source.status != "running":
            raise AndroidBuildError(f"Source sandbox is not running: {source_container_name}")
        project_path = f"/workspace/{uid}/{project_id}"
        archive = _archive_bytes(source, project_path)

        networks = list(source.attrs.get("NetworkSettings", {}).get("Networks", {}))
        builder = client.containers.run(
            BUILDER_IMAGE,
            command=["sleep", "infinity"],
            detach=True,
            remove=False,
            user="root",
            network=networks[0] if networks else None,
            mem_limit=os.getenv("ANDROID_BUILD_MEMORY_LIMIT", "8g"),
            nano_cpus=int(float(os.getenv("ANDROID_BUILD_CPUS", "4")) * 1_000_000_000),
            pids_limit=int(os.getenv("ANDROID_BUILD_PIDS_LIMIT", "512")),
            tmpfs={"/tmp": "rw,noexec,nosuid,size=1g"},
            labels={"agent_swarm.android_builder": "true", "agent_swarm.build_id": job_id},
        )
        builder.exec_run(["mkdir", "-p", f"/workspace/{uid}/{project_id}"])
        builder.put_archive(f"/workspace/{uid}/{project_id}", archive)
        # put_archive writes as root even though the image's normal user is
        # `android`; Gradle must be able to create its cache and build output.
        code, _output = builder.exec_run(
            ["chown", "-R", "android:android", f"/workspace/{uid}/{project_id}"],
            demux=True,
        )
        if code != 0:
            raise AndroidBuildError("Could not set Android project ownership")
        build_path = f"/workspace/{uid}/{project_id}"
        command = (
            f"cd {__import__('shlex').quote(build_path)} && "
            "if test -f ./gradlew; then "
            "chmod +x ./gradlew && ./gradlew --no-daemon --stacktrace assembleRelease; "
            "else echo 'gradle wrapper ./gradlew not found' >&2; exit 2; fi"
        )
        result = {}
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(
            builder.exec_run, ["bash", "-lc", command], user="android", demux=True
        )
        try:
            code, output = future.result(timeout=BUILD_TIMEOUT_SECONDS)
            stdout, stderr = output if output else (b"", b"")
            result = {
                "code": code,
                "output": ((stdout or b"") + (stderr or b"")).decode("utf-8", errors="replace")[-12000:],
            }
        except FutureTimeout as exc:
            try:
                builder.kill()
            except Exception:
                pass
            pool.shutdown(wait=False, cancel_futures=True)
            raise AndroidBuildError(
                f"Android build exceeded the {BUILD_TIMEOUT_SECONDS}-second timeout"
            ) from exc
        else:
            pool.shutdown(wait=True)
        if result.get("code") != 0:
            raise AndroidBuildError(f"Android build failed:\n{result.get('output', '')}")

        code, stdout, stderr = builder.exec_run(
            ["bash", "-lc", f"find {__import__('shlex').quote(build_path)} -type f -name '*.apk' -print"],
            user="android",
            demux=True,
        )
        if code != 0:
            raise AndroidBuildError("Could not inspect Android build outputs")
        candidates = [line.strip() for line in (stdout or b"").decode().splitlines() if line.strip()]
        if len(candidates) != 1:
            raise AndroidBuildError(f"Expected exactly one APK, found {len(candidates)}")
        size = _copy_apk_from_builder(builder, candidates[0], artifact_path)
        return {
            "job_id": job_id,
            "filename": artifact_name,
            "size": size,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "download_url": _signed_artifact_url(artifact_name),
            "signed": bool(ARTIFACT_SIGNING_SECRET),
        }
    finally:
        if builder is not None:
            try:
                builder.remove(force=True)
            except Exception:
                pass
        try:
            client.close()
        except Exception:
            pass
