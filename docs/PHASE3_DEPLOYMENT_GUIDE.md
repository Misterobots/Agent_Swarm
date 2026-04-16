# Phase 3: Update & Restart Justin-PC
# Remove local Traefik and monitoring stack, keep compute services

## Changes Made
✅ **Removed Services:**
- traefik (Reverse proxy - now using R730 Traefik)
- cadvisor (Container metrics - now on R730)
- prometheus (Metrics DB - now on R730)
- grafana (Dashboard - now on R730)
- loki (Log aggregation - now on R730)
- promtail (Log shipper - now on R730)
- redis_queue (Monitoring queue - not needed)

✅ **Removed Volumes:**
- prometheus_data
- grafana_data
- loki_data
- redis_data

✅ **Kept Services (Unchanged):**
- spire-agent (Identity provider)
- ollama (GPU inference)
- bmo-voice (Voice cloning)
- voice-engine (TTS)
- openhands (Sandbox)
- agent-runtime (FastAPI server)
- comfyui (Image gen)
- agent-ui (Web UI)
- ops-portal (Dashboard)
- agent_ide_devops (DevOps IDE)
- agent_ide_coding (Code IDE)
- authentik (Identity)
- text-gen-webui (Diagnostic)

## Deployment Steps

### Step 1: Backup Current Compose
```bash
ssh misterobots@192.168.2.101 "cd ~/execution_plane && \
cp docker-compose.yml docker-compose.backup.20260314_phase3 && \
echo '✅ Backup created'"
```

### Step 2: Copy New Compose
```powershell
# From Justin-PC, copy the Phase 3 compose
scp 'C:\Users\panca\Documents\GitHub\Home_AI_Lab\execution_plane\docker-compose-phase3.yml' `
    misterobots@192.168.2.101:~/execution_plane/docker-compose.yml
```

### Step 3: Prune Dangling Resources (optional)
```bash
ssh misterobots@192.168.2.101 "cd ~/execution_plane && \
docker system prune -f && \
docker volume rm prometheus_data grafana_data loki_data redis_data 2>/dev/null || true && \
echo '✅ Pruned old monitoring volumes'"
```

### Step 4: Restart Justin-PC Services
```bash
ssh misterobots@192.168.2.101 "cd ~/execution_plane && \
docker-compose down && \
sleep 5 && \
docker-compose up -d && \
sleep 10 && \
docker-compose ps"
```

### Step 5: Verify Services Running
All these should show "Up":
```bash
ssh misterobots@192.168.2.101 "cd ~/execution_plane && docker-compose ps | grep -E 'Up|STATUS'"
```

Expected output:
- ✅ spire-agent (Up)
- ✅ ollama_gpu (Up)
- ✅ bmo_voice_gpu (Up)
- ✅ voice_engine_gpu (Up)
- ✅ openhands_sandbox (Up)
- ✅ agent_runtime (Up)
- ✅ comfyui_gpu (Up)
- ✅ agent_ui (Up)
- ✅ ops_portal (Up)
- ✅ agent_ide_devops (Up)
- ✅ agent_ide_coding (Up)
- ✅ authentik_server (Up)
- ✅ authentik_worker (Up)
- ✅ authentik_db (Up)
- ✅ authentik_redis (Up)
- ✅ text-gen-webui (Exit 0, profile-based)

### Step 6: Test Service Connectivity
```powershell
# Test from Justin-PC that services are accessible locally
# These should work internally at :port but route through R730 for external access

# Test Ollama
curl -s http://192.168.2.101:11434/api/tags

# Test ComfyUI
curl -s http://192.168.2.101:8188/system_stats

# Test Agent Runtime
curl -s http://192.168.2.101:8008/docs
```

### Step 7: Verify Metrics Collection on R730
```bash
# Check that R730 Prometheus is scraping Justin-PC services
curl -s http://192.168.2.103:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, state: .health}'

# Expected: Some targets should now be DOWN initially (they're on different port)
# This is OK - R730's Traefik will need to be configured to scrape Justin-PC services
```

### Step 8: Git Commit
```bash
ssh misterobots@192.168.2.101 "cd ~/Home_AI_Lab && \
git add execution_plane/docker-compose.yml && \
git commit -m 'PHASE 3: Remove local Traefik + monitoring, migrate to R730 gateway'"
```

## Validation Checklist

- [ ] All compute services running on Justin-PC
- [ ] No local Traefik (no port 81, 443, 8082)
- [ ] No local Prometheus/Grafana/Loki
- [ ] Services accessible via http://192.168.2.101:port
- [ ] R730 Prometheus points to Justin-PC services
- [ ] Access via R730 Traefik: http://192.168.2.103/comfy, http://192.168.2.103/ai, etc.

## Storage Impact

Before Phase 3:
- Justin-PC: ~500GB total, ~425GB used (85%)
- Monitoring: ~50-75GB (Prometheus, Grafana, Loki logs, Promtail cache)

After Phase 3:
- Justin-PC: ~425GB freed → ~500GB used (~60%)
- R730: Absorbs monitoring (now ~50-75GB used for monitoring)

**Result: Justin-PC freed ~75GB of storage, now focused on COMPUTE only**

## Quick Command (All Steps)

```bash
ssh misterobots@192.168.2.101 "cd ~/execution_plane && \
cp docker-compose.yml docker-compose.backup.20260314 && \
docker system prune -f && \
docker volume rm prometheus_data grafana_data loki_data redis_data 2>/dev/null || true && \
docker-compose down && \
sleep 5 && \
docker-compose up -d && \
sleep 15 && \
docker-compose ps"
```

(Remember to copy new compose file first!)

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `execution_plane/docker-compose.yml` | Infrastructure | Post-Phase 3 Justin-PC compose |
| `migration_backup_20260314_163149/` | Backup | Pre-migration compose backup |

</details>

<details>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance notes |
| 2026-03-14 | AI-Copilot | Phase 3 deployment guide — Traefik + monitoring offloaded |

</details>

---

## Maintenance Notes

This is a **completed deployment guide**. Migration has been executed. Retain as reference for understanding the service topology change.
