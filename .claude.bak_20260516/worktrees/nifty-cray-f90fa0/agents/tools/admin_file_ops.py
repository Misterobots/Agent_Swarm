"""
Admin-level file operations with unrestricted system access.
These tools bypass workspace sandboxing and can access any path on Lovelace, Turing, or Hopper.
Only available to L3_ADMIN users.
"""
import os
import subprocess
from pathlib import Path
from typing import Literal

NodeName = Literal["lovelace", "turing", "hopper", "local"]

NODE_IPS = {
    "lovelace": "192.168.2.101",
    "turing": "192.168.2.103",
    "hopper": "192.168.2.102",
}

SSH_USER = "misterobots"
SSH_BIN = "C:\\Windows\\System32\\OpenSSH\\ssh.exe"


def _ssh_exec(node: str, command: str) -> dict:
    """Execute command via SSH on target node."""
    if node == "local":
        # Local execution on Turing (current container host)
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else ""
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    if node not in NODE_IPS:
        return {"success": False, "output": "", "error": f"Invalid node: {node}"}
    
    ip = NODE_IPS[node]
    ssh_cmd = [
        SSH_BIN,
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        f"{SSH_USER}@{ip}",
        command
    ]
    
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8"
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else ""
        }
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def admin_read_file(node: str, path: str) -> str:
    """Read any file on specified node (admin only)."""
    # Use cat with error handling
    command = f"cat {path}"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error reading {node}:{path}: {result['error']}"
    
    return result["output"]


def admin_write_file(node: str, path: str, content: str) -> str:
    """Write to any file on specified node (admin only)."""
    # Escape single quotes in content for shell safety
    safe_content = content.replace("'", "'\\''")
    
    # Ensure parent directory exists and write file
    command = f"mkdir -p $(dirname {path}) && echo '{safe_content}' > {path}"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error writing {node}:{path}: {result['error']}"
    
    return f"✓ Successfully wrote to {node}:{path}"


def admin_list_dir(node: str, path: str) -> str:
    """List directory contents on specified node (admin only)."""
    command = f"ls -lah {path}"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error listing {node}:{path}: {result['error']}"
    
    return f"Contents of {node}:{path}:\n{result['output']}"


def admin_delete_file(node: str, path: str) -> str:
    """Delete file on specified node (admin only)."""
    command = f"rm -f {path}"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error deleting {node}:{path}: {result['error']}"
    
    return f"✓ Deleted {node}:{path}"


def admin_file_exists(node: str, path: str) -> str:
    """Check if file exists on specified node (admin only)."""
    command = f"test -e {path} && echo 'EXISTS' || echo 'NOT_FOUND'"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error checking {node}:{path}: {result['error']}"
    
    exists = "EXISTS" in result["output"]
    return f"{'✓' if exists else '✗'} {node}:{path} {'exists' if exists else 'not found'}"
