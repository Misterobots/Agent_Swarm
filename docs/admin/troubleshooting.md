# Admin: Troubleshooting Guide

> **Back to:** [Documentation Index](../INDEX.md)
> **See also:** [Technical Reference](technical_reference.md) · [Security](security.md)

---

## Quick Diagnostic Commands

```bash
# Check running containers on each node
docker compose ps                              # from each node's compose directory

# Check Justin-PC from R730 (if SSH configured)
ssh panca@192.168.2.101 "cd ~/Home_AI_Lab/execution_plane && docker compose ps"

# Check Prometheus scrape targets (all should be UP)
curl http://192.168.2.103:9091/api/v1/targets | python -m json.tool

# Check agent runtime health
curl http://192.168.2.101:8008/api/v1/health/nodes

# Check Ollama models loaded
curl http://192.168.2.101:11434/api/ps
curl http://192.168.2.103:11434/api/ps
```

---

## 1. Agent Runtime / Swarm API

### "System Offline" in the UI

**Symptoms**: Sidebar shows red "System Offline". Chat requests hang or return errors.

**Checks**:
```bash
# On Justin-PC
cd execution_plane
docker compose ps agent-runtime
docker compose logs agent-runtime --tail=50

# From any machine
curl http://192.168.2.101:8008/  # Should return 200 or JSON
```

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| `agent-runtime` container crashed | `docker compose restart agent-runtime` |
| Missing `.env` variables (startup fail) | Check `docker compose logs agent-runtime` for missing var errors; update `.env` |
| Port 8008 not reachable from R730 | Check firewall/WSL2 network bridging; verify Traefik route to `192.168.2.101:8008` |
| Ollama not responding (`OLLAMA_HOST` unreachable) | Restart Ollama: `docker compose restart ollama` |
| SPIRE agent down (SVID fetch fail at startup) | `docker compose restart spire-agent`, then agent-runtime |

---

### Chat Returns Empty or "Solver Failed"

**Symptoms**: Response is empty, or you see "Solver failed: ..." in chat.

**Checks**:
```bash
# Check Ollama logs
docker compose logs ollama --tail=30

# Check which model is loaded
curl http://192.168.2.101:11434/api/ps

# Check if qwen3.5:9b is available
curl http://192.168.2.101:11434/api/tags | python -m json.tool
```

**Common causes**:

| Cause | Fix |
|-------|-----|
| `qwen3.5:9b` not pulled | `ollama pull qwen3.5:9b` (run inside ollama container or via API) |
| VRAM OOM — model evicted mid-request | Reduce `OLLAMA_KEEP_ALIVE`, restart Ollama |
| Training runtime holds GPU mutex | Wait for training to finish, or kill it: `docker compose stop training-runtime` |
| R730 Ollama used but `nemotron` not loaded | `docker exec ollama-r730 ollama pull nemotron-orchestrator:8b` |

---

### MarsRL Loop Hangs

**Symptoms**: Status shows "Solver is generating..." indefinitely.

**Checks**:
```bash
# Check Loki for stream timeout messages
# Grafana → GPU & Inference → MarsRL Loop Activity
# Or query directly:
curl -s 'http://192.168.2.103:3100/loki/api/v1/query_range?query=%7Bcontainer%3D%22agent_runtime%22%7D%20%7C~%20%22stream%20idle%22' | python -m json.tool
```

**Stream timeout** is logged when the Solver stream produces no tokens for 60 seconds. The loop breaks and returns what it has. This is usually a GPU memory pressure issue — reduce active models or restart Ollama.

---

## 2. Monitoring Stack (Grafana / Prometheus / Loki)

### Grafana Panels Show "No Data"

**Step 1**: Check the datasource. Open the panel editor and note which datasource it uses:
- `Prometheus` → check Prometheus targets
- `Loki` → check Loki query syntax (see below)
- `PostgreSQL-Swarm` → check DB connection + table existence

**Step 2: Prometheus panels**
```bash
# Check target status
curl http://192.168.2.103:9091/api/v1/targets 2>/dev/null | python -m json.tool | grep -A2 '"health"'

# Manually check a metric
curl 'http://192.168.2.103:9091/api/v1/query?query=agent_state' | python -m json.tool
```

If a target is `DOWN`, restart the affected container and verify its metrics port is reachable.

**Step 3: Loki panels**

The most common cause: **wrong label name**. Promtail labels containers as `container`, NOT `container_name`.

