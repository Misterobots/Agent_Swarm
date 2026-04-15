---
title: Deploy Execution Plane
---

# Deploy Execution Plane

The Execution Plane (Justin-PC, {{ execution_node_ip }}) runs all GPU compute: Ollama, Agent Runtime, ComfyUI, Voice Engine, and sandboxed code execution.

## Services

| Service | Port | GPU | Purpose |
|---------|------|-----|---------|
| Ollama | {{ ollama_port }} | ✅ | LLM inference |
| Agent Runtime | {{ agent_runtime_port }} | — | FastAPI agent orchestrator |
| ComfyUI | 8188 | ✅ | Image generation pipelines |
| Voice Engine | 5050 | ✅ | TTS (Qwen3-TTS + RVC) |
| BMO Voice | 5060 | ✅ | Character voice assistant |
| OpenHands | 3300 | — | Sandboxed code execution |
| SPIRE Agent | — | — | Workload identity |

## Steps

### 1. Prepare the Node

```powershell
cd C:\Users\panca\Documents\Github\Agent_Swarm
git pull origin main
```

Ensure Docker Desktop is running with WSL 2 backend and GPU support enabled.

### 2. Verify GPU Access

```powershell
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

### 3. Pull Models

```powershell
# Start Ollama first
docker compose -f execution_plane/docker-compose.yml up -d ollama

# Pull required models
docker exec ollama ollama pull {{ solver_model }}
docker exec ollama ollama pull {{ router_model }}
docker exec ollama ollama pull {{ verifier_model }}
docker exec ollama ollama pull moondream:latest
```

!!! info "Model Download"
    Initial model pulls may take 10–30 minutes depending on bandwidth. Models are cached in the Ollama Docker volume.

### 4. Configure SPIRE Agent

Set the join token from the Control Plane deployment:

```powershell
# Edit the agent configuration
notepad execution_plane\config\spire\agent.conf
```

Update `join_token` with the token generated during Control Plane setup.

### 5. Start All Services

```powershell
cd execution_plane
docker compose --env-file ..\network.env up -d
```

### 6. Verify Services

```powershell
# Agent Runtime health
curl http://localhost:{{ agent_runtime_port }}/

# Ollama models loaded
curl http://localhost:{{ ollama_port }}/api/tags | python -m json.tool

# ComfyUI
curl http://localhost:8188/system_stats

# SPIRE agent health
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck
```

### 7. Ollama Configuration

Key Ollama environment variables in `docker-compose.yml`:

| Variable | Recommended | Description |
|----------|-------------|-------------|
| `OLLAMA_NUM_PARALLEL` | 2 | Max concurrent requests |
| `OLLAMA_MAX_LOADED_MODELS` | 3 | Max models in VRAM |
| `OLLAMA_KEEP_ALIVE` | 10m | Idle model unload time |
| `OLLAMA_FLASH_ATTENTION` | 1 | Enable Flash Attention |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `nvidia-smi` not found | Install/update NVIDIA drivers |
| `docker: Error response from daemon: could not select device driver` | Install NVIDIA Container Toolkit |
| Ollama OOM | Reduce `OLLAMA_MAX_LOADED_MODELS`, or pull smaller quant |
| Agent Runtime can't reach Ollama | Check `OLLAMA_HOST` in network.env |
| SPIRE agent attestation failed | Regenerate join token from Control Plane |

## Next

→ [Deploy Gateway](gateway.md)
