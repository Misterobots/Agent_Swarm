"""
dev_files/docker_exec.py — Low-level Docker exec helpers for the dev-sandbox container.

All filesystem operations are scoped to WORKSPACE_ROOT inside the container.
Commands run as the non-root 'dev' user.
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

logger = logging.getLogger("agents.dev_files.docker_exec")

SANDBOX_CONTAINER = os.getenv("DEV_SANDBOX_CONTAINER", "dev_sandbox")
WORKSPACE_ROOT = os.getenv("DEV_WORKSPACE_ROOT", "/workspace")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_container():
    """Return the running dev-sandbox Docker container, or raise RuntimeError."""
    try:
        import docker
        client = docker.from_env()
        container = client.containers.get(SANDBOX_CONTAINER)
        if container.status != "running":
            raise RuntimeError(
                f"dev-sandbox container '{SANDBOX_CONTAINER}' is not running "
                f"(status={container.status!r}). Start it with: "
                "docker compose -f execution_plane/docker-compose.yml up dev-sandbox"
            )
        return container
    except ImportError:
        raise RuntimeError(
            "docker Python package not installed. "
            "Add 'docker' to the agent_runtime requirements."
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Cannot connect to dev-sandbox: {exc}") from exc


# ---------------------------------------------------------------------------
# Public primitives
# ---------------------------------------------------------------------------

def exec_in_sandbox(*cmd: str, timeout: int = 30) -> Tuple[int, bytes, bytes]:
    """
    Execute an arbitrary command inside the dev-sandbox container.

    Returns (exit_code, stdout_bytes, stderr_bytes).
    The caller is responsible for interpreting the result.
    """
    container = _get_container()
    result = container.exec_run(
        list(cmd),
        user="dev",
        demux=True,
        stdout=True,
        stderr=True,
    )
    # demux=True → result.output is (stdout_bytes | None, stderr_bytes | None)
    exit_code = result.exit_code
    stdout, stderr = result.output if result.output else (b"", b"")
    return exit_code, (stdout or b""), (stderr or b"")


def provision_project_dir(uid: str, project_id: str) -> None:
    """
    Create the directory skeleton for a blank project inside the dev-sandbox.

    Creates:
      {WORKSPACE_ROOT}/{uid}/{project_id}/
      {WORKSPACE_ROOT}/{uid}/{project_id}/.memex/notes.md
    """
    project_root = f"{WORKSPACE_ROOT}/{uid}/{project_id}"

    rc, _, err = exec_in_sandbox("mkdir", "-p", project_root, timeout=10)
    if rc != 0:
        raise RuntimeError(
            f"Failed to create project directory '{project_root}': "
            f"{err.decode(errors='replace')[:200]}"
        )

    rc, _, err = exec_in_sandbox("mkdir", "-p", f"{project_root}/.memex", timeout=10)
    if rc != 0:
        raise RuntimeError(
            f"Failed to create .memex directory: {err.decode(errors='replace')[:200]}"
        )

    # Create notes.md only if it doesn't already exist
    rc, _, err = exec_in_sandbox(
        "sh", "-c",
        f'[ -f "{project_root}/.memex/notes.md" ] || '
        f'echo "# Project Notes" > "{project_root}/.memex/notes.md"',
        timeout=10,
    )
    if rc != 0:
        raise RuntimeError(
            f"Failed to create notes.md: {err.decode(errors='replace')[:200]}"
        )

    logger.info(f"[docker_exec] Provisioned blank project dir: {project_root}")


def git_clone(
    uid: str,
    project_id: str,
    git_url: str,
    git_ref: str = "main",
) -> None:
    """
    Clone a public git repository into the project directory inside the sandbox.

    Only https:// and http:// URLs are permitted (rejects git://, ssh://, etc.).
    A shallow clone (--depth 50) is performed to keep the sandbox lean.

    Raises:
        ValueError: if the URL scheme is not permitted.
        RuntimeError: if the clone fails (partial clone is cleaned up).
    """
    if not (git_url.startswith("https://") or git_url.startswith("http://")):
        raise ValueError(
            f"Unsafe git URL scheme. Only https:// is permitted. Got: {git_url!r}"
        )

    project_root = f"{WORKSPACE_ROOT}/{uid}/{project_id}"

    # Ensure parent uid directory exists
    exec_in_sandbox("mkdir", "-p", f"{WORKSPACE_ROOT}/{uid}", timeout=10)

    rc, out, err = exec_in_sandbox(
        "git", "clone",
        "--depth", "50",
        "--branch", git_ref,
        git_url,
        project_root,
        timeout=300,  # 5-minute timeout for large repos
    )
    if rc != 0:
        # Clean up any partial clone before raising
        exec_in_sandbox("rm", "-rf", project_root, timeout=30)
        raise RuntimeError(
            f"git clone failed (rc={rc}): "
            f"{err.decode(errors='replace')[:500]}"
        )

    # Ensure .memex/notes.md exists (may already be in the repo)
    exec_in_sandbox("mkdir", "-p", f"{project_root}/.memex", timeout=10)
    exec_in_sandbox(
        "sh", "-c",
        f'[ -f "{project_root}/.memex/notes.md" ] || '
        f'echo "# Project Notes" > "{project_root}/.memex/notes.md"',
        timeout=10,
    )

    logger.info(
        f"[docker_exec] Cloned {git_url}@{git_ref} → {project_root}"
    )
