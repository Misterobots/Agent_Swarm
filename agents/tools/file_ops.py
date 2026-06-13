import os
from pathlib import Path

# Shared with sandbox_ops: the file_change SSE sink and the MAESTRO blacklist.
# set_file_change_sink is re-exported here for existing callers (e.g. the
# coordination executor); _emit_file_change keeps the legacy name used below.
from tools.file_change_sink import set_file_change_sink, emit_file_change as _emit_file_change
from tools.maestro_guard import is_protected_path

WORKSPACE_ROOT = Path("/workspace").resolve()


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
    clean_path = path.lstrip("/").replace("\\", "/")
    if is_protected_path(path):
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
