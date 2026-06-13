# Plan: Swarm-on-DevHarness — unify the multi-agent coordinator onto the dev harness

> Status: proposed. Successor to the Phase 0–4 dev-harness plan. Land Phase 0/1
> of the dev harness first (done: commits `998d714`, `be9d17e`, `abb4dff`).

## Context

Memex has **two** agent engines today, and they don't share a substrate:

1. **Swarm** (`/swarm`, `/build`) — a real, capable multi-agent coordinator:
   - **Team Builder** (`team_builder.py`) assigns a **model per role** (e.g. devops=`qwen3-coder:30b`, coordinator=`gemma4:31b`, researcher=`qwen3.6:27b`).
   - **Decomposer** (`coordination/decomposer.py`) splits a goal into role-tagged subtasks.
   - **Pioneers** (`coordination/pioneers.py`) give research its **"lenses"** — multiple personas that surface converging/diverging viewpoints.
   - **Synthesizer/verifier** (`coordination/synthesizer.py`) combine and check.
   - Workers are **phidata Agents** (`leibniz_agent.py`: `Agent(model=Ollama(...))`, `agent.run()`), with tools from `tools/file_ops.py` (agent_runtime's **host `/workspace`**) and `tools/terminal.py` (the OpenHands-POST terminal). Coding workers also have a **knowledge base** (`CombinedKnowledgeBase`/`PgVector`).

2. **Dev harness** (`dev_mode`, "HiveCode") — the new in-house engine (Phase 0/1):
   - `DevHarness` loop over a provider-neutral history, `ModelRouter` (per-model provider + escalation), the **12-tool** set on the isolated **Docker `dev_sandbox`** (`tools/sandbox_ops.py`: `edit_file`+diff, `glob`, `grep`, `git`, …), a permission gate (plan mode), MAESTRO guard, and `Task` subagents (`main.py::_run_subagent` already runs a **child DevHarness as a worker**).

The split is the problem the dev-harness effort set out to remove: phidata-on-host-fs vs DevHarness-on-sandbox; three tool-calling stacks; coding output landing in two different filesystems.

**Goal:** make the Swarm coordinator run **`DevHarness` instances as its workers** instead of phidata Agents — **without losing any Swarm capability** (per-role models, decomposition, lensed research, synthesis/verify) and **gaining** the unified sandbox, the full dev toolset, escalation, and a path to durability. `Task` and `/swarm` become the **same engine at two scales**: `Task` = one child worker; `/swarm` = the coordinator orchestrating many.

## Key insight

Almost none of Swarm's capability lives in the worker *engine* — it lives in the coordination *layer*. **Keep the coordinator's brain; swap the worker's body.**

A worker today is `phidata Agent.run()` on host `/workspace`. Make a worker a `DevHarness.run()` on `dev_sandbox`. Everything above the worker is untouched.

> Elegant consequence: a `DevHarness` given an **empty toolset is just a reasoning LLM** (a turn with no tool calls returns text). So research/analyst lenses — which produce text, not file edits — are DevHarness workers with `tools=[]`. One worker abstraction subsumes coder, devops, researcher, analyst, verifier; only the **(model, system_prompt, tool_subset)** triple varies per role.

## Capability preservation matrix

| Swarm capability | Lives in | Under unification |
|---|---|---|
| Per-role models (devops=qwen-coder, coord=gemma30b, researcher=qwen27b) | `team_builder.py` | **Unchanged** — the role's model becomes the worker's `ModelRouter` model (provider-neutral, 1:1). Each worker gains escalation for free. |
| Decompose goal → role subtasks | `decomposer.py` | **Unchanged** — output feeds worker construction. |
| Parallel workers | ThreadPool in `executor.py` | Each worker thread runs `asyncio.run(devharness_worker(...))`; GPU placement still via `utils/gpu_queue`. |
| "Lensed" research (converging/diverging) | `pioneers.py` personas | **Unchanged** — a lens *is* the worker's system prompt; each lens is a DevHarness worker (optionally a different model). Lenses can now *ground* viewpoints with `web_fetch`/`read`. |
| Scratchpad coordination | `CoordinatorSession` | **Unchanged** — worker results written to the scratchpad for the synthesizer. |
| Synthesize / verify | `synthesizer.py` / verifier | **Unchanged** — verifier can itself be a read-only DevHarness worker. |
| Coordinator brain (gemma30b) | orchestrator/decomposer/synthesizer LLM | **Unchanged** — no tools, stays a direct LLM call (not a DevHarness). |
| Non-coding roles (researcher/analyst) | plain Ollama agents | DevHarness with a restricted toolset (web + read-only, or none) via the permission gate. |
| Coder knowledge base / RAG | `leibniz_agent` (`CombinedKnowledgeBase`/`PgVector`) | **Preserved as a new `kb_search` tool** — the only net-new piece (see below). |

## The one gap to close for true no-loss: `kb_search`

`leibniz_agent` gives the coder retrieval over a knowledge base. The DevHarness has no RAG. Preserve it by mounting the KB as a **`kb_search(query)` tool**, exactly like `web_search` was mounted (`main.py::_run_mcp_tool` pattern, or a direct sandbox-independent tool). Add it to `DEV_TOOL_DEFINITIONS` and the coder/architect role's `tool_subset`. With this, the coder loses nothing.

## The code change — one seam in `coordination/executor.py`

Replace the worker *construction* and *execution*, keep everything else:

- **`_get_agent_for_role(role, session_id, scope)`** (builds a phidata `Agent`) → **`_build_worker_config(role, scope)`** returning `(model, system_prompt, tool_subset)`:
  - model ← Team Builder / role config (today's source of per-role models)
  - system_prompt ← role instructions (+ pioneer lens for research)
  - tool_subset ← per role: coder/devops = full sandbox set (+`kb_search`); researcher = `web_search`/`web_fetch`/`read_file`/`glob`/`grep`; analyst/verifier = read-only; pure-reasoning lens = `[]`
- **`_run_worker(session, worker_id, agent, prompt)`** → **`_run_worker(session, worker_id, role, scope, prompt)`**:
  - build `History(system=system_prompt, turns=[UserMessage(prompt)])`
  - build `ModelRouter(OllamaProvider(model), escalation_targets)`
  - `result_text, trace = asyncio.run(_devharness_worker(history, tool_subset, router, ...))`
  - push `trace` (agent_events + file_changes) onto the session event queue (generalize `session.file_change_queue`); write `result_text` to the scratchpad — **the same string contract the synthesizer already consumes**.
- **Reuse as-is:** `decomposer.py`, `coordination/session.py` (`CoordinatorSession`, scratchpad, `WorkerState`), `synthesizer.py`, `orchestrator.py`'s flow, `pioneers.py`, `team_builder.py`, `utils/gpu_queue`.

`main.py::_run_subagent` is already a working "DevHarness worker" — generalize it into `coordination/devharness_worker.py` and call it from both `Task` (one worker) and the swarm orchestrator (many workers).

**Files:**
- `agents/coordination/executor.py` — the seam (`_build_worker_config`, `_run_worker` body)
- `agents/coordination/devharness_worker.py` (new) — the shared worker runner (extracted/generalized from `main.py::_run_subagent`)
- `agents/coordination/session.py` — generalize `file_change_queue` → a worker-event queue carrying agent_events + file_changes
- `agents/tools/kb_tool.py` (new) — `kb_search` over the existing KB; schema in `DEV_TOOL_DEFINITIONS`
- `agents/dev_harness/permissions.py` — per-role tool subsets / role profiles
- reuse `decomposer.py`, `synthesizer.py`, `orchestrator.py`, `pioneers.py`, `team_builder.py`, `utils/gpu_queue`

## Risks to manage

1. **Substrate migration** — swarm coding output moves host `/workspace` → `dev_sandbox`. Audit consumers that assume host fs: the design-revision artifact cache (`/workspace/delivered_artifacts/latest_{session_id}.html`), any delivered-artifacts pickup, and the pending **Android build pipeline**. Decide whether swarm output stays host-fs for those flows or the consumers move to the sandbox.
2. **GPU concurrency** — N workers × N models concurrently is VRAM-bound. Keep `utils/gpu_queue` (`get_swarm_worker_host`, GPU lock) serializing/placing model loads; the DevHarness worker must acquire the lock around its provider calls just as phidata workers do today.
3. **SSE framing** — Swarm uses the church named-event pipeline (`swarm_phase`, `swarm_worker_created`, pioneer cards); DevHarness emits OpenAI-chunk deltas. Bridge worker traces via the existing `agent_event` type (already rendered by `agent-trace-card.tsx`); keep the coordinator emitting the swarm-theater events. Drain the worker-event queue between orchestrator future-waits (the existing `file_change_queue` drain pattern).
4. **Per-worker memory** — phidata workers had `PgAgentStorage`. DevHarness workers are single-shot (like `Task`); if persistent worker memory is wanted, it rides on the dev harness's Phase 3 durability, not this plan.
5. **Recursion** — the past crash (phidata pydantic on a shared `session_id`) **disappears** (no phidata). New risk: a worker spawning `Task` → cap worker depth (workers get no `Task` tool, mirroring `_run_subagent`).

## Migration phases (incremental, flagged, reversible)

- **Phase A — coder/devops on the sandbox (highest payoff).** Extract `coordination/devharness_worker.py` from `_run_subagent`. Behind a flag (`SWARM_DEVHARNESS_WORKERS=true`), route `scope==codebase` coder/devops workers through it; everything else stays phidata. Add `kb_search` (host-side). Keep the flag **off by default** until Phase B lands (sandbox output breaks artifacts cache + Android build).
- **Phase B — substrate reconciliation (prerequisite to enabling Phase A in prod).** Repoint the design-revision artifact cache (`/workspace/delivered_artifacts/latest_{session_id}.html`) to a sandbox-relative path (or an explicit host-mount). Wire the Android build pipeline to pull compiled output from the sandbox. Only after both consumers are repointed: flip `SWARM_DEVHARNESS_WORKERS=true` as the default.
- **Phase C — research/analyst lenses.** Move pioneer-lensed research + analyst to DevHarness (web + read-only or `tools=[]`). Keep `pioneers.py` personas as system prompts.
- **Phase D — retire phidata workers.** Remove `_get_agent_for_role` / `leibniz_agent` once all roles are across. Keep `decomposer`/`synthesizer`/`orchestrator`/`session`/`pioneers`/`team_builder`.
- **Phase E (optional) — unify SSE + extend durability** to swarm workers (Phase 3 of the dev-harness plan).

## Verification

1. **Phase A parity:** run the same `/swarm` codebase goal with the flag off (phidata) vs on (DevHarness). Confirm: per-role models still honored; coder edits land in `dev_sandbox` with `edit_file`/diffs/`git`; `kb_search` returns KB hits; synthesizer output is equivalent or better; swarm-theater UX (phases, pioneer cards, agent traces) still renders.
2. **Lensed research (Phase C):** a research `/swarm` query spawns N lensed DevHarness workers (different personas/models); confirm the synthesizer surfaces converging/diverging viewpoints as before, now optionally grounded with web fetches.
3. **GPU:** confirm 3 concurrent workers on different models don't OOM the GPU (gpu_queue serialization holds).
4. **Recursion/limits:** a worker cannot spawn `Task`; depth capped.
5. **Regression:** `Task` (single worker) unaffected; `dev_mode`, `/design`, `/workshop` unaffected; flag-off restores exact current swarm behavior.

## Decisions (locked 2026-06-13)

| Decision | Choice | Implication |
|---|---|---|
| **Swarm coding output** | `dev_sandbox` (full migration) | Phase B must repoint the design-revision artifact cache (`/workspace/delivered_artifacts/latest_{session_id}.html`) and the Android build pipeline before Phase A workers go fully live. Flag Phase A workers off by default until Phase B lands. |
| **Coordinator engine** | Direct LLM (no DevHarness) | `decomposer.py`, `synthesizer.py`, `orchestrator.py` call the LLM directly — no tool loop overhead. This is the existing behavior; no change needed. |
| **`kb_search` placement** | Host-side tool | `agent_runtime` queries `PgVector` on Hopper directly (same network path as the existing `AGNO_DB_URL`). Worker calls it like `web_search` via `_run_mcp_tool` / `ToolHookRegistry`. No sandbox → Hopper network plumbing required. Add schema to `DEV_TOOL_DEFINITIONS` and wire into coder/architect role tool subsets only. |