```
WRONG:  {container_name="agent_runtime"}
RIGHT:  {container="agent_runtime"}
```

Test a query directly:
```bash
curl -s 'http://192.168.2.103:3100/loki/api/v1/query?query=%7Bcontainer%3D%22agent_runtime%22%7D' | python -m json.tool
```

If Loki returns no streams, check Promtail is running and can reach the Docker socket:
```bash
docker compose ps promtail
docker compose logs promtail --tail=30
```

**Step 4: PostgreSQL-Swarm panels**

```bash
# Test connection from Grafana container
docker exec grafana-r730 psql postgresql://langfuse:langfuse@192.168.2.102:5432/langfuse \
  -c "SELECT COUNT(*) FROM swarm.performance_history"
```

If the table is empty, data hasn't been written yet. The `swarm.*` tables are populated by the agent runtime during normal usage. Run a few chat requests first.

---

### Prometheus "agent-runtime" Target Always DOWN

**Cause**: The agent runtime metrics path is `/metrics/` (trailing slash), not `/metrics`.

Verify the prometheus.yml scrape config:
```yaml
- job_name: 'agent-runtime'
  metrics_path: /metrics/   # ← must have trailing slash
  static_configs:
    - targets: ['192.168.2.101:8008']
```

Test: `curl http://192.168.2.101:8008/metrics/` — should return Prometheus text format.

---

### "cadvisor-justin" Target Shows No Container Name Labels

**Cause**: The cAdvisor proxy (`cadvisor_proxy` container) is not running on Justin-PC.

```bash
# On Justin-PC
docker compose ps cadvisor-proxy
docker compose logs cadvisor-proxy --tail=20
```

The proxy enriches raw cAdvisor metrics with container `name` labels by reading the Docker socket. Without it, container panels in Grafana will show hash IDs instead of readable names and may not match name-based filters.

---

## 3. SPIRE / SPIFFE Identity

### SPIRE Agent Won't Start

**Symptoms**: `docker compose logs spire-agent` shows connection errors to SPIRE server.

**Checks**:
```bash
# Verify SPIRE server on Wyse is running
curl http://192.168.2.102:8081/health

# Check join token hasn't expired
# If expired, generate a new one on Wyse:
docker exec spire-server spire-server token generate -spiffeID spiffe://home-ai-lab/agent/runtime
# Add new token to execution_plane/.env as SPIRE_JOIN_TOKEN=<token>
# Then restart: docker compose restart spire-agent
```

**One-time enrollment** (if workload entry is missing):
```bash
# Run on Wyse 5070
docker exec spire-server spire-server entry create \
  -spiffeID spiffe://home-ai-lab/agent/runtime \
  -parentID spiffe://home-ai-lab/agent/node \
  -selector docker:label:spiffe.io/spiffe-id:spiffe://home-ai-lab/agent/runtime
```

For full SPIRE setup procedures, see [`troubleshooting/spire-agent.md`](../troubleshooting/spire-agent.md).

---

### Agent Runtime Logs "SPIFFE SVID fetch failed"

**Impact**: Non-fatal in most configurations — the agent runtime continues with degraded mTLS.

**Fix**: Restart the SPIRE agent, then the agent runtime:
```bash
docker compose restart spire-agent
sleep 10
docker compose restart agent-runtime
```

If the issue persists after restart, the workload attestation entry may be out of date (e.g., after an image rebuild that changed the container SHA). Re-register the workload entry on the Wyse SPIRE server.

---

## 4. Training Pipeline

### Training Container Won't Start

**Checks**:
```bash
# Build the training image
docker compose --profile training build training-runtime

# Check build logs for errors
docker compose --profile training logs training-runtime
```

**Missing VRAM**: Training requires ~12.5GB. Verify ComfyUI and Ollama have released VRAM before starting:
```bash
# Force-unload all Ollama models
curl -X DELETE http://192.168.2.101:11434/api/delete  # or restart ollama

# Stop ComfyUI
docker compose stop comfyui
```

### Training Completes But Model Doesn't Appear in Ollama

```bash
# Check convert_gguf output
ls execution_plane/training_output/

# Check if Ollama has the model
curl http://192.168.2.101:11434/api/tags

# Manual import
docker exec ollama_gpu ollama import /path/to/output.gguf
```

### export_traces Returns 0 Records

**Cause**: No traces have `training_candidate = 1.0` score in Langfuse.

