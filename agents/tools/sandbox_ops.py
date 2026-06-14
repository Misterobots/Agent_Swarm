"""
sandbox_ops.py — AI agentic coding tools that execute inside the dev-sandbox
Docker container.

Operations are constrained to /workspace inside the container.  Commands run as
the non-root 'dev' user.  File writes/edits enforce the MAESTRO protected-files
guardrail and emit file_change events (edit_file includes a unified diff) so the
UI can show inline activity + diffs.
"""

from __future__ import annotations

import base64
import difflib
import logging
import os
from pathlib import PurePosixPath
from typing import Optional

from tools.file_change_sink import emit_file_change
from tools.maestro_guard import is_protected_path

logger = logging.getLogger("sandbox_ops")

SANDBOX_CONTAINER = os.getenv("DEV_SANDBOX_CONTAINER", "dev_sandbox")
SANDBOX_WORKSPACE = "/workspace"
EXEC_TIMEOUT = int(os.getenv("SANDBOX_EXEC_TIMEOUT", "30"))

_MAX_OUTPUT = 64 * 1024          # cap returned command/search output
_MAX_DIFF_RETURN = 6 * 1024      # cap the diff echoed back to the model


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------

def _safe_posix_path(path: str) -> str:
    """
    Resolve a user-supplied path against /workspace, reject traversal.
    Returns an absolute POSIX path guaranteed to be under /workspace.
    Raises ValueError on traversal or empty input.

    Handles paths that already start with /workspace/ (e.g. /workspace/foo.py)
    by stripping the prefix before re-joining — avoiding /workspace/workspace/foo.py.
    """
    if not path or not path.strip():
        raise ValueError("Path must not be empty")
    p = path.strip()
    # Strip existing /workspace prefix so "/workspace/foo.py" → "foo.py" before joining.
    if p == SANDBOX_WORKSPACE:
        return SANDBOX_WORKSPACE
    if p.startswith(SANDBOX_WORKSPACE + "/"):
        p = p[len(SANDBOX_WORKSPACE):]  # → "/foo.py"
    clean = PurePosixPath(p.lstrip("/"))
    resolved = PurePosixPath(SANDBOX_WORKSPACE) / clean
    parts: list[str] = []
    for part in resolved.parts:
        if part == "..":
            if parts and parts[-1] != "/":
                parts.pop()
        elif part != ".":
            parts.append(part)
    result = str(PurePosixPath(*parts)) if parts else SANDBOX_WORKSPACE
    if not result.startswith(SANDBOX_WORKSPACE + "/") and result != SANDBOX_WORKSPACE:
        raise ValueError(f"Path traversal rejected: {path!r}")
    return result


def _rel_workspace(abs_path: str) -> str:
    """Strip the /workspace/ prefix for display/file_change paths."""
    if abs_path.startswith(SANDBOX_WORKSPACE + "/"):
        return abs_path[len(SANDBOX_WORKSPACE) + 1:]
    return abs_path.lstrip("/")


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
# Exec helpers
# ---------------------------------------------------------------------------

def _exec(cmd: list[str], workdir: str = SANDBOX_WORKSPACE) -> tuple[int, str]:
    """Run a command (list form, no shell — injection-safe) as 'dev'."""
    container = _get_container()
    exit_code, output = container.exec_run(cmd, user="dev", workdir=workdir, demux=False)
    text = output.decode("utf-8", errors="replace") if output else ""
    return exit_code, text


def _exec_bash(command: str, workdir: str = SANDBOX_WORKSPACE) -> tuple[int, str]:
    """Run a shell command string as 'dev' (used for redirections like base64 -d > file)."""
    container = _get_container()
    exit_code, output = container.exec_run(["bash", "-c", command], user="dev", workdir=workdir, demux=False)
    text = output.decode("utf-8", errors="replace") if output else ""
    return exit_code, text


def _write_raw(safe_path: str, content: str) -> tuple[int, str]:
    """Write content to safe_path via base64 tee (avoids shell-escaping issues)."""
    parent = str(PurePosixPath(safe_path).parent)
    _exec(["mkdir", "-p", parent])
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return _exec_bash(f"echo '{encoded}' | base64 -d > {safe_path}")


def _file_exists(safe_path: str) -> bool:
    try:
        ec, _ = _exec(["test", "-f", safe_path])
        return ec == 0
    except Exception:
        return False


def _compute_unified_diff(old: str, new: str, path: str) -> str:
    """Pure unified-diff between two strings (testable without a container)."""
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def sandbox_read_file(path: str) -> str:
    """Read a file from the dev-sandbox /workspace."""
    safe_path = _safe_posix_path(path)
    try:
        exit_code, text = _exec(["cat", safe_path])
        if exit_code != 0:
            return f"Error reading {path}: {text.strip() or '(no output)'}"
        return text
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] read_file failed for {path!r}: {e}", exc_info=True)
        return f"Error reading file {path}: {e}"


