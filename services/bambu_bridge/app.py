"""Windows-local, approval-gated bridge for Friday's Bambu P1S workflow."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

APP = FastAPI(title="Friday Bambu Bridge", version="0.1.0")
TOKEN = os.environ.get("BAMBU_BRIDGE_TOKEN", "")
JOB_ROOT = Path(os.environ.get("BAMBU_JOB_ROOT", r"C:\Users\panca\Documents\Github\Friday_Body\cad\print_jobs")).resolve()
MANIFEST_PATH = Path(os.environ.get("BAMBU_JOB_MANIFEST", str(JOB_ROOT / "jobs.json"))).resolve()
STUDIO_EXE = Path(os.environ.get("BAMBU_STUDIO_EXE", r"C:\Program Files\Bambu Studio\bambu-studio.exe"))
CONNECTOR_URL = os.environ.get("BAMBU_CONNECTOR_URL", "").rstrip("/")
CONNECTOR_TOKEN = os.environ.get("BAMBU_CONNECTOR_TOKEN", "")
_approvals: dict[str, dict[str, Any]] = {}


class JobRequest(BaseModel):
    job_id: str


class StartRequest(JobRequest):
    approval_token: str
    confirmed: bool = False


class CancelRequest(BaseModel):
    approval_token: str
    confirmed: bool = False


def _auth(authorization: str | None) -> None:
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Bridge authentication failed")


def _manifest() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return {str(job["id"]): job for job in raw.get("jobs", [])}
    except FileNotFoundError:
        return {}
    except (ValueError, KeyError) as exc:
        raise HTTPException(500, f"Invalid Bambu job manifest: {exc}") from exc


def _job(job_id: str) -> tuple[dict[str, Any], Path]:
    job = _manifest().get(job_id)
    if not job:
        raise HTTPException(404, "Unknown or unapproved print job")
    path = (JOB_ROOT / str(job["file"])).resolve()
    if JOB_ROOT not in path.parents or path.suffix.lower() not in {".3mf", ".gcode", ".gcode.3mf"}:
        raise HTTPException(400, "Job file is outside the approved root or has an invalid format")
    return job, path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preflight(job_id: str) -> dict[str, Any]:
    job, path = _job(job_id)
    if not path.is_file():
        return {"ok": False, "job_id": job_id, "error": "Approved job file is missing"}
    actual = _sha256(path)
    expected = str(job.get("sha256", "")).lower()
    if not expected or actual.lower() != expected:
        return {"ok": False, "job_id": job_id, "error": "Job SHA-256 does not match its approved manifest"}
    return {"ok": True, "job_id": job_id, "file": path.name, "bytes": path.stat().st_size,
            "sha256": actual, "profile": job.get("profile"), "filament": job.get("filament"),
            "estimated_minutes": job.get("estimated_minutes"), "requires_human_confirmation": True}


def _consume_approval(job_id: str, token: str) -> None:
    record = _approvals.pop(token, None)
    if not record or record["job_id"] != job_id or record["expires_at"] < time.time():
        raise HTTPException(403, "Missing, expired, or invalid approval token")


@APP.get("/status")
def status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    return {"ok": True, "bridge": "Friday Bambu Bridge", "job_root": str(JOB_ROOT),
            "bambu_studio_found": STUDIO_EXE.is_file(), "connector_configured": bool(CONNECTOR_URL),
            "start_mode": "connector" if CONNECTOR_URL else "manual_bambu_studio_handoff"}


@APP.get("/list_jobs")
def list_jobs(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    return {"ok": True, "jobs": [{k: v for k, v in job.items() if k != "sha256"} for job in _manifest().values()]}


@APP.post("/preflight")
def preflight(request: JobRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    return _preflight(request.job_id)


@APP.post("/request_approval")
def request_approval(request: JobRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    check = _preflight(request.job_id)
    if not check["ok"]:
        return check
    token = secrets.token_urlsafe(24)
    expires_at = time.time() + 600
    _approvals[token] = {"job_id": request.job_id, "expires_at": expires_at}
    return {**check, "approval_token": token, "expires_in_seconds": 600,
            "next_step": "Call start with this token and confirmed=true after the user explicitly approves."}


@APP.post("/start")
def start(request: StartRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    if not request.confirmed:
        raise HTTPException(409, "Explicit confirmed=true is required to start a physical print")
    check = _preflight(request.job_id)
    if not check["ok"]:
        return check
    _consume_approval(request.job_id, request.approval_token)
    _, path = _job(request.job_id)
    if CONNECTOR_URL:
        # Connector implementation is a separately-paired local service.
        # Its only accepted payload is this already-validated, allow-listed file.
        import urllib.request
        body = json.dumps({"job_id": request.job_id, "file": str(path)}).encode()
        try:
            req = urllib.request.Request(f"{CONNECTOR_URL}/start", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {CONNECTOR_TOKEN}"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            return {"ok": False, "error": f"Paired P1S connector failed: {exc}"}
    if not STUDIO_EXE.is_file():
        return {"ok": False, "error": "Bambu Studio executable is not configured"}
    subprocess.Popen([str(STUDIO_EXE), str(path)], close_fds=True)
    return {"ok": True, "mode": "manual_handoff_required", "job_id": request.job_id,
            "message": "Approved file opened in Bambu Studio. Review plate and click Print Plate there."}


@APP.post("/cancel")
def cancel(request: CancelRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    if not request.confirmed:
        raise HTTPException(409, "Explicit confirmed=true is required to cancel a physical print")
    if not CONNECTOR_URL or not CONNECTOR_TOKEN:
        return {"ok": False, "error": "No paired P1S connector; cancel from Bambu Studio or printer panel."}
    import urllib.request
    try:
        req = urllib.request.Request(f"{CONNECTOR_URL}/cancel", data=b"{}",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {CONNECTOR_TOKEN}"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())
    except Exception as exc:
        return {"ok": False, "error": f"Paired P1S connector cancellation failed: {exc}"}
