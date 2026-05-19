---
description: Pioneer node topology — defines which machine is local and how to reach remote nodes. Apply to all files so every AI agent session has correct context.
applyTo: "**"
---

## Pioneer Node Topology

**This VS Code session runs on Lovelace. Lovelace is the LOCAL machine. Never SSH into Lovelace — run commands directly in the terminal.**

| Pioneer  | IP            | Type          | Repo path                          | Key services                       |
|----------|---------------|---------------|------------------------------------|------------------------------------|
| Lovelace | 192.168.2.101 | **LOCAL PC**  | C:\Users\panca\OneDrive\Documents\GitHub\Agent_Swarm | Ollama (2× RTX 5060 Ti, 32 GB VRAM), ComfyUI |
| Turing   | 192.168.2.103 | Remote server | /home/misterobots/Home_AI_Lab      | agent_runtime, hive_ui, Traefik, Docker stack |
| Hopper   | 192.168.2.102 | Remote server | /home/misterobots/Agent_Swarm      | PostgreSQL, Redis, Langfuse, MemPalace |
| BMO      | 192.168.2.106 | Raspberry Pi  | /home/misterobots/Home_AI_Lab      | Voice/IoT, wakeword daemon         |

### SSH rules
- SSH user for all remote nodes: `misterobots`
- SSH binary on Windows is NOT in PATH: `C:\Windows\System32\OpenSSH\ssh.exe`
- PowerShell SSH pattern for remote commands:
  ```powershell
  $cmd = "your-command-here"
  Start-Process -FilePath "C:\Windows\System32\OpenSSH\ssh.exe" `
    -ArgumentList @("-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "misterobots@192.168.2.103", $cmd) `
    -NoNewWindow -Wait -RedirectStandardOutput "C:\Temp\out.txt" -PassThru | Out-Null
  Get-Content "C:\Temp\out.txt"
  ```
- Do **not** use `&&` in SSH commands — use `;` or `&&` inside a bash string passed as a single argument.

### Docker stack
- The compose file is on Turing: `/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml`
- Container names use **underscores**: `agent_runtime`, `hive_ui` (service names use hyphens: `agent-runtime`, `hive-ui`)
- `agent_runtime` mounts `../agents` as a volume — Python-only changes take effect after `docker restart agent_runtime` (no rebuild needed)
- UI changes require a Docker image rebuild: `docker compose build hive-ui && docker compose up -d hive-ui`

### Ollama endpoints
- `OLLAMA_HOST` (inside agent_runtime) = `http://ollama:11434` → Turing's 3070 Ti (8 GB VRAM)
- `SECONDARY_OLLAMA_HOST` = `http://192.168.2.101:11434` → Lovelace's dual 5060 Ti (32 GB VRAM)
- Lovelace Ollama is accessible from Turing over LAN; no SSH needed for inference calls