This means no responses scored above 0.80 in the quality threshold. Check:
1. Is the agent runtime actually writing to Langfuse? → `curl http://192.168.2.102:3210/api/health`
2. Are the `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` correct in the execution_plane `.env`?
3. View traces at `http://192.168.2.102:3000` — are any traces present?

---

## 5. Voice & BMO

### BMO Voice Not Responding

```bash
# Check containers
docker compose ps bmo-voice voice-engine

# Check logs
docker compose logs bmo-voice --tail=30
docker compose logs voice-engine --tail=30
```

**Common causes**:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `bmo-voice` exits immediately | GPU driver error | Restart container; check `nvidia-smi` on Justin-PC |
| Voice quality degraded | RVC model not loaded | Check `bmo-voice` logs for model load status |
| TTS produces silence | Qwen-TTS model not initialized | Restart `voice-engine`; check HuggingFace cache volume |
| Long TTS latency | `qwen2.5:3b` evicted from VRAM by other workloads | Set `BMO_LLM_MODEL` to a smaller model or increase `OLLAMA_KEEP_ALIVE` |

---

## 6. GPU Issues

### VRAM OOM / Container Killed

```bash
# Check current VRAM usage on Justin-PC
nvidia-smi

# Check which container is holding GPU
docker stats --no-stream
```

If training and inference are competing, the GPU mutex should handle this. If Redis is unavailable, the mutex fails open (both can run). To force release:
```bash
docker compose stop training-runtime comfyui
docker compose restart ollama
```

### nvidia-smi Not Available (WSL2)

Justin-PC runs on Windows with WSL2. GPU access requires:
1. NVIDIA driver installed on Windows host (≥535.x for CUDA 12.x)
2. WSL2 CUDA support enabled (`/usr/lib/wsl/lib/` must exist inside WSL2)
3. Docker Desktop with GPU support enabled

Check: `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi`

---

## 7. ComfyUI

### ComfyUI Returns 500 / Workflow Errors

ComfyUI patching is version-sensitive. The container applies a version-specific patch on first start (tracked by `.5060_patch_v10_applied` marker).

```bash
# Force re-patch (delete marker)
docker compose exec comfyui rm /home/runner/ComfyUI/.5060_patch_v10_applied
docker compose restart comfyui

# Watch patch logs
docker compose logs comfyui -f
```

### ComfyUI Outputs Not Visible in Agent Chat

The agent runtime mounts ComfyUI output at:
- Host: `C:/Users/panca/Documents/ComfyUI/ComfyUI/output`
- Container: `/app/comfy_io/output`

Check the volume mount is correct in `execution_plane/docker-compose.yml` and that the Windows path resolves inside WSL2.

---

## 8. Redis / GPU Mutex

### GPU Mutex Not Working (fail-open)

If both training and inference can run simultaneously, Redis connectivity is the issue.

```bash
# Test Redis on Wyse
redis-cli -h 192.168.2.102 -p 6379 -a <REDIS_PASSWORD> PING

# If Redis port not exposed, it must be added to Wyse docker-compose.yml:
# ports:
#   - "6379:6379"
# Then: sudo docker compose up -d redis
```

The `control_plane/docker-compose.yml` is root-owned on Wyse — edit requires `sudo` on the console.

---

## 9. Authentik SSO

### Services Show "Authentik Unauthorized"

```bash
# Check Authentik containers
docker compose ps authentik_server authentik_worker

# Check Authentik logs
docker compose logs authentik_server --tail=30
```

If Authentik is healthy but blocking, the provider configuration may need updating after a service URL change. Log in to `http://192.168.2.103:9000` as admin and verify the provider settings.

---

## 10. Useful Log Queries (Grafana Loki)

```logql
# All agent errors in last hour
{container="agent_runtime"} |~ "(?i)(error|exception|failed)" | json

# MarsRL quality issues
{container="agent_runtime"} |~ "(?i)(score|verifier|corrector|mars)"

# SPIRE authentication events
{container="agent_runtime"} |~ "(?i)(spiffe|svid|spire)"

# JWT-ACE events
{container="agent_runtime"} |~ "(?i)(jwt|capability|token|denied)"

# Training pipeline progress
{container="agent_runtime"} |~ "(?i)(training|grpo|qlora|export)"

# All container errors
{container=~".+"} |~ "(?i)(error|fatal|panic)" | json
```

---

*For security-related issues, see [Security](security.md) · [Back to Index](../INDEX.md)*
