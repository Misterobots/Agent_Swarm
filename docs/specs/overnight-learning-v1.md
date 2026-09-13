# Overnight learning API and event contract v1

Status: proposed contract for coordination with Memex Desktop and the shared
Core web surfaces. No endpoint in this document is implemented merely because
it is specified.

## Contract rules

- Media type: `application/vnd.memex.learning+json; version=1` for JSON
  responses. Events use `schema: "learning.event.v1"`.
- All identifiers are opaque UUIDs. `job_id` identifies one durable logical
  execution; `experiment_id` identifies the hypothesis/recipe comparison;
  `attempt_id` identifies one worker attempt; `checkpoint_id` identifies one
  validated checkpoint; `event_seq` is a monotonically increasing integer per
  job.
- Every request is owner-scoped. The server derives the authenticated owner;
  a supplied owner/workspace/project/session must match authorization. Omitted
  owner scope never means global search.
- `Idempotency-Key` is required for mutating launch and control requests. The
  server stores the key, request fingerprint, resulting status, and response
  for at least the job's retention period. Reusing a key with a different
  fingerprint returns `409 idempotency_conflict`.
- A successful control response means the command was durably accepted, not
  that the phase has already changed. The subsequent event/snapshot is the
  source of truth.

## Resource model

```json
{
  "schema": "learning.job.v1",
  "job_id": "uuid",
  "experiment_id": "uuid",
  "owner_id": "opaque-owner",
  "workspace_id": "workspace",
  "project_id": "project",
  "session_id": "session",
  "parent_id": "uuid-or-null",
  "worker_id": "uuid-or-null",
  "kind": "sft|preference|rl|harness_adaptation|dataset_prepare|evaluation|export",
  "status": "queued",
  "phase": "queued",
  "attempt": {"attempt_id": "uuid", "number": 1, "status": "pending"},
  "recipe": {"revision": "sha256:...", "method": "verified_sft"},
  "model": {"base_revision": "sha256:...", "tokenizer_revision": "sha256:..."},
  "dataset": {"manifest_id": "uuid", "revision": "sha256:..."},
  "schedule": {"schedule_id": "uuid-or-null", "timezone": "America/Chicago"},
  "resource": {
    "eligibility": "pending|eligible|ineligible|blocked",
    "gpu_uuid": "gpu-uuid-or-null",
    "host_id": "memex-host-or-null",
    "lease_generation": 0
  },
  "progress": {"unit": "step", "current": 0, "total": null},
  "checkpoint": {"latest_id": null, "age_sec": null, "recovery_point": null},
  "retry": {"used": 0, "max": 2, "next_at": null, "reason": null},
  "freshness": {"observed_at": "RFC3339", "heartbeat_at": null},
  "blocking_reason": null,
  "provenance": {"source_run_ids": [], "memory_ids": [], "pioneer_ids": []},
  "evaluation": {"report_id": null, "decision": "pending"},
  "candidate": {"candidate_id": null, "state": "none"},
  "created_at": "RFC3339",
  "updated_at": "RFC3339"
}
```

### Status and phase

`status` is the durable lifecycle: `queued`, `running`, `paused`,
`retry_wait`, `blocked`, `failed`, `cancelled`, or `completed`.

`phase` is operational detail: `queued`, `preflight`, `preparing`,
`training`, `checkpointing`, `evaluating`, `exporting`, `awaiting_review`,
`restoring`, or `done`.

`completed` means the requested work completed. It does not mean a candidate
was promoted. Promotion is a separate candidate state: `none`, `candidate`,
`evaluating`, `accepted`, `promoted`, `rejected`, `retired`, or `rolled_back`.

## Endpoints

