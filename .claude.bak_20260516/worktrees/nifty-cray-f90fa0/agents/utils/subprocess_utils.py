# Windows Subprocess Console Suppression
# Add this utility to agents/utils/ to prevent console windows from popping up

import subprocess
import sys
import os

def get_subprocess_flags():
    """
    Get platform-specific subprocess creation flags to prevent console windows.
    
    On Windows, this returns CREATE_NO_WINDOW to suppress console popup.
    On Linux/Mac, returns 0 (no special flags needed).
    
    Usage:
        import subprocess
        from agents.utils.subprocess_utils import get_subprocess_flags
        
        subprocess.Popen(
            ["python", "script.py"],
            creationflags=get_subprocess_flags(),
            ...
        )
    """
    if sys.platform == "win32":
        # CREATE_NO_WINDOW = 0x08000000
        # Prevents console window from appearing
        return 0x08000000
    return 0


def run_hidden(cmd, **kwargs):
    """
    Run a subprocess without showing a console window on Windows.
    
    Args:
        cmd: Command to run (list or string)
        **kwargs: Additional arguments passed to subprocess.run()
    
    Returns:
        subprocess.CompletedProcess
    
    Example:
        result = run_hidden(["python", "worker.py"], capture_output=True)
    """
    if sys.platform == "win32":
        # Suppress console window on Windows
        creationflags = kwargs.pop("creationflags", 0)
        creationflags |= 0x08000000  # CREATE_NO_WINDOW
        kwargs["creationflags"] = creationflags
    
    return subprocess.run(cmd, **kwargs)


def Popen_hidden(cmd, **kwargs):
    """
    Create a Popen subprocess without showing a console window on Windows.
    
    Args:
        cmd: Command to run (list or string)
        **kwargs: Additional arguments passed to subprocess.Popen()
    
    Returns:
        subprocess.Popen instance
    
    Example:
        proc = Popen_hidden(["python", "daemon.py"], stdout=subprocess.PIPE)
    """
    if sys.platform == "win32":
        # Suppress console window on Windows
        creationflags = kwargs.pop("creationflags", 0)
        creationflags |= 0x08000000  # CREATE_NO_WINDOW
        kwargs["creationflags"] = creationflags
    
    return subprocess.Popen(cmd, **kwargs)
