---
title: "Tool: Terminal"
---

# Terminal Tool

Execute shell commands in a sandboxed environment.

## Functions

| Function | Description |
|----------|-------------|
| `run_command(cmd)` | Execute a shell command |
| `run_script(path)` | Execute a script file |

## Security

- Only accessible with `terminal` in JWT-ACE token
- Commands checked against the blocklist before execution
- Blocked commands trigger governance requests
- All executions logged with command, exit code, and output

### Blocked Commands

Dangerous patterns are intercepted:

- `rm -rf /`, `mkfs`, `dd if=/dev/zero` — filesystem destruction
- `curl | bash`, `wget | sh` — arbitrary code download
- `chmod 777` — permission weakening

## Allowed Intents

`CODE`, `DEVOPS`, `COORDINATE`
