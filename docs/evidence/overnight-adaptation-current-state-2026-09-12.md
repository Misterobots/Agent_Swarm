# Overnight adaptation current-state evidence

Inventory date: 2026-09-12
Scope: source-only inspection of this Memex_Core checkout, the sibling
Agent_Swarm checkout, MemPalace source, and the Memex Desktop source. No live
service, container, scheduler, GPU, database, or deployment state was changed.

This is an evidence supplement to:

- [`overnight-adaptation-core-reference.md`](../governance/overnight-adaptation-core-reference.md)
- [`overnight-adaptation-backlog.md`](../governance/overnight-adaptation-backlog.md)
- [`overnight-learning-v1.md`](../specs/overnight-learning-v1.md)

## Backend route inventory

| Surface | Current source evidence | Finding for `learning.v1` |
|---|---|---|
| Dispatcher execution | `agents/training/dispatcher.py:187-374` | Separate `/train`, `/jobs`, `/train/{job_id}`, and delete control path; `_jobs` and `Popen` state are process-local. |
| Primary training facade | `agents/main.py:4291-4770` | `/v1/training/status`, history, curated datasets, scan, start, cancel, live metrics, and report; start/cancel are backed by `_active_training` and an API-process background task. |
| Conversion/deployment | `agents/main.py:5143-5300` | Conversion reuses `_active_training`; deployment starts A/B activity through legacy numeric run IDs. These must become job/attempt-compatible adapters. |
| Secondary read/catalog family | `agents/main.py:6752-6785` and `ui/src/lib/api/training.ts` | `/api/v1/training/runs` and `/api/v1/training/catalog` coexist with `/v1/training/runs`; the contract needs one authoritative source and explicit legacy aliases. |
| UI failure semantics | `ui/src/lib/api/training.ts:6-35, 318-327` | Several helpers convert transport/API errors into empty arrays, zero counters, or null; this violates the required disconnected/stale/error distinction. |
| Existing UI ownership | `ui/src/app/training/*`, `ui/src/app/mission-control/page.tsx` | Core owns shared web Training and Mission Control surfaces. Training already has Overview, Run History, Launch, Models, and Voice. Mission Control has Overview, Fleet, Agents, Memory, Service Health, and Action Queue. |

### Current training control implications

The current `/v1/training/cancel` implementation resets the in-memory guard and
marks the database row as failed; it does not prove that the underlying task or
process tree stopped. The `learning.v1` adapter must therefore acknowledge a
durable control command and report actual worker/attempt state rather than
wrapping this behavior as a successful cancellation.

The current live endpoint combines Prometheus gauges with a database heartbeat.
That is useful telemetry, but it is not a reconnectable event log: the new
contract needs durable event sequence numbers plus a snapshot cursor.

## Mission Control safety inventory

The current page is more than a dashboard:

- `ui/src/app/mission-control/page.tsx:65-70` defines Fleet, Agents, Memory,
  Service Health, and Action Queue tabs.
- `ui/src/app/mission-control/page.tsx:78-126` defines maintenance, memory,
  research, and build shortcuts.
- `ui/src/app/mission-control/page.tsx:272-280` runs admin/maintenance/update
  tasks inline in Mission Control.
- `ui/src/components/mission-control/fleet-panel.tsx` describes controls for
  administering containers across the cluster and force-clearing the GPU lock.
- `ui/src/lib/api/ops.ts:109-132` exposes container restart and GPU lock-clear
  helpers.

This is a hard prerequisite for OA-001/OA-042. Learning controls cannot share
the broad fleet action path or inherit its target scope. The future resource
and control adapters must reject SaltMedia nodes, services, containers,
networks, mounts, credentials, and unknown GPU ownership before any action is
accepted.

## MemPalace contract inventory

| Capability | Current source evidence | Current boundary |
|---|---|---|
| Memory write | `control_plane/mempalace/app/main.py:298-328` | `owner_id` is required; owner/team/agent metadata is persisted. |
| Semantic search | `control_plane/mempalace/app/main.py:332-367` | Optional owner/agent/team/type/domain filters exist; a training snapshot needs a mandatory authorized scope. |
| Synchronous extraction | `control_plane/mempalace/app/main.py:477-520` | Owner required; writes memories and an extraction log. No training eligibility decision. |
| Queued extraction | `control_plane/mempalace/app/main.py:522-551` | Durable pending row includes owner, agent, team, source device, and timestamps. No idempotency/source-run key. |
| Pending processing | `control_plane/mempalace/app/main.py:594-662` | Processes unprocessed rows and retries failed rows on a later cycle. No dataset-manifest or revocation linkage. |
| Database model | `control_plane/mempalace/app/database.py:218-258` | `ExtractionLog` and `PendingExtraction` exist; migrations currently stop at `0004_pending_extractions`. |

The current service is a useful foundation for the proposed outbox, but the
training layer still needs separate eligibility, lineage, immutable snapshot,
revocation, and replay/idempotency records. It must not treat every queued
conversation or memory as training data.

## Desktop ownership and route inventory

| Desktop surface | Current source evidence | Verified ownership |
|---|---|---|
| Native top-level tabs | `src/types/memex.ts:1`, `src/components/layout/TabBar.tsx:19-20, 103-106` | Native shell exposes chat/code experiences and `Eval`; no Training or Mission Control tab exists. |
| Native rendering | `src/components/layout/AppShell.tsx:13, 64-77` | `EvalBenchView` is native; there is no native Training/Mission Control component in the shell. |
| Model Arena | `src/components/views/EvalBenchView.tsx`, `electron/eval-store.ts` | Desktop-owned comparative evaluation store/view. It should link to Core candidates, not own scheduler state. |
| Hosted browser | `src/components/views/BrowserView.tsx`, `src/components/views/DevView.tsx:269-320` | Hosted site is embedded as a native BrowserView inside the Dev project-tools pane, not as a Training/Mission Control route. |
| Runtime profiles | `electron/config-store.ts:90-125`, `src/lib/runtime-urls.ts:16-70` | Desktop can target hosted Memex, Home LAN, or localhost profiles. Core controls must be capability-discovered per active profile. |

Therefore, “desktop integration” is not currently a route rename. It is a
coordination task: Core publishes the durable contract and shared web pages;
desktop adds typed adapters and native presentation only after the server
advertises capabilities and durable acknowledgements.

## Schema and persistence gap

Core contains references to `swarm.training_runs`, `swarm.model_versions`, and
`swarm.ab_tests` in `agents/training/*` and `agents/main.py`, but the inspected
Core migration tree contains only MemPalace Alembic migrations. The owning
location, migration history, and deployed schema for the `swarm` tables were
not established by this source-only inventory.

This is a release-blocking discovery item, not permission to inspect or modify
the live database. OA-010 must first identify the authorized schema owner and
choose additive durable learning tables or a documented compatibility layer.

## Revised immediate sequence

1. Complete OA-001 resource ownership and isolation manifest without claiming
   idle GPUs.
2. Complete OA-002 feature/route map and obtain Core/desktop ownership signoff.
3. Identify the authorized owner of the existing `swarm` schema and choose the
   additive persistence boundary.
4. Specify the compatibility adapter from legacy numeric runs and legacy
   controls to `learning.v1`.
5. Only then implement the durable store, worker, lease, and UI adapters.
