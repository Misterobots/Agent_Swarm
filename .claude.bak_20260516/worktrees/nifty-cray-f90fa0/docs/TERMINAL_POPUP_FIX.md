# Terminal Popup Issue in Dev Mode - Fix Documentation

## Problem
When the swarm begins in dev mode, a terminal window pops up and cannot be collapsed/minimized. This is disruptive to the user experience.

## Root Cause
On Windows, subprocess creation without proper flags causes visible console windows to appear. This can happen when:
1. Python spawns subprocesses using `subprocess.Popen()` or `subprocess.run()`
2. PowerShell scripts use `Start-Process` without `-WindowStyle Hidden`
3. Docker containers with interactive TTY flags may trigger console behavior

## Solution

### 1. Python Subprocesses
Use the new utility in `agents/utils/subprocess_utils.py`:

```python
from agents.utils.subprocess_utils import run_hidden, Popen_hidden

# Instead of:
# subprocess.run(["python", "worker.py"])

# Use:
run_hidden(["python", "worker.py"], capture_output=True)

# For Popen:
# proc = subprocess.Popen(["python", "daemon.py"])
proc = Popen_hidden(["python", "daemon.py"], stdout=subprocess.PIPE)
```

### 2. PowerShell Scripts
Always use `-WindowStyle Hidden` for background processes:

```powershell
# Good:
$process = Start-Process -FilePath "python" `
    -ArgumentList $args `
    -WindowStyle Hidden `
    -PassThru

# Bad (creates visible window):
$process = Start-Process -FilePath "python" -ArgumentList $args
```

### 3. Docker Containers
Avoid using interactive TTY flags (`stdin_open: true`, `tty: true`) unless absolutely necessary:

```yaml
# Only use for containers that genuinely need interactive shells
dev-sandbox:
  stdin_open: true  # Required for terminal access
  tty: true         # Required for terminal colors/formatting
```

## Files to Update

### Confirmed Safe (Already Correct)
- ✅ `agents/launch_auto_repair.ps1` (line 113) - uses `-WindowStyle Hidden`
- ✅ `agents/daemon_registry.py` - uses `daemon=True` threads (no console)
- ✅ `agents/tools/terminal.py` - uses `docker exec` (no console)

### Need Review
- ⚠️ `launch_swarm.ps1` (lines 96-97) - uses `Start-Process` for browsers (may need `-WindowStyle Hidden`)
- ⚠️ Any custom scripts in `scripts/` directory
- ⚠️ Training workers (`agents/training/image_lora_worker.py` line 140) - uses `shell=True`

## Testing
1. Start the swarm in dev mode from Hive UI
2. Verify no console windows appear
3. Check Task Manager for hidden background processes
4. Confirm logs are still being written correctly

## References
- Windows subprocess flags: https://docs.python.org/3/library/subprocess.html#windows-constants
- PowerShell Start-Process: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process
- CREATE_NO_WINDOW = 0x08000000
