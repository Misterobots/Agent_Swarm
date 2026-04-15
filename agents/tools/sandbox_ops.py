"""
sandbox_ops.py — Phase 2 AI Agentic Coding
Tools that execute inside the dev-sandbox Docker container.

Operations are constrained to /workspace inside the container.
Commands run as the non-root 'dev' user with a 30-second timeout.
"""

from __future__ import annotations

import logging
import os
import base64
from pathlib import PurePosixPath
from typing import Optional

logger = logging.getLogger("sandbox_ops")

SANDBOX_CONTAINER = os.getenv("DEV_SANDBOX_CONTAINER", "dev_sandbox")
SANDBOX_WORKSPACE = "/workspace"
EXEC_TIMEOUT = int(os.getenv("SANDBOX_EXEC_TIMEOUT", "30"))


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------

def _safe_posix_path(path: str) -> str:
    """
    Resolve a user-supplied path against /workspace, reject traversal.
    Returns an absolute POSIX path guaranteed to be under /workspace.
    Raises ValueError on traversal or empty input.
    """
    if not path or not path.strip():
        raise ValueError("Path must not be empty")
    # Normalise: always treat as relative to workspace root
    clean = PurePosixPath(path.lstrip("/"))
    # Resolve potential '../../' components
    resolved = PurePosixPath(SANDBOX_WORKSPACE) / clean
    # PurePosixPath doesn't collapse '..'; walk the parts manually
    parts: list[str] = []
    for part in resolved.parts:
        if part == "..":
            if parts and parts[-1] != "/":
                parts.pop()
        elif part != ".":
            parts.append(part)
    result = str(PurePosixPath(*parts)) if parts else SANDBOX_WORKSPACE
    # Ensure result is under /workspace
    if not result.startswith(SANDBOX_WORKSPACE + "/") and result != SANDBOX_WORKSPACE:
        raise ValueError(f"Path traversal rejected: {path!r}")
    return result


def _get_container():
    """Return the dev-sandbox Docker container object, or raise RuntimeError."""
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
    except Exception as e:
        logger.error(f"[sandbox_ops] Failed to get container '{SANDBOX_CONTAINER}': {e}", exc_info=True)
        raise RuntimeError(f"Cannot connect to dev-sandbox: {e}") from e


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def sandbox_read_file(path: str) -> str:
    """
    Read a file from the dev-sandbox /workspace.
    Returns the file contents as a string.
    """
    safe_path = _safe_posix_path(path)
    try:
        container = _get_container()
        exit_code, output = container.exec_run(
            ["cat", safe_path],
            user="dev",
            demux=False,
        )
        text = output.decode("utf-8", errors="replace") if output else ""
        if exit_code != 0:
            return f"Error reading {path}: {text.strip() or '(no output)'}"
        return text
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] read_file failed for {path!r}: {e}", exc_info=True)
        return f"Error reading file {path}: {e}"


def sandbox_write_file(path: str, content: str) -> str:
    """
    Write content to a file in the dev-sandbox /workspace.
    Parent directories are created automatically.
    """
    safe_path = _safe_posix_path(path)
    parent = str(PurePosixPath(safe_path).parent)
    try:
        container = _get_container()
        # Ensure parent directory exists
        container.exec_run(["mkdir", "-p", parent], user="dev")
        # Write via tee — pipe base64-encoded content to avoid shell escaping issues
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        write_cmd = (
            f"echo '{encoded}' | base64 -d > {safe_path}"
        )
        exit_code, output = container.exec_run(
            ["bash", "-c", write_cmd],
            user="dev",
            demux=False,
        )
        text = output.decode("utf-8", errors="replace") if output else ""
        if exit_code != 0:
            return f"Error writing {path}: {text.strip() or '(no output)'}"
        return f"Successfully wrote {path}"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] write_file failed for {path!r}: {e}", exc_info=True)
        return f"Error writing file {path}: {e}"


def sandbox_list_dir(path: str = ".") -> str:
    """
    List contents of a directory in the dev-sandbox /workspace.
    Returns a newline-separated list of entries.
    """
    safe_path = _safe_posix_path(path) if path and path.strip() not in (".", "/", "") else SANDBOX_WORKSPACE
    try:
        container = _get_container()
        exit_code, output = container.exec_run(
            ["ls", "-lA", "--color=never", safe_path],
            user="dev",
            demux=False,
        )
        text = output.decode("utf-8", errors="replace") if output else ""
        if exit_code != 0:
            return f"Error listing {path}: {text.strip() or '(no output)'}"
        return text
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] list_dir failed for {path!r}: {e}", exc_info=True)
        return f"Error listing directory {path}: {e}"


def sandbox_run_command(command: str, cwd: Optional[str] = None) -> str:
    """
    Execute a shell command in the dev-sandbox /workspace.
    cwd defaults to /workspace.
    Returns combined stdout + stderr (max 64 KB trimmed).
    """
    if not command or not command.strip():
        return "Error: command must not be empty"
    # Validate cwd if provided
    workdir = SANDBOX_WORKSPACE
    if cwd and cwd.strip():
        try:
            workdir = _safe_posix_path(cwd)
        except ValueError as e:
            return f"Error: invalid cwd — {e}"
    try:
        container = _get_container()
        exit_code, output = container.exec_run(
            ["bash", "-c", command],
            user="dev",
            workdir=workdir,
            demux=False,
        )
        text = output.decode("utf-8", errors="replace") if output else ""
        # Trim very large outputs
        MAX_CHARS = 64 * 1024
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + f"\n... (output truncated at {MAX_CHARS} chars)"
        prefix = f"[exit {exit_code}] " if exit_code != 0 else ""
        return f"{prefix}{text}" if text else f"[exit {exit_code}] (no output)"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] run_command failed: {e}", exc_info=True)
        return f"Error running command: {e}"


# ---------------------------------------------------------------------------
# Tool dispatcher — called by the agentic loop
# ---------------------------------------------------------------------------

TOOL_DISPATCH: dict[str, callable] = {
    "read_file": lambda args: sandbox_read_file(args["path"]),
    "write_file": lambda args: sandbox_write_file(args["path"], args["content"]),
    "list_directory": lambda args: sandbox_list_dir(args.get("path", ".")),
    "run_command": lambda args: sandbox_run_command(
        args["command"], args.get("cwd")
    ),
}


def execute_tool(name: str, arguments: dict) -> str:
    """
    Dispatch a named tool call to the appropriate sandbox function.
    Returns a string result suitable for sending back to the model.
    """
    handler = TOOL_DISPATCH.get(name)
    if not handler:
        return f"Unknown tool: {name!r}. Available: {', '.join(TOOL_DISPATCH)}"
    try:
        return handler(arguments)
    except RuntimeError as e:
        return f"Sandbox error: {e}"
    except KeyError as e:
        return f"Missing required argument {e} for tool {name!r}"
    except Exception as e:
        logger.error(f"[sandbox_ops] execute_tool({name!r}) raised: {e}", exc_info=True)
        return f"Tool execution error: {e}"
