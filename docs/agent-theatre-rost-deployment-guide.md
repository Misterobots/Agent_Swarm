# Agent Theatre & Rost — Implementation and Deployment Guide

> **Audience:** Developers deploying the Memex multi-agent orchestration experience on a new system or architecture.  
> **Scope:** Backend coordinator (Lamport), event stream contract, frontend Theatre UI, and the Rost (Roster) component system.  
> **Date:** April 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Map](#2-architecture-map)
3. [Backend — The Coordinator (Lamport)](#3-backend--the-coordinator-lamport)
4. [Event Stream Contract](#4-event-stream-contract)
5. [Frontend — Agent Theatre](#5-frontend--agent-theatre)
6. [Frontend — The Rost (Agent Roster)](#6-frontend--the-rost-agent-roster)
7. [State Machine: Theatre Phases](#7-state-machine-theatre-phases)
8. [Pioneer Persona System](#8-pioneer-persona-system)
9. [Cross-Window Broadcast](#9-cross-window-broadcast)
10. [Dependencies and Environment Variables](#10-dependencies-and-environment-variables)
11. [Deployment Checklist](#11-deployment-checklist)
12. [Porting to a New Architecture](#12-porting-to-a-new-architecture)

---

## 1. System Overview

The **Agent Theatre** is the real-time visual orchestration layer that brings multi-agent task execution to life in the Memex UI. When the backend decomposes a user request into parallel and serial sub-tasks, the Theatre animates each agent's "arrival" as a physical ID badge drop-in, then transitions to the **Rost** — a grid of active worker cards — while work proceeds.

**Rost** (short for Roster) is the persistent visual registry of all workers spawned for a given coordination session. It shows role, status, pioneer persona name, and a short task description for each agent.

The two systems are tightly coupled through a single event stream: the backend emits structured JSON events, and the frontend's Zustand store consumes them to drive the animation state machine.

---

## 2. Architecture Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  USER  ──►  Hive UI (Next.js)                                       │
│             │                                                        │
│             ▼                                                        │
│         use-chat-stream.ts ──► fetch (streaming POST)               │
│             │                      │                                 │
│             │◄──── SSE / NDJSON ───┘                                 │
│             │                                                        │
│             ▼                                                        │
│         useSwarmStore (Zustand)                                      │
│         ├── theaterPhase (state machine)                             │
│         ├── badgeQueue (FIFO animation queue)                        │
│         └── workers[] (Rost data)                                    │
│             │                                                        │
│             ▼                                                        │
│         SwarmDrawer ──► AgentIdCard (badge drop-in animation)       │
│                     └─► AgentRoster (Rost grid, frosted-glass cards) │
│                     └─► AgentDock (live "working" status row)        │
│                                                                      │
│  BACKEND (agent_runtime, Turing Docker)                              │
│  ├── church.py — intent router                                       │
│  ├── lamport.py — coordinator / generator                            │
│  │   ├── _decompose_task() — LLM structured decomposition           │
│  │   ├── Phase 2: parallel research (ThreadPoolExecutor)             │
│  │   ├── Phase 3: synthesis (LLM)                                    │
│  │   ├── Phase 4: serial implementation                              │
│  │   └── Phase 5: verifier worker                                    │
│  └── scratchpad/ — per-session file workspace                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend — The Coordinator (Lamport)

**File:** `agents/lamport.py`

The coordinator is a Python **generator function** that `yield`s structured event dicts throughout the entire lifecycle of a multi-agent task. The caller (the API endpoint) streams these to the client as newline-delimited JSON.

### 3.1 Session Object

```python
class CoordinatorSession:
    session_id: str           # Inherited from the chat session
    coordination_id: str      # coord-<8 hex chars> — unique per invocation
    workers: dict[str, WorkerInfo]
    scratchpad_dir: Path      # agents/scratchpad/<session_id>/<coordination_id>/
```

The scratchpad is a local filesystem workspace. Each worker writes its output to a `.md` file there. At synthesis time, all files are concatenated and passed to the LLM.

### 3.2 WorkerInfo

```python
class WorkerInfo:
    worker_id: str            # w-<6 hex chars>
    role: str                 # researcher | architect | coder | devops | analyst | verifier
    task: str                 # The specific subtask text
    phase: str                # research | implementation | verification
    pioneer: dict             # {name, full_name, motto} — display persona
    state: WorkerState        # pending | running | completed | failed | cancelled
    result: Optional[str]
    error: Optional[str]
    started_at: Optional[float]
    completed_at: Optional[float]
    cancel_flag: threading.Event
```

### 3.3 Execution Phases

| Phase | Number | Parallelism | Key Event Emitted |
|-------|--------|-------------|-------------------|
| Decompose | 1 | — | `swarm_phase` |
| Research | 2 | **Parallel** (ThreadPoolExecutor) | `swarm_worker_created`, `swarm_task_list` |
| Synthesize | 3 | — | `swarm_phase`, `message` |
| Implement | 4 | **Serial** | `swarm_worker_created`, `swarm_task_list` |
| Verify | 5 | — | `swarm_worker_created`, `swarm_task_list` |

### 3.4 Task Decomposition

`_decompose_task()` calls the `COORDINATOR_MODEL` (default: `qwen3:14b`) with a structured JSON prompt. It returns:

```json
{
  "summary": "One-sentence task summary",
  "research_tasks": [
    {"role": "researcher|architect|analyst", "task": "specific question"}
  ],
  "implementation_tasks": [
    {"role": "architect|coder|devops", "task": "specific step"}
  ],
  "verification_criteria": ["criterion 1", "criterion 2"]
}
```

Rules enforced: 2–5 research tasks, 1–4 implementation tasks, 1–3 criteria. All research tasks run in parallel; implementation tasks are strictly serial.

### 3.5 Agent Factory (`_get_agent_for_role`)

Maps role strings to Agno `Agent` instances:

| Role | Agent Used |
|------|------------|
| `architect`, `coder`, `devops` | `leibniz_agent.get_architect_agent()` |
| `analyst` | Inline Agno Agent (data analyst instructions) |
| `researcher` | Inline Agno Agent (research instructions) |
| `verifier` | Inline Agno Agent (verification instructions) |

All agents use `ARCHITECT_MODEL` (env var) via Ollama with a 300 s timeout.

### 3.6 JWT-ACE Child Tokens

If the JWT-ACE security layer is available (`security/token_issuer.py`), each worker receives a **derived child token** scoped to the minimum capabilities that role needs:

```python
_ROLE_CAPS = {
    "architect": ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read", "git_write"],
    "coder":     ["file_read", "file_write", "terminal_exec", "terminal_read", "model_generate", "git_read"],
    "researcher":["model_generate", "api_call", "file_read"],
    "verifier":  ["model_generate", "file_read"],
    ...
}
```

Child token derivation is **graceful-fallback**: if the security module is absent, workers run without capability tokens (suitable for dev/lab deployments).

---

## 4. Event Stream Contract

This is the **interface boundary** between backend and frontend. Implementing this contract correctly is all that is required to make the Theatre UI work with any backend.

All events are dicts yielded by the coordinator generator, serialised as JSON, and sent line-by-line over HTTP streaming.

### 4.1 `swarm_phase`

Signals a new coordination phase.

```json
{
  "type": "swarm_phase",
  "phase_num": 2,
  "phase_name": "Research",
  "total_phases": 5
}
```

**Phase number → Theatre phase mapping:**

| `phase_num` | Theatre State |
|-------------|---------------|
| 1 | `decomposing` |
| 2 | `roster` (initial worker reveal) |
| 3 | `synthesizing` |
| 4+ | `working` |

### 4.2 `swarm_worker_created`

Tells the UI to animate a new agent ID badge and add it to the Rost.

```json
{
  "type": "swarm_worker_created",
  "worker_id": "w-a3f21b",
  "role": "researcher",
  "pioneer_name": "Shannon",
  "pioneer_full_name": "Claude Shannon",
  "pioneer_motto": "Information is the resolution of uncertainty.",
  "task": "Investigate existing retry logic in the HTTP client",
  "phase": "research",
  "content": "Spawned Shannon (researcher)"
}
```

**Required fields:** `worker_id`, `role`, `pioneer_name`, `pioneer_full_name`, `pioneer_motto`, `task`, `phase`.

### 4.3 `swarm_task_list`

Provides a full snapshot of all workers in a phase, including their current state. Used to update the Rost after each worker completes or fails.

```json
{
  "type": "swarm_task_list",
  "workers": [
    {
      "worker_id": "w-a3f21b",
      "pioneer_name": "Shannon",
      "pioneer_full_name": "Claude Shannon",
      "pioneer_motto": "...",
      "role": "researcher",
      "task": "...",
      "state": "completed",
      "output": "First 600 chars of worker result..."
    }
  ],
  "content": "Shannon completed"
}
```

**Worker states:** `pending` | `running` | `completed` | `failed` | `cancelled`

### 4.4 Other Event Types (pass-through)

These events also reach the Theatre's `use-chat-stream.ts` consumer but drive the main chat bubble, not the Rost:

| Type | Purpose |
|------|---------|
| `status` | Status bar text (e.g. "🧠 Synthesizing...") |
| `message` | Appended to assistant chat bubble |
| `thought` | Thought trace (collapsible) |
| `log` | Dev console only |
| `content` | Streamed LLM text tokens |

---

## 5. Frontend — Agent Theatre

**Key files:**
- `ui/src/lib/stores/swarm-store.ts` — Zustand state machine
- `ui/src/lib/hooks/use-chat-stream.ts` — SSE consumer, calls store actions
- `ui/src/components/swarm/swarm-drawer.tsx` — Theatre container component
- `ui/src/app/swarm/page.tsx` — Detachable popout page

### 5.1 Activating the Theatre

The Theatre is activated when the chat stream's `use-chat-stream` hook detects a `swarm_worker_created` event for the first time in a response. If the Zustand store's `theaterPhase` is `"idle"`, it sets it to `"decomposing"` automatically.

```typescript
// use-chat-stream.ts (simplified)
if (event.type === "swarm_worker_created") {
  const { addWorker } = useSwarmStore.getState();
  addWorker({
    worker_id: event.worker_id,
    role: event.role,
    pioneer_name: event.pioneer_name,
    pioneer_full_name: event.pioneer_full_name,
    pioneer_motto: event.pioneer_motto,
    task: event.task,
    phase: event.phase,
    state: "pending",
  });
}
if (event.type === "swarm_phase") {
  useSwarmStore.getState().setSwarmPhase(event.phase_num, event.phase_name);
}
```

### 5.2 `SwarmDrawer` — Theatre Container

`swarm-drawer.tsx` renders different content based on `theaterPhase`:

| Phase | Content Rendered |
|-------|-----------------|
| `idle` | Nothing (drawer hidden) |
| `decomposing` | Spinner / thinking indicator |
| `spawning_card` | `AgentIdCard` (badge drop-in) + partial `AgentRoster` below |
| `roster` | Full `AgentRoster` grid (auto-transitions to `working` after 2 s) |
| `working` | `AgentDock` (live 3-worker activity row) + worker detail panels |
| `synthesizing` | Synthesis status indicator |
| `complete` | Final summary banner |

The drawer is a **slide-in panel** attached to the right of the chat view. It can be dismissed (soft-collapsed) and recalled via a floating action button. It also supports **popout** into a separate `/swarm` browser window via `BroadcastChannel`.

---

## 6. Frontend — The Rost (Agent Roster)

**File:** `ui/src/components/swarm/agent-roster.tsx`

The Rost is a responsive grid (`grid-cols-3` default) of agent cards. Each card shows:
- Role-colored accent stripe and background
- Pioneer portrait (SVG avatar)
- Pioneer name and full name
- Role badge with clearance level
- Task summary (truncated)
- Deterministic mini-barcode (generated from `worker_id`)
- Status (pending / running / completed / failed)

### 6.1 Role Theme System

Each role maps to a consistent color palette used across all Theatre components:

| Role | Color | Clearance |
|------|-------|-----------|
| `researcher` | Amber (`#f59e0b`) | LEVEL 3 |
| `architect` | Blue (`#3b82f6`) | LEVEL 4 |
| `coder` | Violet (`#8b5cf6`) | LEVEL 3 |
| `devops` | Emerald (`#10b981`) | LEVEL 5 |
| `analyst` | Cyan (`#06b6d4`) | LEVEL 3 |
| `verifier` | Rose (`#f43f5e`) | LEVEL 5 |

These color mappings must be consistent across: `agent-roster.tsx`, `agent-id-card.tsx`, `agent-dock.tsx`, and the CSS file (`agents/style.css`).

### 6.2 Progressive Reveal Animation

When workers spawn rapidly, the Rost uses a `revealedWorkerIds` set to progressively reveal cards as their ID badge animation completes:

1. Worker arrives → enters `badgeQueue`
2. `AgentIdCard` drops in for ~4.6 s
3. `onDone()` fires → `dequeueBadge()` called → worker_id added to `revealedWorkerIds`
4. Rost card fades in with `card-enter` bounce animation
5. If more workers in queue, next badge immediately plays; otherwise transitions to `roster` phase

Concurrency note: `addWorker` deduplicates by `worker_id` — safe to call multiple times with the same worker.

---

## 7. State Machine: Theatre Phases

```
idle
 │
 ▼ (first swarm_worker_created arrives)
decomposing
 │
 ▼ (swarm_phase phase_num=2 OR first worker created)
spawning_card ◄──────────────────────────┐
 │                                       │
 │ onDone() — badge animation completes  │
 ▼                                       │
 ├── more in badgeQueue? ────────────────┘
 │
 └── queue empty?
      ▼
    roster (2 s auto-advance timer)
      ▼
    working  ◄── swarm_phase phase_num ≥ 4
      │
      ▼ (swarm_phase phase_num=3)
    synthesizing
      │
      ▼ (stream complete)
    complete
```

**Critical rule:** The `spawning_card` phase is never overwritten by an incoming `swarm_phase` event. The badge must finish its animation before the phase can advance. This is enforced in `setSwarmPhase`:

```typescript
// Don't overwrite spawning_card — let the card animation finish
...(s.theaterPhase !== "spawning_card" ? { theaterPhase } : {}),
```

---

## 8. Pioneer Persona System

Ephemeral workers are named after real historical computer scientists. The system:

1. Assigns a pool of 3 pioneers per role (defined in `WORKER_PIONEERS` dict in `lamport.py`)
2. Picks the first name not already used in the current session (`_pick_unique_pioneer`)
3. Appends a numeric suffix if all three names are taken (e.g., `Shannon-2`)

**Pool definitions (from `lamport.py`):**

| Role | Pioneer Pool |
|------|-------------|
| researcher | Shannon, Curie, Feynman |
| architect | Babbage, Dijkstra, Brooks |
| coder | Knuth, Lovelace, Ritchie |
| devops | Cerf, Torvalds, Thompson |
| analyst | Codd, Hopper, Boole |
| verifier | Hoare, Turing, McCarthy |

The pioneer dict `{name, full_name, motto}` is attached to every `swarm_worker_created` event and stored in the `SwarmWorker` type so the UI can display it without any backend lookup.

### `SwarmWorker` TypeScript Type

```typescript
interface SwarmWorker {
  worker_id: string;
  role: string;
  pioneer_name: string;
  pioneer_full_name: string;
  pioneer_motto: string;
  task: string;
  phase: string;
  state: "pending" | "running" | "completed" | "failed" | "cancelled";
  output?: string;            // partial result (first ~600 chars, from swarm_task_list)
}
```

---

## 9. Cross-Window Broadcast

**File:** `ui/src/lib/hooks/use-swarm-broadcast.ts`

The Theatre supports detaching the Rost into a second browser window (e.g. a monitor-spanning overview) using the `BroadcastChannel` API on channel `"hive-swarm"`.

**Main window:** calls `useSwarmBroadcast()` at layout level — subscribes to Zustand store changes and posts serialized state to the channel on every change.

**Popout window** (`/swarm` page): on mount, posts a `"request_state"` message to the channel, receives a full state snapshot, then hydrates its own `useSwarmStore`.

No special server infrastructure is required — this is a client-only browser API. It will silently degrade in environments that don't support `BroadcastChannel` (e.g., Safari private mode).

---

## 10. Dependencies and Environment Variables

### Backend Python Dependencies

```
agno          # Agent framework (Phi)
requests      # HTTP calls to Ollama
threading     # Parallel research workers (stdlib)
concurrent.futures  # ThreadPoolExecutor (stdlib)
```

### Backend Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `COORDINATOR_MODEL` | `qwen3:14b` | LLM used for decomposition and synthesis |
| `ARCHITECT_MODEL` | *(required)* | LLM used for all worker agents |
| `OLLAMA_HOST` | `http://localhost:11434` | Primary Ollama endpoint |
| `SECONDARY_OLLAMA_HOST` | — | Secondary Ollama endpoint (load balancing) |
| `AGNO_DB_URL` | *(required)* | PostgreSQL connection string for agent memory |

### Frontend Dependencies

```json
{
  "zustand": "^4.x",
  "react": "^18.x",
  "next": "^14.x",
  "tailwindcss": "^3.x"
}
```

No additional npm packages are required for the Theatre or Rost. All animation is CSS-based.

### CSS Requirements

The Theatre uses custom CSS keyframes. Ensure the following animations are defined (from `agents/style.css` or equivalent):

```css
@keyframes id-card-hang { /* pendulum drop */ }
@keyframes id-scan { /* scan line sweep */ }
@keyframes card-enter { /* bounce-in for roster cards */ }
```

The UI relies on CSS custom properties for theming:
- `--chat-surface`, `--chat-bg`, `--chat-border`, `--chat-soft`, `--chat-muted`

---

## 11. Deployment Checklist

### Backend (agent_runtime container)

- [ ] `lamport.py` present in agents directory (or equivalent module path)
- [ ] `COORDINATOR_MODEL` points to a model capable of structured JSON output (Qwen3 14b recommended; minimum: any 7b+ with JSON mode)
- [ ] `ARCHITECT_MODEL` points to a model capable of following role-specific instructions
- [ ] Ollama endpoint reachable from `agent_runtime` container
- [ ] `agents/scratchpad/` directory writable by the runtime process
- [ ] The API streaming endpoint serialises the generator's `yield` dicts as NDJSON (one JSON object per line)
- [ ] The endpoint sets `Content-Type: text/event-stream` or `application/x-ndjson`
- [ ] `request_lock` in `utils/gpu_queue.py` is functional (prevents GPU VRAM saturation from concurrent requests)

### Frontend (hive-ui container)

- [ ] `useSwarmStore` imported wherever the Theatre drawer is rendered
- [ ] `use-chat-stream.ts` handles `swarm_phase`, `swarm_worker_created`, and `swarm_task_list` event types
- [ ] `SwarmDrawer` component mounted in the chat layout (conditionally shown when `active === true`)
- [ ] CSS keyframes and custom properties defined in global stylesheet
- [ ] `useSwarmBroadcast()` called once at layout level if popout support is desired
- [ ] `/swarm` route exists if popout is enabled

### Rebuild vs Restart

| Change Type | Required Action |
|-------------|----------------|
| Python agent logic change | `docker restart agent_runtime` |
| UI component change | `docker compose build hive-ui && docker compose up -d hive-ui` |
| Environment variable change | `docker compose up -d agent_runtime` (or `hive-ui`) |
| New model pulled to Ollama | No restart needed |

---

## 12. Porting to a New Architecture

### What is tightly coupled

1. **The event stream contract** (Section 4) — the only true coupling point. Your coordinator must emit `swarm_phase`, `swarm_worker_created`, and `swarm_task_list` events.

2. **The `SwarmWorker` type** — the shape of worker data must match across backend and frontend. Adding extra fields is safe; removing required fields breaks the badge animation.

3. **Phase numbering** — the `phase_num` field drives the Theatre state machine. Phase 1 → decomposing, 2 → roster, 3 → synthesizing, ≥4 → working. You can have more or fewer phases than 5; the UI handles `phase_num ≥ 4` as generic `working`.

### What is completely replaceable

| Component | Replacement strategy |
|-----------|---------------------|
| Ollama / local LLM | Any OpenAI-compatible API endpoint; update `_decompose_task` and `_synthesize_findings` |
| Agno (Phi) agents | Any agent framework; `_run_worker` only needs `agent.run(prompt)` → `response.content` |
| PostgreSQL / Agno DB | Unused by lamport.py directly; only needed if agents use long-term memory |
| MemPalace client | Fully optional; the `_team_store` / `_team_clear` calls are `try/except` guarded |
| SPIRE / JWT-ACE | Fully optional; `_JWT_AVAILABLE` flag disables the security layer gracefully |
| Zustand | Any state management library; reproduce the `SwarmState` interface and action signatures |
| Next.js | Any React framework; the swarm components are plain React with Tailwind |
| Tailwind CSS | Any CSS approach; replace utility classes with equivalent selectors |

### Minimal Backend Implementation

To reproduce the Theatre experience from scratch, your coordinator only needs to emit these events in order:

```python
# 1. Signal decomposition start
yield {"type": "swarm_phase", "phase_num": 1, "phase_name": "Decompose", "total_phases": 5}

# 2. Spawn workers (one yield per worker)
yield {
    "type": "swarm_worker_created",
    "worker_id": "w-abc123",
    "role": "researcher",
    "pioneer_name": "Shannon",
    "pioneer_full_name": "Claude Shannon",
    "pioneer_motto": "Information is the resolution of uncertainty.",
    "task": "Research topic X",
    "phase": "research",
    "content": "Spawned Shannon (researcher)"
}

# 3. Snapshot updates as workers complete
yield {
    "type": "swarm_task_list",
    "workers": [{"worker_id": "w-abc123", "role": "researcher", "state": "completed", ...}],
    "content": "Shannon completed"
}

# 4. Continue through phases...
```

That is the complete contract. The Theatre will handle all animation, state transitions, and display automatically.

### Minimum Viable Frontend

If you are not using Next.js/React, the Theatre's only UI requirements are:

1. A state machine that tracks the current phase string
2. A FIFO animation queue for incoming workers (badge → roster reveal)
3. CSS for the badge drop-in (`@keyframes id-card-hang`) and scan line (`@keyframes id-scan`)
4. A grid of worker cards that update their status from `swarm_task_list` events

The visual design (frosted glass, role-color theming, pioneer portraits) is entirely aesthetic — any equivalent implementation that conveys agent identity and status fulfills the experience intent.

---

*Guide generated from source: `agents/lamport.py`, `ui/src/lib/stores/swarm-store.ts`, `ui/src/lib/hooks/use-chat-stream.ts`, `ui/src/components/swarm/`, and `MEMEX_GLOSSARY.md`.*