The proposed prefix is `/api/v1/learning`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/capabilities` | Contract version, supported job kinds, control capabilities, server revision |
| `GET` | `/jobs` | Owner-scoped cursor-paginated history with filters for status, phase, project, and candidate state |
| `POST` | `/jobs` | Create one durable job; supports `dry_run=true`, which must not acquire/evict/launch |
| `GET` | `/jobs/{job_id}` | Authoritative snapshot, including attempt, checkpoint, lease eligibility, provenance, evaluation, and freshness |
| `GET` | `/jobs/{job_id}/events?after_seq=N&limit=...` | Resumable ordered event page; returns `next_after_seq` and `has_more` |
| `POST` | `/jobs/{job_id}/controls` | Idempotent `pause`, `resume`, `cancel`, `retry`, or `reconcile` command |
| `GET` | `/schedules` | Owner-scoped schedules and next-run calculations |
| `POST`/`PATCH` | `/schedules` or `/schedules/{schedule_id}` | Create or edit timezone-aware bounded schedules |
| `GET` | `/resources` | Memex-only GPU eligibility, measured telemetry freshness, lease generation, and blocking reason; never exposes protected targets as claimable |
| `GET` | `/experiments/{experiment_id}` | Hypothesis, proposal fingerprint, baseline, evidence, evaluation and rejection ledger |
| `POST` | `/candidates/{candidate_id}/promotion` | Explicit review-backed promote or reject decision with rollback reference |

### Job creation request

```json
{
  "experiment_id": "uuid-or-null",
  "kind": "sft",
  "workspace_id": "workspace",
  "project_id": "project",
  "session_id": "session",
  "parent_id": null,
  "recipe_revision": "sha256:...",
  "base_model_revision": "sha256:...",
  "dataset_manifest_id": "uuid",
  "schedule_id": "uuid-or-null",
  "budgets": {
    "window_timezone": "America/Chicago",
    "deadline_at": "RFC3339-or-null",
    "max_wall_clock_sec": 3600,
    "max_retries": 2,
    "checkpoint_target_sec": 300
  },
  "resource_policy": {"allowed_gpu_uuids": ["uuid"], "allow_8gb": false},
  "dry_run": true
}
```

The response is `202 Accepted` for a durable queued job or `200 OK` for a
non-mutating dry-run admission report. A dry run returns the checks and would-
be resource plan but no job, lease, eviction, worker, or outbox effect.

## Control semantics

```json
{
  "action": "pause",
  "expected_version": 12,
  "reason": "end_of_window",
  "requested_by": "authenticated-owner"
}
```

The acknowledgement contains `control_id`, `job_id`, `accepted_at`,
`observed_version`, and `state_url`. A stale `expected_version` returns `409
state_conflict` with the current snapshot. `cancel` means the supervisor stops
only the owned process tree, persists cancellation, releases the fenced lease,
and attempts Memex inference restoration. It never means “clear an in-memory
flag.” `retry` creates a new attempt under the same logical job and records the
error classification; incompatible recipe/model changes require a new
experiment.

## Event envelope and reconnect

```json
{
  "schema": "learning.event.v1",
  "event_id": "uuid",
  "job_id": "uuid",
  "experiment_id": "uuid",
  "attempt_id": "uuid-or-null",
  "event_seq": 42,
  "kind": "phase_changed|progress|heartbeat|checkpoint_published|retry_scheduled|resource_changed|evaluation_recorded|candidate_changed|control_ack|job_finished|job_blocked|error",
  "phase": "training",
  "occurred_at": "RFC3339",
  "payload": {},
  "freshness": {"source": "worker|supervisor|database", "observed_at": "RFC3339"}
}
```

The snapshot is authoritative if an event page is compacted. A client reconnects
by fetching the snapshot, then requesting events with `after_seq` equal to the
last applied sequence. Events with a sequence at or below the cursor are
ignored. The client must surface a cursor gap as `stale_recovery_required`,
refetch the snapshot, and resume from the returned cursor. Duplicate events
must not create duplicate jobs, controls, notifications, or side effects.

## Errors and freshness

Errors use a stable envelope:

```json
{
  "error": {
    "code": "resource_ineligible",
    "message": "GPU ownership is not verified",
    "retryable": false,
    "job_id": "uuid-or-null",
    "attempt_id": "uuid-or-null",
    "details": {"gpu_uuid": "...", "reason": "unknown_owner"}
  }
}
```

Clients distinguish `empty` (valid zero results), `disconnected` (transport
failure), `stale` (last observation exceeds the freshness policy), `blocked`
(known reason), and `failed` (terminal job error). Failed fetches must never
become a zero count or healthy idle state.

## Provenance, evaluation, and promotion

Dataset manifests reference owner/workspace/project/session scope, memory IDs
and revisions, source-run IDs, Pioneer parent/child IDs, eligibility and
revocation decisions, source licenses, transformation/reward versions, split
IDs, and content hashes. A job cannot enter `training` without an immutable
manifest revision.

Evaluation reports include base/current-production/candidate identifiers,
identical harness/recipe references, task-suite and held-out-set revisions,
verifier results, judge evidence (if any), regressions, artifact references,
and a decision. A judge score alone cannot authorize promotion. Promotion and
rollback are explicit, idempotent control records; a completed job may still
have a rejected candidate.

## Compatibility and ownership

- Existing `/v1/training/status`, `/v1/training/runs`, `/v1/training/start`,
  `/v1/training/cancel`, live/report, convert, and deploy routes may be kept as
  compatibility adapters during migration. They must read the durable model
  and must not own a parallel `_active_training` state machine.
- Existing numeric database run IDs can be exposed as `legacy_run_id` while
  new clients use UUID `job_id`.
- Older servers that do not advertise `learning.v1` must make live controls
  unavailable with `unsupported_capability`; fixture-backed UI may be used only
  when visibly labeled test-only.
- Core owns this shared contract, the durable backend, worker/resource/data
  safety, and shared web Training/Mission Control surfaces. Desktop owns native
  shell/integration/presentation and consumes the contract through typed
  adapters. Model Arena owns comparative evaluation and links to candidates;
  it does not create a second scheduler or job store.
