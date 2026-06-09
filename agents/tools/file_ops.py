import os
import threading
from pathlib import Path
from typing import Callable, Optional

WORKSPACE_ROOT = Path("/workspace").resolve()

# ---------------------------------------------------------------------------
# file_change SSE sink
# Thread-local callable set by the SSE coordinator loop before invoking the
# agent tool.  When set, write_file() emits a file_change event into the
# active stream so the UI can show inline activity chips.
# ---------------------------------------------------------------------------
_file_change_sink: threading.local = threading.local()


def set_file_change_sink(sink: Optional[Callable[[dict], None]]) -> None:
    """Register a callable that receives file_change event dicts.

    Call with ``None`` to clear.  The sink must be non-blocking (e.g. it
    should put() onto a queue, not yield directly).
    """
    _file_change_sink.callback = sink


def _emit_file_change(op: str, path: str, size: int) -> None:
    """Fire a file_change event if a sink is registered for this thread."""
    cb = getattr(_file_change_sink, "callback", None)
    if callable(cb):
        try:
            cb({"type": "file_change", "content": {"op": op, "path": path, "size": size}})
        except Exception:
            pass  # sink errors must never break the tool call


def _resolve_in_workspace(path: str) -> Path:
    candidate = (WORKSPACE_ROOT / path.lstrip("/")).resolve()
    if candidate != WORKSPACE_ROOT and WORKSPACE_ROOT not in candidate.parents:
        raise PermissionError("Path traversal detected")
    return candidate

def read_file(path: str) -> str:
    """Reads a file from the workspace."""
    try:
        full_path = _resolve_in_workspace(path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except PermissionError as e:
        return f"Security error reading file {path}: {str(e)}"
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file in the workspace."""
    # --- MAESTRO LAYER 6 SECURITY: TOOL GUARDRAILS ---
    protected_files = [".env", "docker-compose.yml", "agents/security_agent.py"]

    # Normalize path for check
    clean_path = path.lstrip("/").replace("\\", "/")

    # CHECK 1: Explicit Blacklist
    if any(clean_path.endswith(f) for f in protected_files):
        return f"🔒 SECURITY BLOCK: Access to {clean_path} is RESTRICTED by Layer 6 Policy."

    try:
        full_path = _resolve_in_workspace(path)
        # Determine whether this is a create or modify before writing
        op = "modified" if full_path.exists() else "created"
        os.makedirs(full_path.parent, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        size = len(content.encode("utf-8"))
        _emit_file_change(op, clean_path, size)
        return f"Successfully wrote to {path}"
    except PermissionError as e:
        return f"Security error writing file {path}: {str(e)}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

def list_dir(path: str = ".") -> str:
    """Lists contents of a directory in the workspace."""
    try:
        full_path = _resolve_in_workspace(path)
        items = os.listdir(full_path)
        return "\n".join(items)
    except PermissionError as e:
        return f"Security error listing directory {path}: {str(e)}"
    except Exception as e:
        return f"Error listing directory {path}: {str(e)}"
