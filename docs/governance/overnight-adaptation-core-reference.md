# Core reference: overnight adaptation and recovery

Date: 2026-09-12
Status: planning and read-only inventory only. This document authorizes no
training, deployment, scheduler enablement, service restart, or resource
claim.

## Source handoff

The shared requirements remain in the desktop repository. This Core-owned
reference records the exact source files used for this handoff so later edits
can detect drift:

| Source | SHA-256 at inventory | Role |
|---|---|---|
| `C:\Users\panca\Documents\Github\memex-desktop\OVERNIGHT_ADAPTATION_PLAN.md` | `5D475376300FDE6125CE9ECAB69D34FDC808EE344ABA78259CC1EEFFABB53347` | Shared requirements, safety boundary, recovery design, qualification gates, IFM assessment |
| `C:\Users\panca\Documents\Github\memex-desktop\DESKTOP_LEARNING_UI_PLAN.md` | `DF83664C0A085CD25ACD667606CBC0BE517EE600FADB26A3E8E8EB52F9078081` | Desktop ownership, UI acceptance evidence, Core/desktop split |

The desktop work log explicitly assigns Core the overnight infrastructure,
training recovery, MemPalace data integration, GPU scheduling, adaptation
experiments, IFM support, and the shared API/event contract. Desktop retains
native shell/integration and presentation work. The desktop files remain the
planning source; this file is the Core-owned reference, not a replacement for
them.

## Non-negotiable boundary

SaltMedia is out of scope and must not be interrupted, modified, or affected.
Training workers and supervisors must use explicit Memex allowlists for
service IDs, GPU UUIDs, artifact roots, endpoints, credentials, mounts, and
networks. Unknown ownership is ineligible. No automatic host reboot,
Docker/WSL restart, global prune, driver change, broad process termination,
whole-stack restart, unrestricted Docker socket, or media-resource eviction is
allowed. If the 8 GB GPU cannot be proven isolated from SaltMedia, its lane is
disabled. The three reported cards are separate 8 GB, 16 GB, and 16 GB
resources, never a single 40 GB training device.

## Verified Core baseline

These findings are from source inspection in this checkout and the sibling
Agent_Swarm checkout. They are not claims about the currently deployed
services.

### Training execution

- `agents/training/dispatcher.py` owns a separate `/train` subprocess path,
  but jobs are held in `_jobs: Dict[str, TrainingJob]`; the process handle and
  status disappear with the dispatcher process.
- The dispatcher calls `run_preflight(..., evict_inference=True)` while
  `agents/training/preflight.py` accepts `evict`, not `evict_inference`.
- Dispatcher preflight happens before the `dry_run` branch, and eviction is
  part of preflight. A dry run is therefore not guaranteed to be
  non-mutating. The already-running check also occurs after preflight.
- `agents/main.py` exposes a second `/v1/training/start` path using
  `_active_training` and an asyncio background task. Startup cleanup marks
  database rows failed, but does not reattach a worker or resume a checkpoint.
- `grpo_trainer.py` creates a timestamped run directory and uses step saves
  for time-bounded runs, but calls `trainer.train()` without a
  `resume_from_checkpoint` decision. Checkpoint files alone do not provide
  recovery semantics.
- The active GRPO callback scores completion length and code-like markers.
  The separate `MarsRewardFunction` exists and is unit-tested, but it is not
  the callback reward that drives the current trainer.
- The time-budget callback starts after model loading. Download, model load,
  conversion, hung-step, and shutdown deadlines are not separate contracts.

### Resources and leases

- `preflight.py` estimates free VRAM by summing total device memory and
  subtracting Ollama `/api/ps` usage. It can fall back to an assumed 32 GB
  total and does not measure per-device free memory or all consumers.
- `_evict_inference_model()` sends `keep_alive=0` to every model returned by
  Ollama rather than restoring only an explicitly recorded Memex state.
- `agents/api/gpu_lock.py` is an in-memory single mutex with optional secret,
  TTL expiry, and lock IDs. It has no durable lease, GPU UUID, fencing
  generation, process ownership proof, or per-card capacity model.
- `agents/gpu_allocator.py` uses NVML when available but falls back to GPU 0
  if NVML is unavailable and, when no card meets the minimum, deliberately
  selects the card with the most free memory. That fallback is incompatible
  with fail-closed SaltMedia protection.

### MemPalace and data

- MemPalace requires `owner_id` for memory writes and extraction. Search accepts
  owner, agent, team, type, and domain filters.
- `POST /v1/extract/queue` writes a durable `pending_extractions` row, and
  `POST /v1/extract/process_pending` drains it later. The queue has owner,
  agent, team, source-device, and timestamps, but it is not yet a training
  eligibility/outbox/dataset snapshot contract.
- Current extraction and memory APIs do not establish the proposed
  recall-only / approved-example / evaluation-only / excluded / revoked
  training classification, grouped splits, immutable manifests, or model
  lineage.

### Shared and desktop surfaces

- Core contains the shared web routes `/training`, `/training/launch`,
  `/training/runs`, `/training/models`, `/training/voice`, and
  `/mission-control`.
- The Training home currently exposes Launch Run, Run History, Model Catalog,
  Voice Calibration, and three numeric snapshot counters. Its API helpers
  convert failed requests into empty arrays or zero-like fallback state.
- The backend already exposes status/history/live/report/convert/deploy
  endpoints, but the types only model short-lived statuses (`pending`,
  `running`, `completed`, `failed`) and numeric run IDs.
- The installed desktop's native `AppTab` set contains `eval` (its local Model
  Arena), but no Training or Mission Control tab. `AppShell` renders
  `EvalBenchView` natively; `BrowserView` separately opens the hosted
  `https://memex.shivelymedia.com` surface. This does not prove that the
  installed desktop currently presents Core's Training or Mission Control
  pages through a native route.

## Proposed direction

1. Make one durable Core job model authoritative; adapt both current training
   launch paths to it, then retire their independent in-memory state.
2. Keep the interactive API as a control/query facade. A separate Memex-owned
   worker/supervisor owns execution, checkpoints, leases, watchdogs, recovery,
   and restoration.
3. Add owner/workspace/project/session-scoped observations, eligibility,
   immutable dataset manifests, an idempotent MemPalace outbox, and lineage
   through candidate evaluation and promotion.
4. Replace proxy rewards with task verifiers. Start with verified SFT, then
   preference training, and only later bounded RL when verifiers and rollout
   budgets are proven.
5. Add UUID-based GPU eligibility and fencing. Never infer ownership from
   idleness, index, or a successful telemetry call.
6. Publish the contract in
   [`docs/specs/overnight-learning-v1.md`](../specs/overnight-learning-v1.md)
   for the desktop and shared web surfaces. UI controls remain server-backed;
   closing the UI cannot own, cancel, or duplicate a job.

## Explicitly not verified in this inventory

- Current physical host/card mapping, immutable GPU UUIDs, or SaltMedia
  isolation of the 8 GB lane.
- Current live scheduler configuration, worker deployment, model consumers,
  artifact quotas, runtime versions, or whether any overnight job is enabled.
- Installed desktop production route behavior, authentication state, and
  visual usability at the required window sizes.
- A passing real adapter pilot, checkpoint resume, resource restoration, or
  overnight qualification run.
- Executable IFM `xllm` or `horizon-post-train` algorithms. The handoff's
  2026-09-12 assessment found placeholder repositories; recheck before any
  backend integration. TxT360-v2 must be sampled only under bounded,
  provenance-preserving limits.
