"""
dev_files/docker_exec.py — Filesystem operations inside the dev_sandbox container.

All file operations are namespaced under:
    /workspace/<uid>/<project_id>/

`exec_in_sandbox` and `exec_in_project` are the low-level helpers.
`list_tree`, `read_file`, `write_file`, `provision_project_dir` are the
public API consumed by routes.py.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import shlex
from pathlib import PurePosixPath
from typing import Optional

logger = logging.getLogger("dev_files.docker_exec")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SANDBOX_CONTAINER = os.getenv("DEV_SANDBOX_CONTAINER", "dev_sandbox")
WORKSPACE_ROOT = "/workspace"
MAX_FILE_BYTES = int(os.getenv("DEV_FILES_MAX_BYTES", str(4 * 1024 * 1024)))  # 4 MB default


# ---------------------------------------------------------------------------
# Container access
# ---------------------------------------------------------------------------

def _get_container(container_name: Optional[str] = None):
    """Return the target sandbox Docker container, or raise RuntimeError.

    With container_name unset, resolves the per-thread session container set
    via sandbox_identity (agents/coordination/sandbox_identity.py), falling
    back to the shared SANDBOX_CONTAINER env constant for any caller that
    hasn't set one. Passing container_name explicitly bypasses that
    resolution entirely — for the rare caller that needs a SPECIFIC container
    regardless of whatever the current thread-local target is (e.g.
    workspace_ops.checkout_local_project(), which must read the shared
    dev_sandbox even while a per-session container is already "current").
    """
    from coordination.sandbox_identity import get_current_container
    name = container_name or get_current_container(SANDBOX_CONTAINER)
    try:
        import docker
        client = docker.from_env()
        container = client.containers.get(name)
        if container.status != "running":
            raise RuntimeError(
                f"sandbox container '{name}' is not running "
                f"(status={container.status!r}). "
                "Start it with: docker compose -f execution_plane/docker-compose.yml up dev-sandbox"
            )
        return container
    except ImportError:
        raise RuntimeError(
            "docker Python package not installed; add 'docker' to agent_runtime requirements."
        )
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("Failed to get container '%s': %s", name, exc, exc_info=True)
        raise RuntimeError(f"Cannot connect to sandbox '{name}': {exc}") from exc


# ---------------------------------------------------------------------------
# Low-level exec helpers
# ---------------------------------------------------------------------------

def exec_in_sandbox(
    *cmd: str,
    input_bytes: Optional[bytes] = None,
    timeout: int = 30,
    user: str = "root",
    container_name: Optional[str] = None,
) -> tuple[int, str, str]:
    """
    Execute *cmd inside the dev-sandbox container.
    Returns (returncode, stdout, stderr).

    If input_bytes is provided the command is run via a bash here-doc so that
    the bytes are fed to stdin.  (docker-py exec_run doesn't support stdin
    directly, so we base64-encode and pipe.)

    container_name overrides the normal thread-local session-container
    resolution — see _get_container()'s docstring.
    """
    container = _get_container(container_name)

    if input_bytes is not None:
        # Encode payload as base64 and pipe into the target command through bash.
        # This avoids shell injection from the file contents.
        encoded = base64.b64encode(input_bytes).decode("ascii")
        # cmd is expected to be something like ("sh", "-c", "cat > '/path/file.tmp'")
        inner = " ".join(f"'{c}'" if " " in c else c for c in cmd)
        bash_cmd = ["bash", "-c", f"echo '{encoded}' | base64 -d | {inner}"]
        actual_cmd = bash_cmd
    else:
        actual_cmd = list(cmd)

    try:
        exit_code, output = container.exec_run(
            actual_cmd,
            user=user,
            demux=True,
        )
        stdout_bytes, stderr_bytes = output if output else (b"", b"")
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return exit_code, stdout, stderr
    except Exception as exc:
        logger.error("exec_in_sandbox failed cmd=%r: %s", actual_cmd, exc, exc_info=True)
        raise RuntimeError(f"Container exec failed: {exc}") from exc


def exec_in_project(
    uid: str,
    project_id: str,
    *cmd: str,
    input_bytes: Optional[bytes] = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """
    Like exec_in_sandbox but sets workdir to the project root directory.
    The project directory is guaranteed to exist (call provision_project_dir first).
    """
    project_dir = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
    container = _get_container()

    actual_cmd = list(cmd)
    if input_bytes is not None:
        encoded = base64.b64encode(input_bytes).decode("ascii")
        inner = " ".join(f"'{c}'" if " " in c else c for c in cmd)
        actual_cmd = ["bash", "-c", f"echo '{encoded}' | base64 -d | {inner}"]

    try:
        exit_code, output = container.exec_run(
            actual_cmd,
            user="root",
            workdir=project_dir,
            demux=True,
        )
        stdout_bytes, stderr_bytes = output if output else (b"", b"")
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return exit_code, stdout, stderr
    except Exception as exc:
        logger.error("exec_in_project failed cmd=%r: %s", actual_cmd, exc, exc_info=True)
        raise RuntimeError(f"Container exec failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _safe_project_path(uid: str, project_id: str, rel_path: str) -> str:
    """
    Resolve rel_path relative to /workspace/<uid>/<project_id>.
    Rejects empty paths and directory traversal.
    Returns an absolute POSIX path guaranteed to be under the project root.
    """
    if not rel_path or not rel_path.strip():
        raise ValueError("rel_path must not be empty")
    project_root = PurePosixPath(f"{WORKSPACE_ROOT}/{uid}/{project_id}")
    # Strip leading slashes so the path is always relative
    clean = PurePosixPath(rel_path.lstrip("/"))
    # Manually resolve '..' components without touching the real filesystem
    parts: list[str] = list(project_root.parts)
    for part in clean.parts:
        if part == "..":
            # Never go above project root
            if len(parts) > len(project_root.parts):
                parts.pop()
            # else: silently stay at root (traversal absorbed)
        elif part not in ("", "."):
            parts.append(part)
    result = str(PurePosixPath(*parts))
    project_root_str = str(project_root)
    if result != project_root_str and not result.startswith(project_root_str + "/"):
        raise ValueError(f"Path traversal rejected: {rel_path!r}")
    return result


# ---------------------------------------------------------------------------
# File-tree listing
# ---------------------------------------------------------------------------

class FileNode:
    """Internal representation; routes.py converts to dict for JSON."""
    __slots__ = ("name", "path", "type", "size", "children")

    def __init__(
        self,
        name: str,
        path: str,
        type: str,  # "file" | "dir"
        size: int = 0,
        children: Optional[list["FileNode"]] = None,
    ):
        self.name = name
        self.path = path
        self.type = type
        self.size = size
        self.children = children if children is not None else []

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "size": self.size,
        }
        if self.type == "dir":
            d["children"] = [c.to_dict() for c in self.children]
        return d


def list_tree(
    uid: str,
    project_id: str,
    rel_path: Optional[str],
    depth: int = 3,
) -> list[dict]:
    """
    Return a nested JSON-serialisable tree of FileNode dicts for the given path.
    rel_path=None means the project root.
    """
    if rel_path:
        safe_path = _safe_project_path(uid, project_id, rel_path)
    else:
        safe_path = f"{WORKSPACE_ROOT}/{uid}/{project_id}"

    # -printf "%P\t%y\t%s\n"  →  relative-name TAB type(f/d/l/…) TAB size
    rc, out, err = exec_in_sandbox(
        "find", safe_path,
        "-maxdepth", str(depth),
        "-printf", r"%P\t%y\t%s\n",
        timeout=15,
    )

    if rc != 0:
        # Directory might just not exist yet
        logger.warning("list_tree find failed rc=%d path=%s err=%s", rc, safe_path, err.strip())
        return []

    # Build a dict of path → FileNode for O(n) tree construction
    nodes: dict[str, FileNode] = {}
    roots: list[FileNode] = []

    for line in out.splitlines():
        # NOT .strip() — the root entry's %P is empty, so its line starts
        # with a literal tab ("\td\t4096"). .strip() silently eats that
        # leading tab as whitespace, shifting every field over by one:
        # rel_name becomes "d" (the type char) instead of "", ftype_char
        # becomes "4096" (so it's misparsed as a *file* named "d", size 0),
        # and the "skip the root" check below never fires since rel_name is
        # no longer "". splitlines() already strips the trailing newline, so
        # there's nothing left to strip here.
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        rel_name = parts[0]
        ftype_char = parts[1] if len(parts) > 1 else "f"
        size = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        ftype = "dir" if ftype_char == "d" else "file"
        # rel_name is relative to safe_path; empty string = the root itself
        if rel_name == "":
            # The root entry — skip (we return its children)
            continue

        abs_path = f"{safe_path}/{rel_name}" if safe_path != f"{WORKSPACE_ROOT}/{uid}/{project_id}" else f"{WORKSPACE_ROOT}/{uid}/{project_id}/{rel_name}"
        # Normalise to project-relative path for the API response
        proj_root = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
        display_path = abs_path[len(proj_root):].lstrip("/")

        name = rel_name.rsplit("/", 1)[-1]
        node = FileNode(name=name, path=display_path, type=ftype, size=size)
        nodes[rel_name] = node

        parent_rel = rel_name.rsplit("/", 1)[0] if "/" in rel_name else ""
        if parent_rel == "":
            roots.append(node)
        else:
            parent = nodes.get(parent_rel)
            if parent is not None:
                parent.children.append(node)
            else:
                # Parent not yet seen (shouldn't happen with sorted find output, but be safe)
                roots.append(node)

    return [n.to_dict() for n in roots]


# ---------------------------------------------------------------------------
# File read
# ---------------------------------------------------------------------------

_MIME_MAP: dict[str, str] = {
    ".py": "text/x-python",
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".js": "text/javascript",
    ".jsx": "text/javascript",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".md": "text/markdown",
    ".html": "text/html",
    ".css": "text/css",
    ".sh": "text/x-sh",
    ".env": "text/plain",
    ".txt": "text/plain",
    ".toml": "text/toml",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}


def _detect_mime(path: str) -> str:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in _MIME_MAP:
        return _MIME_MAP[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def read_file(uid: str, project_id: str, rel_path: str) -> dict:
    """
    Read a file from the dev-sandbox project directory.
    Returns:
        {
            "content":  str,              # utf-8 text or base64 string
            "encoding": "utf8"|"base64",
            "size":     int,
            "mime":     str,
        }
    Raises:
        ValueError       — path traversal or empty path
        FileNotFoundError — file not found in container
        IOError           — file exceeds MAX_FILE_BYTES
    """
    safe_path = _safe_project_path(uid, project_id, rel_path)

    rc, out, err = exec_in_sandbox("cat", safe_path, timeout=10)
    if rc != 0:
        raise FileNotFoundError(f"File not found or unreadable: {rel_path!r} ({err.strip()})")

    raw_bytes = out.encode("utf-8", errors="surrogateescape")

    if len(raw_bytes) > MAX_FILE_BYTES:
        raise IOError(
            f"File too large: {len(raw_bytes)} bytes (limit {MAX_FILE_BYTES})"
        )

    mime = _detect_mime(rel_path)

    # Binary detection: null byte anywhere → treat as binary
    if b"\x00" in raw_bytes:
        return {
            "content": base64.b64encode(raw_bytes).decode("ascii"),
            "encoding": "base64",
            "size": len(raw_bytes),
            "mime": "application/octet-stream",
        }

    return {
        "content": out,
        "encoding": "utf8",
        "size": len(raw_bytes),
        "mime": mime,
    }


# ---------------------------------------------------------------------------
# File write
# ---------------------------------------------------------------------------

def write_file(
    uid: str,
    project_id: str,
    rel_path: str,
    content: str,
    encoding: str = "utf8",
) -> None:
    """
    Write content to a file in the dev-sandbox project directory.
    Uses an atomic tmp→rename pattern.

    Raises:
        ValueError — path traversal or empty path
        IOError    — content exceeds MAX_FILE_BYTES
    """
    safe_path = _safe_project_path(uid, project_id, rel_path)
    tmp_path = safe_path + ".tmp"

    # Decode content to raw bytes
    if encoding == "base64":
        try:
            content_bytes = base64.b64decode(content)
        except Exception as exc:
            raise ValueError(f"Invalid base64 content: {exc}") from exc
    else:
        content_bytes = content.encode("utf-8")

    if len(content_bytes) > MAX_FILE_BYTES:
        raise IOError(
            f"Content too large: {len(content_bytes)} bytes (limit {MAX_FILE_BYTES})"
        )

    # Ensure parent directory exists
    parent_dir = str(PurePosixPath(safe_path).parent)
    rc, _, err = exec_in_sandbox("mkdir", "-p", parent_dir, timeout=10)
    if rc != 0:
        raise RuntimeError(f"Failed to create parent dir {parent_dir!r}: {err.strip()}")

    # Atomic write: stream bytes into tmp file, then mv
    rc, _, err = exec_in_sandbox(
        "sh", "-c", f"cat > '{tmp_path}'",
        input_bytes=content_bytes,
        timeout=15,
    )
    if rc != 0:
        raise RuntimeError(f"Failed to write tmp file {tmp_path!r}: {err.strip()}")

    rc, _, err = exec_in_sandbox("mv", tmp_path, safe_path, timeout=10)
    if rc != 0:
        raise RuntimeError(f"Failed to rename tmp→target {safe_path!r}: {err.strip()}")


# ---------------------------------------------------------------------------
# Project directory provisioning
# ---------------------------------------------------------------------------

def provision_project_dir(uid: str, project_id: str, git_ref: str = "main") -> str:
    """
    Ensure /workspace/<uid>/<project_id> exists inside the dev-sandbox, as a
    real git repo (not just a bare directory) — this is what lets a "blank"
    project run tasks at all (coordination/workspace_ops.checkout_local_project
    tars this directory into a fresh task container) and be pushed to GitHub
    later without a separate "link git" step.

    Returns the absolute path. Raises RuntimeError if the container is
    unavailable (mkdir failure); a git-init failure is logged but non-fatal —
    the directory is still usable for plain file browsing either way.
    """
    project_dir = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
    rc, _, err = exec_in_sandbox("mkdir", "-p", project_dir, timeout=10)
    if rc != 0:
        raise RuntimeError(
            f"Could not provision project dir {project_dir!r}: {err.strip()}"
        )

    q_dir = shlex.quote(project_dir)
    q_ref = shlex.quote(git_ref or "main")
    rc, out, err = exec_in_sandbox(
        "sh", "-c",
        f"cd {q_dir} && "
        f"(git init -q -b {q_ref} 2>/dev/null || (git init -q && git symbolic-ref HEAD refs/heads/{q_ref})) && "
        f"git -c user.email=memex@local -c user.name=Memex commit --allow-empty -q -m 'Initial commit'",
        timeout=15,
    )
    if rc != 0:
        logger.warning("git init failed for project dir %r (non-fatal): %s", project_dir, (err or out).strip())

    logger.info("Provisioned project dir: %s", project_dir)
    return project_dir


def project_has_content(uid: str, project_id: str) -> bool:
    """
    True if the project directory has anything besides .git — the "basic
    project setup completed" gate for Publish-to-GitHub (main.py's
    publish/preview and publish routes): a brand-new blank project is just
    the bootstrap empty commit from provision_project_dir() above, and
    publishing that would create an empty GitHub repo for no reason.

    -print -quit stops at the first match, so this is cheap even on a large tree.
    """
    project_dir = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
    q_dir = shlex.quote(project_dir)
    # The .git/* pattern MUST stay quoted — unquoted, sh -c expands it as a
    # glob before find ever sees it (against whatever files happen to match),
    # which breaks find's argument parsing as soon as there's more than one
    # match. Verified both ways in a real shell before landing this.
    rc, out, _err = exec_in_sandbox(
        "sh", "-c",
        f"find {q_dir} -mindepth 1 -not -path {q_dir}/.git -not -path '{project_dir}/.git/*' -print -quit",
        timeout=15,
    )
    return rc == 0 and bool(out.strip())


def git_clone(uid: str, project_id: str, git_url: str, git_ref: str = "main") -> str:
    """
    Clone `git_url` into /workspace/<uid>/<project_id>, checked out at
    `git_ref` if it exists (branch, tag, or SHA). If `git_ref` doesn't exist
    anywhere — e.g. the caller's default "main" against a repo whose default
    branch is still "master" — falls back to the repo's actual default
    branch rather than failing the whole clone over a guessed ref.

    Returns the ref actually checked out (equal to git_ref unless it fell
    back). Callers should persist THIS value, not the requested git_ref, or
    later operations that re-checkout by the stored ref will hit the same
    "ref doesn't exist" failure this fallback exists to avoid.

    Raises:
        ValueError   — git_url isn't https/http, or git_ref looks unsafe
        RuntimeError — container unavailable, or the clone itself failed
    """
    if not (git_url.startswith("https://") or git_url.startswith("http://")):
        raise ValueError("git_url must use https:// or http:// scheme")
    if not git_ref or git_ref.startswith("-"):
        raise ValueError(f"invalid git_ref: {git_ref!r}")

    project_dir = f"{WORKSPACE_ROOT}/{uid}/{project_id}"
    q_url = shlex.quote(git_url)
    q_ref = shlex.quote(git_ref)
    q_dir = shlex.quote(project_dir)

    # git_ref is usually a branch name, but may be a tag or commit SHA — try
    # the fast `--branch` clone first (works for branches/tags).
    rc, out, err = exec_in_sandbox(
        "sh", "-c", f"git clone --branch {q_ref} {q_url} {q_dir} 2>&1",
        timeout=180,
    )
    if rc == 0:
        logger.info("git_clone: %s@%s -> %s", git_url, git_ref, project_dir)
        return git_ref

    # --branch failed — could be a SHA (needs a plain clone + checkout) or a
    # ref that doesn't exist anywhere. Plain clone lands on the repo's real
    # default branch, then try to move to what was actually requested.
    rc2, out2, err2 = exec_in_sandbox(
        "sh", "-c", f"rm -rf {q_dir}; git clone {q_url} {q_dir} 2>&1",
        timeout=180,
    )
    if rc2 != 0:
        raise RuntimeError(f"git clone failed for {git_url!r}: {(err2 or out2).strip()[:500]}")

    rc3, out3, err3 = exec_in_sandbox(
        "sh", "-c", f"cd {q_dir} && git checkout {q_ref} 2>&1", timeout=30,
    )
    if rc3 == 0:
        logger.info("git_clone: %s@%s -> %s", git_url, git_ref, project_dir)
        return git_ref

    rc4, head_out, _head_err = exec_in_sandbox(
        "sh", "-c", f"cd {q_dir} && git rev-parse --abbrev-ref HEAD", timeout=10,
    )
    actual_ref = head_out.strip() if rc4 == 0 and head_out.strip() else git_ref
    logger.warning(
        "git_clone: ref %r not found for %s (%s) — using default branch %r instead",
        git_ref, git_url, (err3 or out3).strip()[:200], actual_ref,
    )
    return actual_ref
