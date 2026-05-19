# Hive Architecture Interaction Map

> **Purpose:** Comprehensive reference for understanding network topology, service interactions, API routing, dependencies, and troubleshooting procedures across the entire Hive multi-node architecture.  
> **Last Updated:** May 3, 2026  
> **Target Audience:** AI agents, developers, operators, and troubleshooters

---

## Table of Contents
1. [Network Topology](#1-network-topology)
2. [Pioneer Node Inventory](#2-pioneer-node-inventory)
3. [Service Port Mapping](#3-service-port-mapping)
4. [Docker Networks & Routing](#4-docker-networks--routing)
5. [API Routing Architecture](#5-api-routing-architecture)
6. [Service Dependencies & Data Flow](#6-service-dependencies--data-flow)
7. [Health Check Endpoints](#7-health-check-endpoints)
8. [Authentication & Authorization Flow](#8-authentication--authorization-flow)
9. [GPU Inference Routing](#9-gpu-inference-routing)
10. [Observability Stack](#10-observability-stack)
11. [Common Failure Scenarios](#11-common-failure-scenarios)
12. [Troubleshooting Procedures](#12-troubleshooting-procedures)
13. [Quick Reference Commands](#13-quick-reference-commands)

---

## 1. Network Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LAN: 192.168.2.0/24                                │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ├── 192.168.2.100  Home Assistant (external system)
         ├── 192.168.2.101  Lovelace (LOCAL PC - GPU Compute Node)
         ├── 192.168.2.102  Hopper (Control Plane - Database/Cache)
         ├── 192.168.2.103  Turing (Gateway - Routing/Monitoring)
         ├── 192.168.2.104  iDRAC (server management)
         └── 192.168.2.106  BMO (Raspberry Pi - Voice/IoT)

┌──────────────────────────────────────────────────────────────────────────────┐
│                         External DNS (Cloudflare)                            │
├──────────────────────────────────────────────────────────────────────────────┤
│  • hive.shivelymedia.com      → 192.168.2.103:443 (Turing Traefik)          │
│  • grafana.shivelymedia.com   → 192.168.2.103:443 (Turing Traefik)          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Network Segmentation
- **Production Network:** `ai_lab_net` (bridge, shared across Turing/Hopper services)
- **Saltbox Network:** `saltbox` (external, managed by Saltbox Traefik)
- **Execution Network:** `execution_net` (bridge, Lovelace local services)

---

## 2. Pioneer Node Inventory

### Lovelace (192.168.2.101) — **LOCAL MACHINE**
**Role:** GPU compute node, execution plane  
**Hardware:** Dual RTX 5060 Ti (32GB VRAM total), 64GB RAM  
**Repository Path:** `C:\Users\panca\Documents\Github\Agent_Swarm`  
**Access:** Direct (this machine, no SSH)

**Key Services:**
- **Ollama** (primary): Dual GPU MoE inference, qwen3:14b pinned
- **ComfyUI**: Image generation (FLUX, Stable Diffusion)
- **SPIRE Agent**: Workload identity
- **Voice Engine**: Qwen3-TTS (1.7B)
- **BMO Voice**: RVC inference
- **OpenHands**: Sandboxed execution

**Docker Compose:** `execution_plane/docker-compose.yml`

### Turing (192.168.2.103) — Gateway & Orchestration
**Role:** Traefik gateway, monitoring stack, secondary inference  
**Hardware:** RTX 3070 Ti (8GB VRAM)  
**Repository Path:** `/home/misterobots/Home_AI_Lab`  
**SSH Access:** `C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.103`

**Key Services:**
- **Traefik**: Reverse proxy with Authentik SSO integration
- **agent_runtime** (FastAPI): Primary backend API
- **hive_ui** (Next.js): Frontend application
- **Prometheus**: Metrics aggregation
- **Loki**: Log aggregation
- **Grafana (Hollerith)**: Visualization
- **Ollama (secondary)**: Safety models (llama-guard-3:8b), embeddings (nomic-embed)
- **Redis**: Task queue and cache
- **SPIRE Agent**: Workload identity

**Docker Compose:** `turing_gateway/docker-compose.yml`  
**Container Naming:** Uses **underscores** (`agent_runtime`, `hive_ui`)  
**Service Naming:** Uses **hyphens** (`agent-runtime`, `hive-ui`)

### Hopper (192.168.2.102) — Control Plane
**Role:** Database, cache, observability backend  
**Repository Path:** `/home/misterobots/Agent_Swarm`  
**SSH Access:** `C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.102`

**Key Services:**
- **PostgreSQL**: Main database (agno_memory, langfuse schema)
- **Redis**: Session cache
- **Langfuse**: LLM observability
- **MemPalace**: Long-term memory API
- **SPIRE Server**: Root of trust for workload identity

**Ports:**
- 5432: PostgreSQL
- 6379: Redis
- 3000: Langfuse
- 8200: MemPalace API

### BMO (192.168.2.106) — Voice & IoT
**Role:** Voice assistant satellite, wakeword detection  
**Hardware:** Raspberry Pi  
**Repository Path:** `/home/misterobots/Home_AI_Lab`

**Key Services:**
- Wakeword daemon (always-on listener)
- Voice satellite proxy

---

## 3. Service Port Mapping

### Lovelace (192.168.2.101)
| Port  | Service          | Container Name   | Protocol | Access          |
|-------|------------------|------------------|----------|-----------------|
| 11434 | Ollama (primary) | ollama_gpu       | HTTP     | LAN-wide        |
| 8188  | ComfyUI          | comfyui_gpu      | HTTP     | LAN-wide        |
| 8100  | BMO Voice        | bmo_voice_gpu    | HTTP     | LAN-wide        |
| 8020  | Voice Engine     | voice_engine_gpu | HTTP     | LAN-wide        |
| 3002  | OpenHands        | openhands_sandbox| HTTP     | Local only      |

### Turing (192.168.2.103)
| Port  | Service            | Container Name          | Protocol | Access          |
|-------|--------------------|-------------------------|----------|-----------------|
| 80    | Traefik (HTTP)     | traefik                 | HTTP     | LAN + External  |
| 443   | Traefik (HTTPS)    | traefik                 | HTTPS    | External only   |
| 8080  | Traefik Dashboard  | traefik                 | HTTP     | Admin only      |
| 8008  | Agent Runtime API  | agent_runtime           | HTTP     | Docker network  |
| 3200  | Hive UI            | hive_ui                 | HTTP     | Docker network  |
| 11434 | Ollama (secondary) | ollama-turing           | HTTP     | Docker network  |
| 3000  | Open WebUI         | open-webui-turing       | HTTP     | Docker network  |
| 6379  | Redis              | redis-turing            | TCP      | Docker network  |
| 9091  | Prometheus         | prometheus-turing       | HTTP     | Docker network  |
| 3001  | Grafana (Hollerith)| hollerith-turing        | HTTP     | Docker network  |
| 3100  | Loki               | loki-turing             | HTTP     | Docker network  |
| 9093  | Alertmanager       | alertmanager-turing     | HTTP     | Docker network  |
| 9115  | Blackbox Exporter  | blackbox-exporter-turing| HTTP     | Docker network  |
| 8888  | cAdvisor           | cadvisor-turing         | HTTP     | Docker network  |
| 2375  | Docker Socket Proxy| docker-socket-proxy-turing | HTTP  | Docker network  |

### Hopper (192.168.2.102)
| Port  | Service     | Container Name | Protocol | Access         |
|-------|-------------|----------------|----------|----------------|
| 5432  | PostgreSQL  | postgres       | TCP      | LAN-wide       |
| 6379  | Redis       | redis          | TCP      | LAN-wide       |
| 3000  | Langfuse    | langfuse       | HTTP     | LAN-wide       |
| 8200  | MemPalace   | mempalace      | HTTP     | LAN-wide       |

---

## 4. Docker Networks & Routing

### Network Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Saltbox Network (external)                         │
│  Managed by Saltbox's Traefik — handles external HTTPS + Authentik SSO     │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ├── Traefik (gateway container)
                         │
┌────────────────────────┴────────────────────────────────────────────────────┐
│                          ai_lab_net (bridge)                                │
│  Primary internal network — agent_runtime, hive_ui, monitoring stack       │
├─────────────────────────────────────────────────────────────────────────────┤
│  • agent_runtime:8000     (FastAPI backend)                                 │
│  • hive_ui:3000           (Next.js frontend)                                │
│  • ollama:11434           (Turing Ollama)                                   │
│  • prometheus:9090                                                          │
│  • loki:3100                                                                │
│  • hollerith:3000         (Grafana)                                         │
│  • redis:6379                                                               │
│  • mempalace:8200         (via extra_hosts → Hopper IP)                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        execution_net (bridge, Lovelace)                     │
│  Local compute services on Lovelace                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  • ollama_gpu:11434       (Primary Ollama with dual 5060 Ti)               │
│  • comfyui_gpu:8188                                                         │
│  • bmo_voice_gpu:8000                                                       │
│  • voice_engine_gpu:8020                                                    │
│  • openhands_sandbox:3000                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Network Communication
- **Turing → Lovelace Ollama**: `http://192.168.2.101:11434` (LAN, not Docker network)
- **Turing → Hopper Services**: Via `extra_hosts` mapping (`mempalace:192.168.2.102`)
- **Lovelace → Turing Services**: Direct LAN IP access (192.168.2.103)

---

## 5. API Routing Architecture

### External Request Flow (hive.shivelymedia.com)
```
User Browser
    │
    ├── HTTPS (443) → Cloudflare → Traefik (Turing:443)
    │                                  │
    │                                  ├── TLS Termination
    │                                  ├── Authentik SSO Check
    │                                  │
    ├─────────────────────────────────┴─→ hive_ui:3000 (Next.js)
    │                                       │
    │                                       ├── Static Pages (rendered)
    │                                       ├── /api/backend/[...path] (Next.js API Route)
    │                                       │   │
    │                                       │   └─→ Proxies to agent_runtime:8000
    │                                       │
    │                                       └── Client-side fetch("/api/backend/v1/...")
    │
    └─────────────────────────────────────────→ agent_runtime:8000
                                                   │
                                                   ├── /v1/chat/completions (SSE stream)
                                                   ├── /api/v1/identity
                                                   ├── /api/v1/task
                                                   ├── /api/v1/grounding/status
                                                   └── ... (full FastAPI endpoints)
```

### UI → Backend API Path Translation
| UI Request Path                     | Next.js Route            | Backend Target             |
|-------------------------------------|--------------------------|----------------------------|
| `/api/backend/v1/chat/completions`  | `/api/backend/[...path]` | `agent_runtime:8000/v1/chat/completions` |
| `/api/backend/v1/identity`          | `/api/backend/[...path]` | `agent_runtime:8000/api/v1/identity` |
| `/api/backend/v1/task`              | `/api/backend/[...path]` | `agent_runtime:8000/api/v1/task` |
| `/api/backend/v1/grounding/status`  | `/api/backend/[...path]` | `agent_runtime:8000/api/v1/grounding/status` |
| `/api/backend/v1/art/files/*`       | `/api/backend/[...path]` | `agent_runtime:8000/api/v1/art/files/*` |

**Key Implementation:** `ui/src/app/api/backend/[...path]/route.ts`  
- Strips `/api/backend` prefix  
- Forwards remaining path to `API_BASE_URL` (`http://agent_runtime:8000`)  
- Preserves headers, method, body  
- Streams SSE responses

### Traefik Routing Rules (Key Routes)
```yaml
# Hive UI (External HTTPS)
traefik.http.routers.hive-ext.rule=Host(`hive.shivelymedia.com`)
traefik.http.routers.hive-ext.entrypoints=websecure
traefik.http.routers.hive-ext.middlewares=authentik@docker
traefik.http.routers.hive-ext.service=hive-ext
traefik.http.services.hive-ext.loadbalancer.server.port=3000

# Grafana (Direct iframe access, bypasses Next.js)
traefik.http.routers.grafana-hive.rule=Host(`hive.shivelymedia.com`) && PathPrefix(`/grafana`)
traefik.http.routers.grafana-hive.priority=30
traefik.http.routers.grafana-hive.service=grafana

# Prometheus (Internal LAN only)
traefik.http.routers.prometheus.rule=PathPrefix(`/prometheus`)
traefik.http.routers.prometheus.entrypoints=web

# Ollama (Internal API)
traefik.http.routers.ollama.rule=PathPrefix(`/ollama`)
traefik.http.services.ollama.loadbalancer.server.port=11434
```

---

## 6. Service Dependencies & Data Flow

### Startup Order (Critical Path)
```
1. PostgreSQL (Hopper) ─────┬─→ Langfuse (Hopper)
2. Redis (Hopper)           │
3. MemPalace (Hopper)       │
                            │
4. SPIRE Server (Hopper) ───┼─→ SPIRE Agent (Turing)
                            │   SPIRE Agent (Lovelace)
                            │
5. Ollama (Lovelace) ───────┼─→ agent_runtime (Turing)
6. Ollama (Turing)          │       │
7. ComfyUI (Lovelace) ──────┘       │
                                    │
8. hive_ui (Turing) ────────────────┘
                                    │
9. Traefik (Turing) ────────────────┘
```

### Data Flow: Image Generation Request
```
User: "Create a cyberpunk motorcycle"
    │
    ├─→ UI: POST /api/backend/v1/chat/completions
    │
    ├─→ Next.js: Proxy to agent_runtime:8000/v1/chat/completions
    │
    ├─→ agent_runtime: church.py (Art Director intent detection)
    │       │
    │       ├─→ Check for style/setting keywords
    │       ├─→ Emit clarification_request (if missing)
    │       │   OR
    │       └─→ Proceed to image generation
    │               │
    │               ├─→ GPUQueueManager.get_queue("comfyui")
    │               ├─→ Select Lovelace (192.168.2.101:8188)
    │               ├─→ POST http://192.168.2.101:8188/prompt
    │               │       │
    │               │       └─→ ComfyUI: Generate image (FLUX/SD)
    │               │               │
    │               │               └─→ Save to /tmp/comfyui_images/
    │               │
    │               ├─→ Copy to /workspace/delivered_artifacts/
    │               ├─→ Extract media_metadata
    │               └─→ Yield media_attachment event
    │
    └─→ UI: Render <MessageBubble> with image
```

### Data Flow: Conversation Memory Extraction
```
User sends message
    │
    ├─→ agent_runtime: /v1/chat/completions
    │       │
    │       ├─→ church.py: Generate response
    │       │
    │       └─→ Post-response: mempalace_extractor.py
    │               │
    │               ├─→ POST http://mempalace:8200/v1/extract
    │               │   (async, non-blocking)
    │               │       │
    │               │       └─→ MemPalace (Hopper:8200)
    │               │               │
    │               │               ├─→ Extract entities/relations
    │               │               └─→ Store in knowledge graph
    │               │
    │               └─→ Response continues to user (doesn't wait)
```

### Data Flow: LLM Inference Routing
```
Agent needs inference
    │
    ├─→ inference/node_router.py
    │       │
    │       ├─→ Check NodeHealthMonitor (30s cache)
    │       │       │
    │       │       ├─→ Primary: http://192.168.2.101:11434 (Lovelace)
    │       │       │   - Check /api/ps (loaded models)
    │       │       │   - Check /api/tags (available models)
    │       │       │
    │       │       └─→ Secondary: http://ollama:11434 (Turing)
    │       │
    │       ├─→ Model loaded in VRAM? → Use that node
    │       ├─→ Model on disk? → Route to node, trigger load
    │       └─→ Model missing? → Return error
    │
    └─→ POST {selected_host}/api/generate
            │
            └─→ Stream response back to agent
```

---

## 7. Health Check Endpoints

### Agent Runtime (agent_runtime:8000)
```bash
# Identity check (requires auth)
GET http://192.168.2.103:8008/api/v1/identity

# Node health (all Ollama nodes)
GET http://192.168.2.103:8008/api/v1/health/nodes

# MCP server health
GET http://192.168.2.103:8008/api/v1/mcp/health

# Grounding status
GET http://192.168.2.103:8008/api/v1/grounding/status
```

### Ollama Health
```bash
# Lovelace (primary)
GET http://192.168.2.101:11434/api/tags        # Available models
GET http://192.168.2.101:11434/api/ps          # Loaded models
GET http://192.168.2.101:11434/api/version     # Version info

# Turing (secondary)
GET http://192.168.2.103:11434/api/tags
GET http://192.168.2.103:11434/api/ps
```

### ComfyUI Health
```bash
# System stats
GET http://192.168.2.101:8188/system_stats

# Queue status
GET http://192.168.2.101:8188/queue

# History (recent generations)
GET http://192.168.2.101:8188/history
```

### Database Health (Hopper)
```bash
# PostgreSQL
psql -h 192.168.2.102 -U agno -d agno_memory -c "SELECT 1;"

# Redis
redis-cli -h 192.168.2.102 -a redisshively PING

# Langfuse
curl http://192.168.2.102:3000/api/public/health

# MemPalace
curl http://192.168.2.102:8200/health
```

### Monitoring Stack Health
```bash
# Prometheus targets
curl http://192.168.2.103:9091/api/v1/targets

# Loki ready
curl http://192.168.2.103:3100/ready

# Grafana health
curl http://192.168.2.103:3001/api/health

# Alertmanager status
curl http://192.168.2.103:9093/api/v1/status
```

### Docker Container Health
```bash
# Turing
ssh misterobots@192.168.2.103 "docker ps --filter health=unhealthy"

# Check specific container
ssh misterobots@192.168.2.103 "docker inspect agent_runtime --format='{{.State.Health.Status}}'"
```

---

## 8. Authentication & Authorization Flow

### External Access (hive.shivelymedia.com)
```
1. User → https://hive.shivelymedia.com
2. Traefik → Check Authentik SSO cookie
3. No cookie? → Redirect to Authentik login
4. Valid cookie? → Forward to hive_ui:3000
5. hive_ui → Render page with user session
6. Browser fetch → /api/backend/v1/* (includes session cookie)
7. Next.js API route → Proxy to agent_runtime:8000
8. agent_runtime → Validate JWT (if present) or use API key
```

### Internal API Authentication
**Methods supported by agent_runtime:**
1. **JWT Token** (from Authentik via UI)
   - Extracted from `Authorization: Bearer <token>` header
   - Validated against public key
   - User identity extracted from claims

2. **API Key** (for service-to-service)
   - Hardcoded in `VALID_API_KEYS` env var
   - Format: `{"sk-coder-identity": "hive_ui"}`

3. **SPIRE Workload Identity** (future, via mTLS)
   - Containers issue SVID from SPIRE Agent
   - mTLS validation at service boundary

### Authorization Modes
- **Soft Mode** (default): Requests require approval via UI
- **Hard Mode**: Requests blocked unless explicitly allowed
- **Dev Auto-Approve**: Development convenience flag

**Grounding Control Endpoints:**
```bash
# Check current status
GET /api/v1/grounding/status

# Request grounding permission (as agent)
POST /api/v1/grounding/request
{
  "capability": "file_write",
  "reason": "Need to update config"
}

# Approve/deny (as admin)
POST /api/v1/request/{req_id}/status
{
  "status": "approved"  # or "denied"
}
```

---

## 9. GPU Inference Routing

### GPU Pool Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GPUQueueManager (Singleton)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Pools:                                                                     │
│    • "ollama"   → [Lovelace(pri), Turing(sec)]                             │
│    • "comfyui"  → [Lovelace]                                               │
│    • "bmo"      → [Lovelace]                                               │
│    • "voice"    → [Lovelace]                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Ollama Inference Routing Logic
**File:** `agents/inference/node_router.py`

1. **Check NodeHealthMonitor** (30s cache)
   - Ping `/api/tags` for availability
   - Ping `/api/ps` for loaded models

2. **Route Selection Priority:**
   ```
   IF model in Lovelace VRAM → Lovelace (instant, no load time)
   ELSE IF model in Turing VRAM → Turing
   ELSE IF model on Lovelace disk → Lovelace (trigger load)
   ELSE IF model on Turing disk → Turing (trigger load)
   ELSE → Error: Model not available
   ```

3. **Load Balancing:**
   - Primary model (qwen3:14b) pinned on Lovelace (`OLLAMA_KEEP_ALIVE=-1`)
   - Safety model (llama-guard-3:8b) pinned on Turing
   - Other models loaded on-demand

### GPU Capabilities by Node
| Node     | GPU               | VRAM  | Use Case                          |
|----------|-------------------|-------|-----------------------------------|
| Lovelace | 2× RTX 5060 Ti    | 32GB  | Primary inference, image gen      |
| Turing   | RTX 3070 Ti       | 8GB   | Safety models, embeddings         |

### Model Distribution Strategy
**Lovelace (32GB):**
- qwen3:14b (pinned, ~9GB)
- moondream (vision, on-demand)
- qwen2.5:3b (BMO voice, on-demand)
- Remaining VRAM for image generation

**Turing (8GB):**
- llama-guard-3:8b (safety, pinned, ~5GB)
- nomic-embed-text (embeddings, ~500MB)
- Small space for overflow

---

## 10. Observability Stack

### Metrics Collection (Prometheus)
**Scrape Targets:**
- Ollama metrics: `http://192.168.2.101:11434/metrics`, `http://ollama:11434/metrics`
- cAdvisor: `http://cadvisor:8080/metrics`
- Node Exporter (if running): `http://host.docker.internal:9100/metrics`
- Blackbox Exporter: `http://blackbox-exporter:9115/metrics`
- Agent Runtime: `http://agent_runtime:8000/metrics` (if implemented)

**Retention:** 90 days

### Log Aggregation (Loki)
**Log Sources:**
- Docker containers (via Promtail)
- Scrape config: `/var/lib/docker/containers/*/*-json.log`
- Labels: container_name, compose_project, host

**Query Examples:**
```logql
# Agent runtime errors
{container_name="agent_runtime"} |= "ERROR"

# Image generation logs
{container_name="agent_runtime"} |= "CreativeStudio" or "image_gen"

# SSE event debugging
{container_name="agent_runtime"} |= "media_attachment" or "clarification_request"
```

### Visualization (Grafana)
**Access:** https://hive.shivelymedia.com/grafana or http://192.168.2.103:3001/grafana

**Key Dashboards:**
- **Hive Overview**: Node health, request rates, error rates
- **GPU Utilization**: VRAM usage, model load times, inference latency
- **Docker Containers**: CPU, memory, network per container
- **Traefik**: Request volume, response times, status codes
- **Agent Runtime**: Active sessions, message throughput, tool invocations

### Alerting (Alertmanager)
**Alert Channels:**
- Email: `Justin@shivelymail.com`
- Ntfy: `home-ai-alerts` topic

**Active Alerts:**
- Ollama node down > 5 minutes
- agent_runtime container down
- PostgreSQL connection failures
- Disk usage > 85%
- VRAM exhaustion on any GPU

---

## 11. Common Failure Scenarios

### Scenario 1: "Images Not Appearing in Chat"
**Symptoms:**
- ComfyUI generates image successfully (visible in ComfyUI history)
- Backend logs show "Generated Image" message
- UI chat doesn't display image

**Root Causes:**
1. `media_attachment` event not emitted by church.py
2. Event type not forwarded by main.py SSE handler
3. File path mismatch (image not copied to delivered_artifacts)
4. UI SSE parser not handling `media_attachment` event

**Fix:**
```python
# In church.py (line ~2370)
yield {
    "type": "media_attachment",  # NOT "artifact"
    "content": media_meta
}

# In main.py (line ~1175)
if chunk.get("type") in [..., "media_attachment"]:  # Add to list

# In sse-parser.ts (line ~190)
case "media_attachment":
  parsed.type = "media_attachment";
  // Parse media_meta structure
```

### Scenario 2: "Clarification Card Not Rendering"
**Symptoms:**
- Art Director emits `clarification_request`
- Purple card doesn't appear in UI

**Root Causes:**
1. SSE event type not in main.py forwarding allowlist
2. `ClarificationCard` render logic inside `message.content ?` conditional
3. Event parsed but not added to message state

**Fix:**
```typescript
// In message-bubble.tsx
// Move ClarificationCard outside content conditional
{message.pendingClarification ? (
  <ClarificationCard ... />
) : message.content ? (
  <ReactMarkdown ... />
) : (
  <BlinkingCaret />
)}
```

### Scenario 3: "Ollama Model Not Loading"
**Symptoms:**
- Request fails with "Model not available"
- Model is present on disk (`ollama list` shows it)

**Root Causes:**
1. Both nodes unhealthy (network issue)
2. Model name mismatch (tag variation)
3. VRAM exhausted on target node
4. Ollama service crashed

**Diagnostic Steps:**
```bash
# Check node health
curl http://192.168.2.101:11434/api/tags
curl http://192.168.2.103:11434/api/tags

# Check loaded models
curl http://192.168.2.101:11434/api/ps

# Check VRAM usage (from Lovelace)
docker exec ollama_gpu nvidia-smi

# Check Ollama logs (Turing)
ssh misterobots@192.168.2.103 "docker logs ollama-turing --tail 50"
```

### Scenario 4: "hive_ui Build Failure"
**Symptoms:**
- `docker compose build hive-ui` fails with TypeScript errors
- Syntax errors in TSX files

**Root Causes:**
1. File sync incomplete (wrong file version on Turing)
2. Dependency version mismatch
3. Cached node_modules with stale types

**Fix:**
```bash
# Re-sync corrected files
scp -r ui/src/ misterobots@192.168.2.103:~/Home_AI_Lab/ui/

# Force rebuild without cache
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab/turing_gateway && \
   docker compose build --no-cache hive-ui && \
   docker compose up -d hive-ui"
```

### Scenario 5: "agent_runtime Can't Reach MemPalace"
**Symptoms:**
- Memory extraction requests timeout
- Logs show "Connection refused" to mempalace:8200

**Root Causes:**
1. MemPalace container down on Hopper
2. `extra_hosts` mapping missing in docker-compose.yml
3. Firewall blocking port 8200 between nodes

**Diagnostic Steps:**
```bash
# From Turing container
docker exec agent_runtime curl http://mempalace:8200/health

# Check Hopper MemPalace status
ssh misterobots@192.168.2.102 "docker ps | grep mempalace"

# Test direct IP access
docker exec agent_runtime curl http://192.168.2.102:8200/health

# Verify extra_hosts in compose file
grep -A5 "extra_hosts:" turing_gateway/docker-compose.yml
```

### Scenario 6: "Traefik 502 Bad Gateway"
**Symptoms:**
- External access to hive.shivelymedia.com returns 502
- Internal LAN access works fine (http://192.168.2.103:3200)

**Root Causes:**
1. hive_ui container down or unhealthy
2. Traefik lost connection to `saltbox` network
3. Authentik middleware blocking valid requests
4. Port mismatch in Traefik labels (should be 3000, not 3200)

**Diagnostic Steps:**
```bash
# Check hive_ui health
ssh misterobots@192.168.2.103 "docker inspect hive_ui --format='{{.State.Health.Status}}'"

# Check Traefik logs
ssh misterobots@192.168.2.103 "docker logs traefik --tail 100 | grep hive"

# Restart Traefik
ssh misterobots@192.168.2.103 "docker restart traefik"

# Test internal routing
curl -H "Host: hive.shivelymedia.com" http://192.168.2.103/chat
```

---

## 12. Troubleshooting Procedures

### Procedure 1: Full Stack Health Check
```bash
# === HOPPER (Control Plane) ===
ssh misterobots@192.168.2.102 "docker ps"
# Expected: postgres, redis, langfuse, mempalace running

ssh misterobots@192.168.2.102 "psql -h localhost -U agno -d agno_memory -c 'SELECT 1;'"
# Expected: "1" output

curl http://192.168.2.102:8200/health
# Expected: 200 OK

# === TURING (Gateway) ===
ssh misterobots@192.168.2.103 "docker ps"
# Expected: traefik, agent_runtime, hive_ui, ollama-turing, etc.

curl http://192.168.2.103:8008/api/v1/identity \
  -H "Authorization: Bearer test-token"
# Expected: 401 (service is responding)

curl http://192.168.2.103:8008/api/v1/health/nodes
# Expected: JSON array of Ollama nodes

# === LOVELACE (Compute) ===
docker ps --filter name=ollama_gpu
# Expected: ollama_gpu running

curl http://localhost:11434/api/tags
# Expected: JSON list of available models

curl http://localhost:8188/system_stats
# Expected: ComfyUI system stats
```

### Procedure 2: Restart Service Cascade
```bash
# Order matters — restart from control plane up to gateway

# 1. Restart Hopper services (if needed)
ssh misterobots@192.168.2.102 "cd ~/Agent_Swarm && docker compose restart"

# 2. Restart Lovelace compute services
cd C:\Users\panca\Documents\Github\Agent_Swarm\execution_plane
docker compose restart

# 3. Restart Turing backend
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab/turing_gateway && docker compose restart agent-runtime"

# 4. Restart Turing UI
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab/turing_gateway && docker compose restart hive-ui"

# 5. Restart Traefik (last, minimizes downtime)
ssh misterobots@192.168.2.103 "docker restart traefik"
```

### Procedure 3: Deploy Code Changes
```bash
# === DEPLOY AGENT RUNTIME CHANGES (Python only, no rebuild) ===
# Changes in agents/ folder take effect after restart
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab/turing_gateway && docker compose restart agent-runtime"

# === DEPLOY UI CHANGES (requires rebuild) ===
# 1. Sync changed files
scp -r ui/src/ misterobots@192.168.2.103:~/Home_AI_Lab/ui/

# 2. Rebuild and restart
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab/turing_gateway && \
   docker compose build hive-ui && \
   docker compose up -d hive-ui"

# === DEPLOY AGENT RUNTIME WITH NEW DEPENDENCIES ===
# 1. Update requirements in Home_AI_Lab repo on Turing
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab && git pull origin main"

# 2. Rebuild from parent directory (for correct build context)
ssh misterobots@192.168.2.103 \
  "cd ~/Home_AI_Lab && \
   docker build -f execution_plane/Dockerfile -t home-ai-lab/agent-runtime:latest . && \
   cd turing_gateway && \
   docker compose up -d agent-runtime"
```

### Procedure 4: Monitor Live Logs
```bash
# === AGENT RUNTIME (follow mode) ===
ssh misterobots@192.168.2.103 "docker logs agent_runtime --tail 0 --follow"

# === FILTER FOR SPECIFIC SUBSYSTEM ===
# Image generation
ssh misterobots@192.168.2.103 \
  "docker logs agent_runtime --tail 0 --follow | grep -i 'image\|comfy\|gpu'"

# Memory extraction
ssh misterobots@192.168.2.103 \
  "docker logs agent_runtime --tail 0 --follow | grep -i 'mempalace\|extract'"

# SSE streaming
ssh misterobots@192.168.2.103 \
  "docker logs agent_runtime --tail 0 --follow | grep -i 'sse\|stream\|yield'"

# === HIVE UI ===
ssh misterobots@192.168.2.103 "docker logs hive_ui --tail 100 --follow"

# === TRAEFIK ACCESS LOGS ===
ssh misterobots@192.168.2.103 "docker logs traefik --tail 100 --follow | grep '/api/backend'"

# === COMFYUI (Lovelace) ===
docker logs comfyui_gpu --tail 50 --follow
```

### Procedure 5: Test Image Generation End-to-End
```bash
# 1. Verify ComfyUI is reachable
curl http://192.168.2.101:8188/system_stats

# 2. Test direct ComfyUI prompt
curl -X POST http://192.168.2.101:8188/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": {
      "3": {
        "class_type": "KSampler",
        "inputs": {"model": "flux1-schnell-fp8.safetensors", ...}
      }
    }
  }'

# 3. Monitor agent_runtime logs
ssh misterobots@192.168.2.103 \
  "docker logs agent_runtime --tail 0 --follow | grep -E 'GPU|image_gen|CreativeStudio'"

# 4. Send test request via UI
# Visit https://hive.shivelymedia.com/chat
# Type: "create an image of a futuristic city"

# 5. Check delivered artifacts
ssh misterobots@192.168.2.103 "ls -lh /home/misterobots/Home_AI_Lab/delivered_artifacts/"
```

---

## 13. Quick Reference Commands

### SSH Shortcuts
```bash
# Turing
alias ssh-turing='C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.103'

# Hopper
alias ssh-hopper='C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.102'

# SCP from Lovelace to Turing
scp -r local/path/ misterobots@192.168.2.103:~/Home_AI_Lab/remote/path/
```

### Container Management
```bash
# View all containers across stack
ssh misterobots@192.168.2.103 "docker ps -a"

# Restart specific service
ssh misterobots@192.168.2.103 "cd ~/Home_AI_Lab/turing_gateway && docker compose restart agent-runtime"

# View container logs
ssh misterobots@192.168.2.103 "docker logs agent_runtime --tail 100"

# Execute command in container
ssh misterobots@192.168.2.103 "docker exec agent_runtime env | grep OLLAMA"
```

### Database Queries
```bash
# PostgreSQL (agno_memory)
ssh misterobots@192.168.2.102 \
  "psql -h localhost -U agno -d agno_memory -c 'SELECT COUNT(*) FROM conversations;'"

# Redis cache check
ssh misterobots@192.168.2.102 \
  "redis-cli -h localhost -a redisshively DBSIZE"
```

### Ollama Management
```bash
# List models (Lovelace)
docker exec ollama_gpu ollama list

# Check loaded models
curl http://192.168.2.101:11434/api/ps | jq

# Pull new model
docker exec ollama_gpu ollama pull qwen3:14b

# Stop model from VRAM
curl -X POST http://192.168.2.101:11434/api/generate \
  -d '{"model": "qwen3:14b", "keep_alive": 0}'
```

### Monitoring Queries
```bash
# Prometheus: Check target health
curl http://192.168.2.103:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Loki: Query recent logs
curl -G http://192.168.2.103:3100/loki/api/v1/query \
  --data-urlencode 'query={container_name="agent_runtime"}' \
  --data-urlencode 'limit=10' | jq
```

### Traefik Management
```bash
# List all routers
ssh misterobots@192.168.2.103 \
  "docker exec traefik wget -qO- http://localhost:8080/api/http/routers | jq"

# Check service backends
ssh misterobots@192.168.2.103 \
  "docker exec traefik wget -qO- http://localhost:8080/api/http/services | jq"
```

---

## Appendix A: Environment Variables Reference

### Critical Environment Variables (network.env)
```bash
# Node IPs
LOVELACE_IP=192.168.2.101
HOPPER_IP=192.168.2.102
TURING_IP=192.168.2.103
BMO_IP=192.168.2.106

# Database URLs
AGNO_DB_URL=postgresql://agno:agnoshively@192.168.2.102:5432/agno_memory
TEMPLATE_DB_URL=postgresql://langfuse:langfuseshively@192.168.2.102:5432/langfuse

# API Endpoints
LANGFUSE_HOST=http://192.168.2.102:3000
MEMPALACE_API_URL=http://192.168.2.102:8200
OLLAMA_HOST=http://localhost:11434
SECONDARY_OLLAMA_HOST=http://192.168.2.101:11434

# Auth Keys (Langfuse)
LANGFUSE_SECRET_KEY=sk-lf-2c33081c-c978-4d23-b830-f3b59c62eeb3
LANGFUSE_PUBLIC_KEY=pk-lf-6f6f8da6-8f82-4496-8e0d-39cf71fbad7d

# SPIRE Tokens
SPIRE_JOIN_TOKEN=13292491-01f6-46ca-afa8-4e321000f794
SPIRE_TURING_JOIN_TOKEN=a4ad893e-f01c-48ec-93c3-5dcf76ab4a4e

# Model Configuration
PRIMARY_MODEL=qwen3:14b
ROUTER_MODEL=qwen3:14b
COORDINATOR_MODEL=qwen3:14b
```

---

## Appendix B: File Path References

### Key Configuration Files
- **Turing Docker Compose:** `/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml`
- **Lovelace Docker Compose:** `C:\Users\panca\Documents\Github\Agent_Swarm\execution_plane\docker-compose.yml`
- **Network Config:** `C:\Users\panca\Documents\Github\Agent_Swarm\network.env`
- **Agent Runtime Main:** `/home/misterobots/Home_AI_Lab/agents/main.py`
- **Church (Art Director):** `/home/misterobots/Home_AI_Lab/agents/church.py`
- **Next.js Proxy Route:** `/home/misterobots/Home_AI_Lab/ui/src/app/api/backend/[...path]/route.ts`

### Important Data Directories
- **Ollama Models (Lovelace):** `/var/lib/docker/volumes/execution_plane_ollama_models/_data`
- **Ollama Models (Turing):** `/var/lib/docker/volumes/turing_gateway_ollama_models/_data`
- **ComfyUI Output:** `/tmp/comfyui_images/` (inside container)
- **Delivered Artifacts:** `/workspace/delivered_artifacts/` (mapped to repo root)
- **Grafana Data:** `/var/lib/docker/volumes/turing_gateway_grafana_data/_data`
- **Prometheus Data:** `/var/lib/docker/volumes/turing_gateway_prometheus_data/_data`

---

**Document Version:** 1.0  
**Maintenance Notes:** Update this document when:
- New services are added to the stack
- API endpoints change or are added
- Network topology changes (new nodes, IP reassignments)
- Major architectural refactoring occurs
- Common failure scenarios emerge from incident reports
