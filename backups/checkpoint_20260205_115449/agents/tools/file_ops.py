import os

WORKSPACE_ROOT = "/workspace"

def read_file(path: str) -> str:
    """Reads a file from the workspace."""
    full_path = os.path.join(WORKSPACE_ROOT, path.lstrip("/"))
    try:
        with open(full_path, "r") as f:
            return f.read()
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
        
    full_path = os.path.join(WORKSPACE_ROOT, path.lstrip("/"))
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

def list_dir(path: str = ".") -> str:
    """Lists contents of a directory in the workspace."""
    full_path = os.path.join(WORKSPACE_ROOT, path.lstrip("/"))
    try:
        items = os.listdir(full_path)
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory {path}: {str(e)}"
