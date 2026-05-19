"""
Git operations for L3_ADMIN users via SSH to remote nodes.
Allows checkout, commit, push operations on Lovelace, Turing, and Hopper.
"""
import subprocess
import json
from typing import Literal

NodeName = Literal["lovelace", "turing", "hopper"]

NODE_IPS = {
    "lovelace": "192.168.2.101",
    "turing": "192.168.2.103",
    "hopper": "192.168.2.102",
}

SSH_USER = "misterobots"
SSH_BIN = "C:\\Windows\\System32\\OpenSSH\\ssh.exe"  # Windows SSH path


def _ssh_exec(node: str, command: str) -> dict:
    """Execute command via SSH on target node."""
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
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "SSH command timed out"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def git_status(node: str, repo_path: str) -> str:
    """Get git status for repository on target node."""
    command = f"cd {repo_path} && git status --porcelain && git branch --show-current"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error getting git status on {node}: {result['error']}"
    
    lines = result["output"].split("\n")
    branch = lines[-1] if lines else "unknown"
    status_lines = lines[:-1] if len(lines) > 1 else []
    
    if not status_lines:
        return f"✓ {node}:{repo_path} is clean (branch: {branch})"
    
    return f"Branch: {branch}\nModified files:\n" + "\n".join(status_lines)


def git_checkout(node: str, repo_path: str, branch: str) -> str:
    """Checkout a git branch on target node."""
    command = f"cd {repo_path} && git checkout {branch}"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error checking out branch '{branch}' on {node}: {result['error']}"
    
    return f"✓ Checked out '{branch}' on {node}:{repo_path}\n{result['output']}"


def git_commit(node: str, repo_path: str, message: str, files: list[str] = None) -> str:
    """Commit changes on target node."""
    # Add specified files or all changes
    if files:
        add_cmd = f"cd {repo_path} && git add {' '.join(files)}"
    else:
        add_cmd = f"cd {repo_path} && git add -A"
    
    add_result = _ssh_exec(node, add_cmd)
    if not add_result["success"]:
        return f"Error adding files on {node}: {add_result['error']}"
    
    # Commit with message
    commit_cmd = f"cd {repo_path} && git commit -m \"{message}\""
    commit_result = _ssh_exec(node, commit_cmd)
    
    if not commit_result["success"]:
        # Check if it's "nothing to commit" which is not really an error
        if "nothing to commit" in commit_result["error"].lower():
            return f"✓ No changes to commit on {node}:{repo_path}"
        return f"Error committing on {node}: {commit_result['error']}"
    
    return f"✓ Committed on {node}:{repo_path}\n{commit_result['output']}"


def git_push(node: str, repo_path: str, remote: str = "origin", branch: str = None) -> str:
    """Push commits to remote on target node."""
    # Get current branch if not specified
    if not branch:
        branch_cmd = f"cd {repo_path} && git branch --show-current"
        branch_result = _ssh_exec(node, branch_cmd)
        if not branch_result["success"]:
            return f"Error getting current branch on {node}: {branch_result['error']}"
        branch = branch_result["output"].strip()
    
    # Push to remote
    push_cmd = f"cd {repo_path} && git push {remote} {branch}"
    push_result = _ssh_exec(node, push_cmd)
    
    if not push_result["success"]:
        return f"Error pushing to {remote}/{branch} on {node}: {push_result['error']}"
    
    return f"✓ Pushed {branch} to {remote} on {node}:{repo_path}\n{push_result['output']}"


def git_pull(node: str, repo_path: str, remote: str = "origin", branch: str = None) -> str:
    """Pull latest changes from remote on target node."""
    if branch:
        pull_cmd = f"cd {repo_path} && git pull {remote} {branch}"
    else:
        pull_cmd = f"cd {repo_path} && git pull"
    
    result = _ssh_exec(node, pull_cmd)
    
    if not result["success"]:
        return f"Error pulling from {remote} on {node}: {result['error']}"
    
    return f"✓ Pulled latest changes on {node}:{repo_path}\n{result['output']}"


def git_branch_list(node: str, repo_path: str) -> str:
    """List all branches on target node."""
    command = f"cd {repo_path} && git branch -a"
    result = _ssh_exec(node, command)
    
    if not result["success"]:
        return f"Error listing branches on {node}: {result['error']}"
    
    return f"Branches on {node}:{repo_path}:\n{result['output']}"
