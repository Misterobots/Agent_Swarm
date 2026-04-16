# execution_plane/docker-compose.yml (AFTER MIGRATION)
# 
# This is the REFERENCE structure for Justin-PC after moving Traefik + monitoring to R730.
# Only compute/inference services remain on Justin-PC.
#
# Original full config remains in execution_plane/docker-compose.yml
# To apply this, remove the deleted services section by  section from your current compose file.
#
# SERVICES REMOVED FROM JUSTIN-PC:
#   - traefik (→ moved to R730)
#   - prometheus (→ moved to R730)
#   - grafana (→ moved to R730)
#   - loki (→ moved to R730)
#   - promtail (→ moved to R730)
#   - cadvisor (→ moved to R730)
#   - redis_queue (→ moved to R730)
#
# SERVICES REMAINING ON JUSTIN-PC:
#   ✓ spire-agent (identity)
#   ✓ ollama (primary inference)
#   ✓ bmo-voice (RVC voice)
#   ✓ voice-engine (TTS)
#   ✓ openhands (sandbox)
#   ✓ agent-runtime (FastAPI core)
#   ✓ comfyui (generative)

version: '3.8'

services:
  # IDENTITY PROVIDER
  spire-agent:
    image: ghcr.io/spiffe/spire-agent:1.10.1
    container_name: spire-agent
    hostname: spire-agent
    # ... keep existing config ...

  # PRIMARY INFERENCE ENGINE
  ollama:
    image: ollama/ollama:latest
    container_name: ollama_gpu
    # ... keep existing config ...
    # NOTE: This is the primary (heavy) inference engine for Justin-PC
    # All inference requests should prefer this over R730

  # VOICE SYNTHESIS & GENERATION
  bmo-voice:
    build:
      context: ../agents/bmo_voice
      dockerfile: Dockerfile
    container_name: bmo_voice_gpu
    # ... keep existing config ...
    # NOTE: Runs at Home Assistant's voice cadence
    # GPU time-shared with ComfyUI (ComfyUI unloads on demand)

  voice-engine:
    build:
      context: ../services/voice_engine
      dockerfile: Dockerfile
    container_name: voice_engine_gpu
    # ... keep existing config ...

  # SANDBOX DEVELOPMENT
  openhands:
    build:
      context: .
      dockerfile: Dockerfile.openhands
    image: custom-openhands:latest
    container_name: openhands_sandbox
    # ... keep existing config ...

  # CORE INFERENCE SERVICE
  agent-runtime:
    build:
      context: ..
      dockerfile: execution_plane/Dockerfile
    image: home-ai-lab/agent-runtime:latest
    container_name: agent_runtime
    restart: always
    depends_on:
      - ollama
      - openhands
      - comfyui
      - spire-agent
    environment:
      # ... existing config ...
      # NOTE: Now routes metrics/logs to R730 instead of local stack
      - METRICS_ENDPOINT=http://192.168.2.103:9090  # Prometheus on R730
      - LOGS_ENDPOINT=http://192.168.2.103:3100     # Loki on R730
    labels:
      # CRITICAL: These labels enable Traefik on R730 to route requests to this service
      - "traefik.enable=true"
      - "traefik.http.routers.agent-runtime.rule=PathPrefix(`/swarm`)"
      - "traefik.http.routers.agent-runtime.entrypoints=web"
      - "traefik.http.services.agent-runtime.loadbalancer.server.port=8000"
    # ... rest of config ...

  # GENERATIVE WORKLOADS
  comfyui:
    image: yanwk/comfyui-boot:cu121
    container_name: comfyui_gpu
    hostname: comfyui
    # ... keep existing config ...
    labels:
      # CRITICAL: These labels enable Traefik on R730 to route requests to this service
      - "traefik.enable=true"
      - "traefik.http.routers.comfyui.rule=PathPrefix(`/comfy`)"
      - "traefik.http.routers.comfyui.entrypoints=web"
      - "traefik.http.services.comfyui.loadbalancer.server.port=8188"
    # ... rest of config ...

# ═══════════════════════════════════════════════════════════════════════════════
# VOLUMES (MONITORING VOLUMES REMOVED)
# ═══════════════════════════════════════════════════════════════════════════════
# DELETED VOLUMES:
#   ✗ prometheus_data (→ moved to R730)
#   ✗ grafana_data (→ moved to R730)
#   ✗ loki_data (→ moved to R730)
#   ✗ redis_data (→ moved to R730)

volumes:
  ollama_models: {}
  bmo_models: {}
  # ... keep other non-monitoring volumes ...

networks:
  execution_net:
    driver: bridge

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `execution_plane/docker-compose.yml` | Infrastructure | Actual compose file for Justin-PC |
| `network.env` | Configuration | Node IPs, environment variables |

</details>

<details>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide |
| 2026-03-14 | AI-Copilot | Post-migration compose reference (monitoring offloaded to R730) |

</details>

---

## Maintenance & Update Guide

- Update when services are added or removed from Justin-PC.
- Cross-reference with `execution_plane/docker-compose.yml` to ensure this reference matches reality.
- Update volume list when new persistent storage is added.
