# Memex / Agent_Swarm — Session Primer

> **Read this first, every session.** This file is the authoritative reference for the home lab infrastructure, project layout, and workflow conventions. `topology.md` is outdated — ignore it.

---

## 🗺️ Network Map

| Host | IP | Role |
|------|----|------|
| **Home Assistant** | `192.168.2.100` | Home automation hub |
| **Lovelace** | `192.168.2.101` | **Local workstation** — where you and Claude Code run. Execution plane, GPU node, ComfyUI, Ollama. |
| **Hopper** | `192.168.2.102` | Data plane (Postgres, Redis, Langfuse, MemPalace) |
| **Turing** | `192.168.2.103` | **Primary Memex host** (Traefik, memex_ui, agent_runtime, Cloudflare tunnel) |
| **BMO** | `192.168.2.106` | Voice / media node |

> ⚠️ **Common mistake:** Turing is `.103`, Lovelace is `.101`. The names look similar in env vars — always double-check before running commands.

---

## 🖥️ Turing (192.168.2.103) — Primary Host

| Service | Host Port | Notes |
|---------|-----------|-------|
| SSH | 22 | `ssh -o IdentitiesOnly=yes -o IdentityAgent=none -i ~/.ssh/id_ed25519 misterobots@192.168.2.103` |
| HTTP (Traefik) | 80 | |
| HTTPS (Traefik) | 443 | wildcard cert via CF DNS (`*.shivelymedia.com`) |
| Docker API | **2375** | `docker-socket-proxy`, bound to `192.168.2.103:2375` only, `POST=1` (restart/exec), behind host iptables allowlist |
| Ollama | 11434 | GPU-backed (RTX 3070Ti, 8GB) — **small-model fast path**: safety, embeddings, nano/small general models (`llama-guard3`, `nomic-embed-text`, `llama3.2:3b`, `qwen3:8b`). Routing list lives in `agents/utils/gpu_queue.py` `_get_preferred_host()`. Everything larger routes to Lovelace. |
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
memex_ui          running   ai_lab_net + saltbox   ← image: home-ai-lab/memex-ui:latest
traefik           running   saltbox
cloudflared       running   (CF tunnel daemon)
ollama-turing     running   small-model fast path (8GB VRAM) — must stay running, restart=always
redis-turing      running
authentik         running   (SSO)
```

> Turing's live Compose project is owned by `/home/misterobots/docker-compose.yml` and reads `/home/network.env`. The tracked deployment template is `turing_gateway/docker-compose.yml`; copy the validated template to the live root path when deploying. The retired `docker-compose-Justin-PC.yml` fork must not be used.

**Traefik auth middleware:** `authentik@file` — requests to `memex.shivelymedia.com` go through Authentik SSO.

---

## ⚙️ Lovelace (192.168.2.101) — Local Workstation

> **This is the machine you and Claude Code are running on.** It is not a remote server — it is the local workstation. Run Docker and shell commands here directly; no SSH needed.

| Service | Host Port | Notes |
|---------|-----------|-------|
| Docker Desktop | local | Run `docker` commands directly — no remote API needed |
| Ollama | 11434 | GPU-backed (2× RTX 5060Ti, 32GB) — **primary model host**: all heavy models (27–31B: `qwen3.6:27b`, `gemma4:31b`, `qwen3-coder:30b`, `deepseek-r1:32b`, etc.) plus mid-size (`qwen3:14b`). This is `OLLAMA_HOST` for both Lovelace and Turing agent_runtime containers. |
| Open Design daemon | 7456 | OD v0.5.0; requires caller-supplied `id` UUID in POST /api/projects |
| Authentik | 9000 | SSO |
| `agent_runtime` (prod) | **8008** | internal 8000 → host 8008 |
| `agent_runtime` (dev) | **8009** | internal 8000 → host 8009 |
| `hive_ui_local` (prod) | **3300** | internal 3000 → host 3300 |
| `hive_ui_dev` | **3301** | internal 3000 → host 3301 |

**Docker Compose project:** `execution_plane/docker-compose.yml` (runs locally)

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
│   ├── main.py                ← FastAPI entry point; SSE allowlist = _RICH_EVENT_TYPES /
│   │                             _NONSTANDARD_SIGNAL_TYPES module-level frozensets (search
│   │                             for either name — no fixed line number, they get edited)
│   ├── church.py               ← Master router/dispatcher; chat_swarm() generator; slash commands
│   ├── config.py               ← Model-role env defaults (PRIMARY/COORDINATOR/ARCHITECT/etc.)
│   ├── semantic_router.py      ← Single file; neural router + fast_classify() regex fast-path
│   ├── swarm_run_store.py      ← Durable swarm-run history (task list, diff, approve/deny)
│   ├── handlers/               ← 12 handlers + base.py, NOT a 3-file dir (design/workshop/swarm
│   │                             is stale — there is no swarm.py; swarm dispatch lives in
│   │                             coordinate.py + agents/coordination/)
│   │   ├── design.py           ← Design Mode (Ollama HTML → Open Design project)
│   │   ├── workshop.py         ← Workshop Mode (Phase 1 questions → Phase 2 brief)
│   │   ├── coordinate.py       ← Swarm Mode entry point (hands off to agents/coordination/)
│   │   ├── cad.py              ← CAD Mode (OpenSCAD generation → cad_artifact SSE event)
│   │   └── architect.py, conversation.py, creative.py, devops.py, image.py, media.py,
│   │       research.py, train.py, vision.py
│   ├── coordination/            ← Swarm coordinator internals
│   │   ├── orchestrator.py      ← Phase loop, worker dispatch, swarm-theater SSE events
│   │   ├── session.py           ← CoordinatorSession / WorkerInfo lifecycle tracking
│   │   ├── executor.py          ← DEVHARNESS_ELIGIBLE_ROLES gate, worker execution
│   │   └── devharness_worker.py ← DevHarness-backed worker (coder/devops on sandbox)
│   ├── pairing/
│   │   └── routes.py           ← Remote pairing REST + WS relay (routed via a dedicated
│   │                             Traefik `pairing-ws` router, bypasses the Next.js proxy)
│   ├── utils/
│   │   └── gpu_queue.py        ← get_best_host_for_model() / _get_preferred_host() — the
│   │                             Lovelace-vs-Turing model routing decision lives here
│   ├── specialized/
│   │   └── open_design_client.py  ← OD daemon client
│   └── dev_harness/, dev_files/, dev_projects/, dev_sessions/  ← /dev workspace backend
├── ui/
│   └── src/
│       ├── app/api/backend/[...path]/route.ts  ← Next.js proxy → agent_runtime (HTTP only —
│       │                                          cannot upgrade WebSockets; see pairing gotcha)
│       ├── lib/
│       │   ├── api/chat.ts            ← API_BASE = "/api/backend"
│       │   ├── hooks/
│       │   │   ├── use-chat-stream.ts
│       │   │   └── use-pairing.ts     ← WS_BASE points at the gateway directly, NOT /api/backend
│       │   ├── stores/
│       │   │   ├── chat-store.ts
│       │   │   └── settings-store.ts  ← workshopMode, designMode, swarmMode flags
│       │   └── utils/sse-parser.ts    ← single deltaToStreamEvent() dispatcher (deduped from
│       │                                 two copy-pasted blocks — do not re-duplicate it)
│       ├── components/chat/
│       │   ├── workshop-questions-card.tsx   ← Phase 1 accordion chips
│       │   ├── workflow-actions-card.tsx     ← "Continue the Pipeline" buttons
│       │   ├── cad-artifact-card.tsx         ← CAD Mode render (scad/stl links)
│       │   └── workshop-toggle.tsx
│       └── types/chat.ts              ← StreamEvent union; WorkshopQuestion; WorkflowNextStep
├── execution_plane/
│   └── docker-compose.yml     ← Lovelace containers (hive_ui, agent_runtime workers)
└── turing_gateway/            ← Traefik + Cloudflare tunnel config (on Turing)
    ├── docker-compose.yml               ← canonical
    └── kiosk/                           ← Memex Brain rack-display kiosk (separate feature)
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
Two places, both required (as of the 2026-07 SSE refactor — the old "3 places, one of them duplicated" gotcha is gone):
1. `agents/main.py` — add the type to `_RICH_EVENT_TYPES` or `_NONSTANDARD_SIGNAL_TYPES` (module-level frozensets, search for either name)
2. `ui/src/lib/utils/sse-parser.ts` — add a case to the single `deltaToStreamEvent()` function. **It is no longer duplicated** — do not reintroduce a second copy-pasted dispatch block; both the line loop and the trailing-buffer tail call the same function.

### Git branch drift on deployed hosts — check before you deploy
Turing's live checkout (`/home/misterobots/Agent_Swarm`) is not guaranteed to be on `main`. It has been found running its own long-lived feature branch, diverged from `main` for weeks, carrying real unmerged commits (a durable swarm-task-history feature, a kiosk display feature) and uncommitted WIP. **Before any `git pull`/deploy on Turing (or any other host), SSH in and check `git branch --show-current`, `git status --short`, and `git log --oneline -1` first** — do not assume it mirrors `main`.

### WebSocket routes must bypass the Next.js `/api/backend` proxy
`ui/src/app/api/backend/[...path]/route.ts` is a plain HTTP catch-all — it cannot upgrade a connection to WebSocket. Any WS feature (pairing, the dev terminal) must connect directly to the gateway (`NEXT_PUBLIC_GATEWAY_URL`, see `WS_BASE` in `use-pairing.ts` / `terminal-pane.tsx`) and needs its own dedicated Traefik `PathPrefix` router pointing straight at `agent_runtime:8000` (see the `pairing-ws` / `terminal-ws` routers in both `turing_gateway/*.yml` files) — routing it through `memex-ext` will silently fail to connect.

### Container names ≠ service names
- `agent_runtime` listens on container port **8000**, mapped to host port **8008**
- `memex_ui` listens on container port **3000**, mapped to host port **3200**
- The UI's Next.js proxy uses the **container hostname** `agent_runtime:8000` (internal Docker network) — not the host port

### Deploying changes
```bash
# Backend only (no rebuild needed) — SSH to Turing first, code is bind-mounted
docker restart agent_runtime

# UI changes (must rebuild), and ANY new Traefik labels (they live on the
# memex-ui service block, so recreating it is also how Traefik picks up new
# routers e.g. pairing-ws) — SSH to Turing first
cd /home/misterobots
# From the clean /home/misterobots/Agent_Swarm-deploy checkout:
/home/misterobots/Agent_Swarm-deploy/turing_gateway/deploy.sh
```
Verifying a new Traefik router actually registered is hard from outside: Authentik's forward-auth middleware intercepts every path under `memex.shivelymedia.com` identically before any backend routing happens, so an unauthenticated `curl` to a new route and to a nonsense path both 302 to Authentik — that is NOT evidence the router works or doesn't. Confirm instead via (a) valid label YAML, (b) zero errors in `docker logs traefik` after the recreate, and (c) an authenticated end-to-end test through the browser.

**Management from Windows via SSH tunnel** (port 2375 is IP-restricted; see Security below):
```powershell
# Open SSH tunnel to Turing in one terminal, leave it running
ssh -N -L 2375:127.0.0.1:2375 user@192.168.2.103

# In a second terminal — all calls go via the tunnel
Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/agent_runtime/restart" -Method Post
Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/json?all=true" -Method Get |
  ForEach-Object { "$($_.Names) | $($_.State) | $($_.Status)" }
```

### Open Design daemon (OD v0.5.0)
- Endpoint: `http://192.168.2.101:7456`
- `POST /api/projects` **requires** a caller-supplied `id` (UUID) field — the daemon does NOT generate one
- No file upload endpoint; no agent-run API
- Design mode uses Ollama-first HTML generation; OD project is created only for the "Open Studio" deep-link

### MemPalace timeout + connectivity
- Recall timeout is `timeout=3.0` in church.py (was 10s — caused routing stalls); circuit breaker (`_mp_breaker`, 3-failure threshold → 60s open → half-open probe) is implemented and shared across recall call sites.
- `MEMPALACE_API_URL=http://mempalace:8200` is a Docker-DNS name — it only resolves if the compose service has an `extra_hosts: ["mempalace:${HOPPER_IP}"]` entry. This was missing from `agent-runtime` in the deployed Turing compose for a while (found + fixed 2026-07); if MemPalace recall silently stops working after a Turing redeploy, check `docker exec agent_runtime getent hosts mempalace` first.
- Optional per-user "vault" federation exists in `church.py` (`MEMPALACE_VAULT_URL`/`_OWNER`/`_FOR` env vars) — an opt-in, per-owner personal MemPalace instance consulted in addition to the shared one. Inert unless all three vars are set; shares `_mp_breaker` under its own `"vault"` key.

### Routing latency
- qwen3:8b cold start = 20-30s VRAM load — eliminated by `fast_classify()` regex pre-check in church.py
- Swarm mode pre-intent check uses `_SWARM_MEDIA_RE` regex, not LLM

### DNS / Cloudflare
- `*.shivelymedia.com` → CNAME → CF tunnel (proxied)
- Specific A records (e.g. `jellyfin.shivelymedia.com → 192.168.2.103`) **override** the wildcard — if a subdomain stops working externally, check for a stale A record in CF dashboard
- CF BYOK proxy blocks RFC1918 addresses (can't proxy to 192.168.x.x directly)

---

## 🔑 Management Without SSH

Port 2375 is a `docker-socket-proxy` (tecnativa) with an iptables allowlist — not the raw Docker daemon.
Allowed sources: Lovelace → Turing, Turing → Lovelace. Windows management uses an SSH tunnel (see Deploying above).

```powershell
# Via SSH tunnel (ssh -N -L 2375:127.0.0.1:2375 user@192.168.2.103 running in background):
Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/json?all=true" -Method Get |
  ForEach-Object { "$($_.Names) | $($_.State) | $($_.Status)" }

Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/agent_runtime/restart" -Method Post

Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/agent_runtime/logs?stdout=true&stderr=true&tail=50" -Method Get

(Invoke-RestMethod -Uri "http://127.0.0.1:2375/containers/memex_ui/json" -Method Get).NetworkSettings.Ports
```

> **Security model:** port 2375 is `POST=1` (full write) but bound to the node's own LAN IP only (`192.168.2.103:2375` on Turing, `192.168.2.101:2375` on Lovelace — not `0.0.0.0`), and only reachable from allowlisted node IPs via iptables DOCKER-USER rules. SSH tunnel is the management path from Windows — do not open 2375 to 0.0.0.0. If you ever find a proxy container bound to `0.0.0.0:2375` (check with `docker inspect <name> --format '{{json .HostConfig.PortBindings}}'`), it predates a compose-file fix and needs `docker compose up -d --force-recreate` to pick up the correct binding — the compose file being correct does NOT mean the running container is.

---

## 📦 Pending Tasks (as of 2026-07-06)

- [ ] **BMO voice model too large for the Turing fast path** — `BMO_LLM_MODEL=qwen3:14b` (9.2GB) doesn't fit Turing's 8GB VRAM. If voice should run on Turing's fast path, switch it to `qwen3:8b` or `llama3.2:3b` (compose env change, not yet done).
- [ ] **Turing small-model warm latency is higher than expected** — `llama3.2:3b` measured ~10s warm-inference for a few tokens on the 3070Ti. GPU is confirmed engaged (100% VRAM via `/api/ps`), so this isn't a CPU fallback — likely a tuning/contention question, worth investigating before relying on the fast path for latency-sensitive calls.
- [ ] **Pairing end-to-end test needs a human** — the WS routing fix and Traefik `pairing-ws` router were verified by config/log inspection only; Authentik's forward-auth intercepts every path identically, so it cannot be confirmed via unauthenticated curl. Needs two authenticated browser sessions (host + guest) to actually confirm the relay.
- [ ] **"Agent View" live session registry** — an in-progress feature in `agents/coordination/session.py` (`_ACTIVE_SESSIONS` weakref registry) found uncommitted on the main checkout during a 2026-07-06 branch reconciliation. Preserved as-is (not reviewed, not finished) — pick up wherever it was left off.
- [ ] **`-Justin-PC` fork file sprawl + worktree sprawl** — the obsolete Turing compose fork was retired in 2026-08; other duplicate files and accumulated worktrees still need triage.
- [ ] **Unverified from the 2026-07-03 review**: docs-site Traefik router may be missing `authentik@file` middleware (would serve internal docs unauthenticated); ntfy compose has a bcrypt-hash fallback default instead of required-var syntax. Neither independently re-verified since.
- [ ] **Android build pipeline** — add a `./gradlew assembleRelease` step to the execution plane so Swarm-generated Kotlin projects can be compiled to an APK and sideloaded to a tablet without leaving Memex. Triggered by the Hitchhiker's Guide project.
- [ ] **Dev workspace session continuity review** — spawned chip, awaiting approval
- [ ] **Dev UI/UX design review** — spawned chip, awaiting approval
- [ ] **Visual UI testing of dev workspace** — `/dev` page blocked by Authentik admin gate locally; needs SSO login or local auth bypass to verify TodoCard rendering, diff chips, pioneer academy cards, and agent trace rendering end-to-end
- [x] **2026-07-03 deep review + fix batch** — 7-dimension multi-agent review (20 confirmed findings) followed by fixes, all merged to `main` and deployed: MemPalace DNS dead on Turing (missing `extra_hosts`) fixed; production model roster silently downgraded to `qwen3:14b` fixed (full 27–31B roster restored + `GPU_LOCK_HOST`); remote pairing fixed (WS routed via dedicated `pairing-ws` Traefik router instead of the non-upgradeable Next.js proxy, plus a frozen-peer-token relay bug); SSE allowlist was silently dropping `model_queue_status`/`tool_start`/`tool_progress`/`tool_result`/`todo` despite full UI support — added, and the two duplicated allowlist tuples in main.py were hoisted into shared frozensets; a dead `heartbeat` event was actively suppressing the SSE keepalive during long swarm silences — now emits a real keepalive; `sse-parser.ts`'s two duplicated dispatch blocks (a known drift landmine — already 4 events out of sync) were collapsed into one `deltaToStreamEvent()`; a committed Fish Audio API key was rotated and compose switched to `env_file`-only (a `${VAR}` passthrough in `environment:` would have kept reading the old key from `execution_plane/.env` — env_file must be the *sole* source); both nodes' `docker-socket-proxy` containers were found bound to `0.0.0.0:2375` despite compose already saying otherwise (fixing the compose file does not fix an already-running container) — recreated + the one remaining file drift (Turing's Justin-PC variant) corrected; `ollama-turing` was never started — started, and `gpu_queue.py` routing widened so small/nano models (`llama-guard3`, `nomic-embed-text`, `llama3.2:3b`, `qwen3:8b`) use it as a fast path. Discovered mid-fix: Turing's live checkout was actually on its own long-lived divergent branch (13 unmerged commits: durable swarm-task-history API, a kiosk display feature, a third independent copy of the MemPalace fix) — reconciled and merged into `main`.
- [x] **MemPalace circuit breaker** — already implemented in church.py (`_mp_breaker = _CircuitBreaker()` from gpu_queue.py); 3-failure threshold → 60s open → half-open probe. Chip was stale.
- [x] **Swarm-on-DevHarness Phase D** — retired leibniz fallback for unknown roles in executor.py; `_run_worker` agent param is now `Agent | None` with clear RuntimeError guard; unknown roles get a minimal text-only agent instead of silently gaining file access (640263b)
- [x] **Swarm-on-DevHarness Phase C — pioneer injection + all roles** — all 6 roles in `DEVHARNESS_ELIGIBLE_ROLES`; scope-based normalization for perspective roles (`technical`/`ethical` → `researcher`); sandbox path double-prefix fix; `setup_logger` fix in devharness_worker. E2E verified 2026-06-13: workers Shannon/Minsky/Codd/Johnson all route to `qwen3:14b` DevHarness with pioneer names in logs (commit 1c974a8)
- [x] **Swarm-on-DevHarness Phase B** — substrate reconciliation; `SWARM_DEVHARNESS_WORKERS=true` default in compose (ecbf2d9)
- [x] **Swarm-on-DevHarness Phase A** — coder/devops on sandbox, `devharness_worker.py` extracted (d67c865)
- [x] ~~**Docker API 2375 security** — restricted to LAN IPs via iptables; ports now bound to node IP, not 0.0.0.0~~ — this was marked done here but the *running containers* on both nodes had actually drifted back to `0.0.0.0:2375` (compose said the right thing; nobody had recreated the containers). Actually fixed in the 2026-07-03/06 batch above — lesson: verify the live container, not just the compose file.
- [x] **`training_dispatcher` crash loop** — fixed (`ARCHETYPE_TRAINING_CONFIGS` added to config.py, `--target` flag corrected); running clean as of 2026-05-31
- [x] **Swarm recursion crash** — fixed; implementation workers now use `worker_id` as Postgres session key instead of coordinator `session_id`, preventing phidata pydantic comparison recursion across workers (2026-06-04)
- [x] **hive_ui → memex_ui container drift** — `docker-compose-Justin-PC.yml` on Turing was never updated by the May rename commit; fixed all `hive-*` → `memex-*` references and added missing static asset bypass routes (2026-06-04)
- [x] **Design revision degradation** — revisions cold-started a fresh generation with no HTML context; fixed with session-scoped artifact cache (`/workspace/delivered_artifacts/latest_{session_id}.html`) injected on revision, capped at 32 KB (2026-06-04)
- [x] **MODEL_WINDOWS stale in UI** — all current models (`gemma4:31b`, `qwen3-coder:30b`, `qwen3.6:27b`, etc.) fell through to `default: 8192`, triggering premature compaction; table updated with correct windows (2026-06-04)
- [x] **Verifier context overflow** — `all_work` passed to verifier with no size cap; added 24 K char limit to stay within `qwen3:14b`'s 16 K context window (2026-06-04)
