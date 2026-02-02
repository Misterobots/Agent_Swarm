import subprocess
import os

def run_git_cmd(cmd_list):
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + cmd_list, 
            capture_output=True, 
            text=True, 
            check=True,
            cwd=os.getcwd() # Run in current project root
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"
    except Exception as e:
        return f"System Error: {str(e)}"

def get_current_branch():
    return run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])

def get_branches():
    raw = run_git_cmd(["branch", "--list"])
    clean_list = [b.replace("*", "").strip() for b in raw.split("\n") if b.strip()]
    return clean_list

def create_branch(name):
    # Create and checkout
    return run_git_cmd(["checkout", "-b", name])

def checkout_branch(name):
    return run_git_cmd(["checkout", name])

def get_status():
    return run_git_cmd(["status", "--short"])

def stage_all():
    return run_git_cmd(["add", "."])

def commit_changes(message):
    return run_git_cmd(["commit", "-m", message])

def get_diff():
    # Show diff of staged/unstaged changes
    return run_git_cmd(["diff", "HEAD"])