def sandbox_write_file(path: str, content: str) -> str:
    """Write (full overwrite) a file in the dev-sandbox /workspace."""
    if is_protected_path(path):
        return f"🔒 SECURITY BLOCK: {path} is RESTRICTED by MAESTRO Layer 6 policy."
    safe_path = _safe_posix_path(path)
    try:
        op = "modified" if _file_exists(safe_path) else "created"
        exit_code, text = _write_raw(safe_path, content)
        if exit_code != 0:
            return f"Error writing {path}: {text.strip() or '(no output)'}"
        emit_file_change(op, _rel_workspace(safe_path), len(content.encode("utf-8")))
        return f"Successfully wrote {path}"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] write_file failed for {path!r}: {e}", exc_info=True)
        return f"Error writing file {path}: {e}"


def sandbox_edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Exact-string replace in a sandbox file; returns (and emits) a unified diff."""
    if is_protected_path(path):
        return f"🔒 SECURITY BLOCK: {path} is RESTRICTED by MAESTRO Layer 6 policy."
    if old_string == new_string:
        return "Error: old_string and new_string are identical — nothing to change."
    safe_path = _safe_posix_path(path)
    try:
        exit_code, current = _exec(["cat", safe_path])
        if exit_code != 0:
            return f"Error: cannot read {path}: {current.strip() or '(missing)'}"

        count = current.count(old_string)
        if count == 0:
            return (f"Error: old_string not found in {path}. "
                    "Read the file and copy the exact text (including whitespace).")
        if count > 1 and not replace_all:
            return (f"Error: old_string appears {count}× in {path} — not unique. "
                    "Add surrounding context to make it unique, or pass replace_all=true.")

        new_content = (current.replace(old_string, new_string)
                       if replace_all else current.replace(old_string, new_string, 1))

        w_exit, w_text = _write_raw(safe_path, new_content)
        if w_exit != 0:
            return f"Error writing {path}: {w_text.strip() or '(no output)'}"

        rel = _rel_workspace(safe_path)
        diff = _compute_unified_diff(current, new_content, rel)
        emit_file_change("modified", rel, len(new_content.encode("utf-8")), diff=diff)

        n = count if replace_all else 1
        shown = diff if len(diff) <= _MAX_DIFF_RETURN else diff[:_MAX_DIFF_RETURN] + "\n... (diff truncated)"
        return f"Edited {path} ({n} replacement{'s' if n != 1 else ''}).\n{shown}"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] edit_file failed for {path!r}: {e}", exc_info=True)
        return f"Error editing file {path}: {e}"


def sandbox_list_dir(path: str = ".") -> str:
    """List contents of a directory in the dev-sandbox /workspace."""
    safe_path = _safe_posix_path(path) if path and path.strip() not in (".", "/", "") else SANDBOX_WORKSPACE
    try:
        exit_code, text = _exec(["ls", "-lA", "--color=never", safe_path])
        if exit_code != 0:
            return f"Error listing {path}: {text.strip() or '(no output)'}"
        return text
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] list_dir failed for {path!r}: {e}", exc_info=True)
        return f"Error listing directory {path}: {e}"


def sandbox_run_command(command: str, cwd: Optional[str] = None) -> str:
    """Execute a shell command in the dev-sandbox /workspace (combined stdout+stderr)."""
    if not command or not command.strip():
        return "Error: command must not be empty"
    workdir = SANDBOX_WORKSPACE
    if cwd and cwd.strip():
        try:
            workdir = _safe_posix_path(cwd)
        except ValueError as e:
            return f"Error: invalid cwd — {e}"
    try:
        exit_code, text = _exec_bash(command, workdir=workdir)
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n... (output truncated at {_MAX_OUTPUT} chars)"
        prefix = f"[exit {exit_code}] " if exit_code != 0 else ""
        return f"{prefix}{text}" if text else f"[exit {exit_code}] (no output)"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] run_command failed: {e}", exc_info=True)
        return f"Error running command: {e}"


def sandbox_glob(pattern: str) -> str:
    """List files matching a glob (ripgrep --files -g; .gitignore-aware, with a find fallback)."""
    if not pattern or not pattern.strip():
        return "Error: pattern must not be empty"
    try:
        try:
            exit_code, text = _exec(["rg", "--files", "-g", pattern])
            if exit_code in (126, 127):  # ripgrep missing (sandbox not yet rebuilt)
                raise FileNotFoundError
        except (RuntimeError,):
            raise
        except Exception:
            base = pattern.rsplit("/", 1)[-1] or pattern
            exit_code, text = _exec(["find", ".", "-type", "f", "-name", base])
            text = "\n".join(l[2:] if l.startswith("./") else l for l in text.splitlines())
        text = text.strip()
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n... (truncated at {_MAX_OUTPUT} chars)"
        return text if text else f"No files match {pattern!r}."
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] glob failed: {e}", exc_info=True)
        return f"Error running glob: {e}"


def sandbox_grep(pattern: str, path: str = ".", ignore_case: bool = False, glob: Optional[str] = None) -> str:
    """Search file contents with ripgrep (line numbers; grep fallback)."""
    if not pattern or not pattern.strip():
        return "Error: pattern must not be empty"
    safe = _safe_posix_path(path) if path and path.strip() not in (".", "/", "") else SANDBOX_WORKSPACE
    try:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never"]
        if ignore_case:
            cmd.append("-i")
        if glob:
            cmd += ["-g", glob]
        cmd += ["--", pattern, safe]
        try:
            exit_code, text = _exec(cmd)
            if exit_code in (126, 127):
                raise FileNotFoundError
        except (RuntimeError,):
            raise
        except Exception:
            gcmd = ["grep", "-rn"] + (["-i"] if ignore_case else []) + ["--", pattern, safe]
            exit_code, text = _exec(gcmd)
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n... (truncated at {_MAX_OUTPUT} chars)"
        return text.strip() or f"No matches for {pattern!r}."
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] grep failed: {e}", exc_info=True)
        return f"Error running grep: {e}"


_GIT_ALLOW = {"status", "diff", "log", "add", "commit", "branch", "show", "init"}


def sandbox_git(command: str, message: Optional[str] = None, paths: Optional[list] = None) -> str:
    """Run an allowlisted git subcommand in /workspace (status/diff/log/add/commit/branch/show/init)."""
    sub = (command or "").strip()
    if sub not in _GIT_ALLOW:
        return f"Error: unsupported git command {command!r}. Allowed: {', '.join(sorted(_GIT_ALLOW))}"
    base = ["git", "-C", SANDBOX_WORKSPACE,
            "-c", "user.email=dev@hive.local", "-c", "user.name=HiveCode"]
    paths = [str(p) for p in (paths or [])]
    if sub == "status":
        cmd = base + ["status", "--short", "--branch"]
    elif sub == "diff":
        cmd = base + ["diff"] + paths
    elif sub == "log":
        cmd = base + ["log", "--oneline", "-n", "20"]
    elif sub == "branch":
        cmd = base + ["branch", "--show-current"]
    elif sub == "show":
        cmd = base + ["show", "--stat", "-1"]
    elif sub == "init":
        cmd = base + ["init"]
    elif sub == "add":
        cmd = base + ["add"] + (paths or ["-A"])
    elif sub == "commit":
        if not message:
            return "Error: git commit requires a 'message'."
        cmd = base + ["commit", "-m", message]
    else:  # unreachable (allowlisted)
        return f"Error: unsupported git command {command!r}."
    try:
        exit_code, text = _exec(cmd)
        text = text.strip()
        if exit_code != 0 and "nothing to commit" in text.lower():
            return "Nothing to commit — working tree clean."
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n... (truncated at {_MAX_OUTPUT} chars)"
        prefix = "" if exit_code == 0 else f"[git exit {exit_code}] "
        return f"{prefix}{text or '(no output)'}"
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"[sandbox_ops] git {sub} failed: {e}", exc_info=True)
        return f"Error running git {sub}: {e}"


# ---------------------------------------------------------------------------
# Tool dispatcher — called by the agentic loop
# ---------------------------------------------------------------------------

TOOL_DISPATCH: dict[str, callable] = {
    "read_file": lambda a: sandbox_read_file(a["path"]),
    "write_file": lambda a: sandbox_write_file(a["path"], a["content"]),
    "edit_file": lambda a: sandbox_edit_file(
        a["path"], a["old_string"], a["new_string"], a.get("replace_all", False)
    ),
    "list_directory": lambda a: sandbox_list_dir(a.get("path", ".")),
    "run_command": lambda a: sandbox_run_command(a["command"], a.get("cwd")),
    "glob": lambda a: sandbox_glob(a["pattern"]),
    "grep": lambda a: sandbox_grep(
        a["pattern"], a.get("path", "."), a.get("ignore_case", False), a.get("glob")
    ),
    "git": lambda a: sandbox_git(a["command"], a.get("message"), a.get("paths")),
}

# Tools that only read — used by plan mode + the permission gate (Phase 1/2).
READ_ONLY_TOOLS: frozenset[str] = frozenset({"read_file", "list_directory", "glob", "grep"})


def execute_tool(name: str, arguments: dict) -> str:
    """Dispatch a named tool call to the appropriate sandbox function."""
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
