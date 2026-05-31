# Memex / Agent_Swarm — Session Primer

> **Read this first, every session.** This file is the authoritative reference for the home lab infrastructure, project layout, and workflow conventions. `topology.md` is outdated — ignore it.

---

## 🗺️ Network Map

| Host | IP | Role |
|------|----|------|
| **Home Assistant** | `192.168.2.100` | Home automation hub |
| **Lovelace** | `192.168.2.101` | Execution plane (GPU node #1, ComfyUI, Ollama, agent workers) |
| **Hopper** | `192.168.2.102` | Data plane (Postgres, Redis, Langfuse, MemPalace) |
| **Turing** | `192.168.2.103` | **Primary Memex host** (Traefik, memex_ui, agent_runtime, Cloudflare tunnel) |
| **BMO** | `192.168.2.106` | Voice / media node |

> ⚠️ **Common mistake:** Turing is `.103`, Lovelace is `.101`. The names look similar in env vars — always double-check before running commands.

---

## 🖥️ Turing (192.168.2.103) — Primary Host

| Service | Host Port | Notes |
|---------|-----------|-------|
| SSH | 22 | Key auth only; password auth fails with "Too many authentication failures" |
| HTTP (Traefik) | 80 | |
| HTTPS (Traefik) | 443 | wildcard cert via CF DNS (`*.shivelymedia.com`) |
| Docker API | **2375** | ⚠️ Unauthenticated — use when SSH unavailable |
| Ollama | 11434 | GPU-backed (primary model host) |
| `agent_runtime` | **8008** | Internal container port is 8000; host port is 8008 |
| `memex_ui` | **3200** | Internal container port is 3000; host port is 3200 |

**External URLs (via Cloudflare Tunnel → Traefik):**
- Memex UI: `https://memex.shivelymedia.com`
- Traefik dashboard: `https://dash.shivelymedia.com`
- Jellyfin: `https://jellyfin.shivelymedia.com`

**Docker networks on Turing:**
- `ai_lab_net` — `agent_runtime` + `memex_ui` (container-to-container via hostname)
- `saltbox` — `memex_ui` + `traefik` (Traefik routing)

**Key containers on Turing:**
```
agent_runtime     running   ai_lab_net
memex_ui          running   ai_lab_net + saltbox
traefik           running   saltbox
cloudflared       running   (CF tunnel daemon)
ollama-turing     running
redis-turing      running
authentik         running   (SSO)
```

**Traefik auth middleware:** `authentik@file` — requests to `memex.shivelymedia.com` go through Authentik SSO.

---

## ⚙️ Lovelace (192.168.2.101) — Execution Plane

| Service | Host Port | Notes |
|---------|-----------|-------|
| SSH | 22 | ❌ **Currently down** (connection refused) — use Docker API |
| Docker API | **2375** | ⚠️ Unauthenticated — primary management method |
| Ollama | 11434 | GPU-backed (secondary model host) |
| Open Design daemon | 7456 | OD v0.5.0; requires caller-supplied `id` UUID in POST /api/projects |
| Authentik | 9000 | SSO (same instance as Turing auth chain) |
| `agent_runtime` (prod) | **8008** | internal 8000 → host 8008 |
| `agent_runtime` (dev) | **8009** | internal 8000 → host 8009 |
| `hive_ui_local` (prod) | **3300** | internal 3000 → host 3300 |
| `hive_ui_dev` | **3301** | internal 3000 → host 3301 |

**Docker Compose project on Lovelace:** `execution_plane/docker-compose.yml`

---

## 🗄️ Hopper (192.168.2.102) — Data Plane

| Service | Port | Notes |
|---------|------|-------|
| Langfuse | 3000 | LLM tracing / observability |
| MemPalace | 8200 | Vector memory service |
| PostgreSQL | 5432 | `agno` DB (agent memory), `langfuse` DB |
| Redis | 6379 | Session state, GPU lock, pub/sub |

**Connection strings (from env):**
```
AGNO_DB_URL=postgresql://agno:...@192.168.2.102:5432/agno_memory
LANGFUSE_HOST=http://192.168.2.102:3000
MEMPALACE_API_URL=http://192.168.2.102:8200
REDIS_HOST=192.168.2.102
```

---

## 📂 Repository Layout

```
Agent_Swarm/
├── CLAUDE.md                  ← you are here (session primer)
├── agents/
│   ├── main.py                ← FastAPI entry point; SSE allowlist (~line 1384)
│   ├── church.py              ← Master router/dispatcher; route() generator; slash commands
│   ├── handlers/
│   │   ├── design.py          ← Design Mode (Ollama HTML → Open Design project)
│   │   ├── workshop.py        ← Workshop Mode (Phase 1 questions → Phase 2 brief)
│   │   └── swarm.py           ← Swarm Mode (multi-agent coordinator)
│   ├── specialized/
│   │   └── open_design_client.py  ← OD daemon client
│   └── semantic_router/
│       └── fast_classify.py   ← Regex fast-path (avoids 30s cold LLM load)
├── ui/
│   └── src/
│       ├── app/api/backend/[...path]/route.ts  ← Next.js proxy → agent_runtime
│       ├── lib/
│       │   ├── api/chat.ts            ← API_BASE = "/api/backend"
│       │   ├── hooks/use-chat-stream.ts
│       │   ├── stores/
│       │   │   ├── chat-store.ts
│       │   │   └── settings-store.ts  ← workshopMode, designMode, swarmMode flags
│       │   └── utils/sse-parser.ts    ← SSE event type dispatch
│       ├── components/chat/
│       │   ├── workshop-questions-card.tsx   ← Phase 1 accordion chips
│       │   ├── workflow-actions-card.tsx     ← "Continue the Pipeline" buttons
│       │   └── workshop-toggle.tsx
│       └── types/chat.ts              ← StreamEvent union; WorkshopQuestion; WorkflowNextStep
├── execution_plane/
│   └── docker-compose.yml     ← Lovelace containers (hive_ui, agent_runtime workers)
└── turing_gateway/            ← Traefik + Cloudflare tunnel config (on Turing)
```

---

## 🔄 Request Flow (Browser → LLM)

```
Browser
  └─→ https://memex.shivelymedia.com  (CF Tunnel → Traefik on Turing:443)
        └─→ memex_ui:3000  (Next.js)
              └─→ /api/backend/* proxy
                    └─→ http://agent_runtime:8000  (ai_lab_net, internal)
                          └─→ agents/church.py → handler → Ollama:11434
```

**SSE pipeline:**
```
Python generator (church.py)
  → main.py async queue
  → SSE allowlist (⚠️ new event types must be added here)
  → sse-parser.ts
  → Zustand store setters
  → React components
```

---

## 🚀 Workflow Modes & Slash Commands

| Command | Mode | What it does |
|---------|------|-------------|
| `/workshop` or `/grill` | Workshop | Two-phase discovery: questions → Product Brief → pipeline buttons |
| `/design` | Design | Ollama generates self-contained HTML; OD project created for "Open Studio" |
| `/build` or `/swarm` | Swarm | Multi-agent coordinator (ultraplan default) |
| `/plan` | Swarm + ultraplan | Explicit planning phase |
| `/research` | Research | Deep web/doc research |
| `/think` | Think | Extended reasoning |

**Workshop pipeline flow:**
1. `/workshop <idea>` → Phase 1 questions emitted as `workshop_questions` SSE event → accordion chips in UI
2. User fills answers → "Submit N answers" → Phase 2 brief generation
3. Brief contains `### ▶️ Design Mode Prompt` and `### ⚙️ Swarm Mode Prompt` sections
4. Backend parses and emits `workflow_next_steps` → "Continue the Pipeline" card with two buttons
5. Click "Generate Mockup" → switches to Design Mode, fires prompt
6. Click "Start Build" → switches to Swarm Mode, fires prompt

---

## ⚠️ Common Gotchas

### Adding new SSE event types
Two places, both required:
1. `agents/main.py` — SSE allowlist (search for `"workshop_questions"` to find it)
2. `ui/src/lib/utils/sse-parser.ts` — both the main loop AND the trailing-buffer handler (duplicated block at bottom of file)

### Container names ≠ service names
- `agent_runtime` listens on container port **8000**, mapped to host port **8008**
- `memex_ui` listens on container port **3000**, mapped to host port **3200**
- The UI's Next.js proxy uses the **container hostname** `agent_runtime:8000` (internal Docker network) — not the host port

### Deploying changes
```bash
# Backend only (no rebuild needed)
docker restart agent_runtime

# UI changes (must rebuild)
cd /opt/stacks/memex   # or wherever docker-compose.yml lives on Turing
docker compose build memex-ui && docker compose up -d memex-ui

# Or via Docker API from Windows (no SSH needed):
Invoke-RestMethod -Uri "http://192.168.2.103:2375/containers/agent_runtime/restart" -Method Post
```

### Open Design daemon (OD v0.5.0)
- Endpoint: `http://192.168.2.101:7456`
- `POST /api/projects` **requires** a caller-supplied `id` (UUID) field — the daemon does NOT generate one
- No file upload endpoint; no agent-run API
- Design mode uses Ollama-first HTML generation; OD project is created only for the "Open Studio" deep-link

### MemPalace timeout
- Set to `timeout=3.0` in church.py (was 10s — caused routing stalls)
- Circuit breaker task is pending (spawned chip awaiting approval)

### Routing latency
- qwen3:8b cold start = 20-30s VRAM load — eliminated by `fast_classify()` regex pre-check in church.py
- Swarm mode pre-intent check uses `_SWARM_MEDIA_RE` regex, not LLM

### DNS / Cloudflare
- `*.shivelymedia.com` → CNAME → CF tunnel (proxied)
- Specific A records (e.g. `jellyfin.shivelymedia.com → 192.168.2.103`) **override** the wildcard — if a subdomain stops working externally, check for a stale A record in CF dashboard
- CF BYOK proxy blocks RFC1918 addresses (can't proxy to 192.168.x.x directly)

---

## 🔑 Management Without SSH

When SSH to a node is unavailable, use the Docker API:

```powershell
# List containers
Invoke-RestMethod -Uri "http://192.168.2.103:2375/containers/json?all=true" -Method Get |
  ForEach-Object { "$($_.Names) | $($_.State) | $($_.Status)" }

# Restart a container
Invoke-RestMethod -Uri "http://192.168.2.103:2375/containers/agent_runtime/restart" -Method Post

# Get logs
Invoke-RestMethod -Uri "http://192.168.2.103:2375/containers/agent_runtime/logs?stdout=true&stderr=true&tail=50" -Method Get

# Check port mappings
(Invoke-RestMethod -Uri "http://192.168.2.103:2375/containers/memex_ui/json" -Method Get).NetworkSettings.Ports
```

> ⚠️ Docker API port 2375 is unauthenticated on both Turing and Lovelace — this is a known security debt.

---

## 📦 Pending Tasks (as of 2026-05-31)

- [ ] **MemPalace circuit breaker** — spawned chip, awaiting user approval to start
- [ ] **Dev workspace session continuity review** — spawned chip, awaiting approval
- [ ] **Dev UI/UX design review** — spawned chip, awaiting approval
- [ ] **Docker API 2375 security** — unauthenticated exposure on both Turing and Lovelace; should be TLS + client cert or socket proxy only
- [ ] **Lovelace SSH** — sshd is down; investigate and restore
- [ ] **`training_dispatcher` container** — stuck in restart loop on Lovelace (exit code 1)
