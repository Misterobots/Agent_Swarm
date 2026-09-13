# Core backlog: overnight adaptation and training recovery

Date: 2026-09-12
Status: partial local implementation; release and live qualification pending.
No item below is approved to launch training or change a live service.

The backlog is intentionally Core-owned. Desktop work should consume the
contract and preserve native presentation ownership; it must not recreate the
scheduler, lease state, or training state in the renderer.

## Implementation status at 2026-09-13

Completed locally, feature-gated and not enabled in the default runtime:

- `agents/learning_contract.py` provides pure `learning.v1` validation,
  UUID/scope requirements, idempotency fingerprints, conservative status
  transitions, and event envelopes.
- `agents/learning_store.py` provides an explicit, Postgres-backed durable
  foundation for jobs, attempts, events, and idempotency. It is not called at
  startup and has no in-memory production fallback.
- `agents/learning/routes.py` provides capabilities, non-mutating dry-run,
  owner-scoped snapshot queries, and event pages. Job creation is blocked
  unconditionally and advertised unavailable until trusted server-side
  admission is wired; client-supplied eligibility never authorizes a write.
- `agents/main.py` includes the router only when `LEARNING_V1_ENABLED` is
  explicitly enabled; the default deployment surface is unchanged.
- Pure contract/router tests and the existing event-contract regression tests
  pass.
- `agents/learning_resources.py` now provides pure resource admission that
  rejects unknown/protected GPUs, host mismatches, stale telemetry,
  unallowlisted consumers, disabled lanes, and insufficient measured memory;
  it performs no hardware or host operations.

Still blocked by required discovery/qualification: OA-001 GPU and SaltMedia
isolation, OA-003 schema ownership and migration boundary, real resource
admission, worker execution, checkpoint/resume, MemPalace eligibility/outbox,
legacy route adaptation, desktop integration, and live/overnight qualification.

The [2026-09-13 check-in review](../evidence/overnight-learning-check-in-2026-09-13.md)
records open persistence, replay, and authentication integration findings.
OA-010 acceptance is not complete; passing pure/router tests does not establish
Postgres concurrency, restart recovery, or contract parity.

## P0 — safety and inventory gate

### OA-001 — Resource ownership manifest

Inspect the authorized Memex hosts, card UUIDs, host RAM/disk budgets, process
and model consumers, artifact roots, credentials, and network endpoints.
Record an allowlist and an explicit SaltMedia denylist. Unknown host/card
ownership is `ineligible`, not `available`.

Acceptance: a dry-run admission test rejects a protected or unknown target
before any eviction, process launch, mount, or network write. No SSH to
Lovelace is assumed; the test must use only already-authorized access.

### OA-002 — Core/desktop route and feature map

Inventory every current Training control, catalog/history/voice feature,
Mission Control panel/action, and native desktop destination. Trace the
installed desktop's actual navigation separately from the hosted web route.

Acceptance: the map names the authoritative owner of every feature, proves
every pre-existing feature remains reachable, and identifies any broad
maintenance shortcut that must be Memex-scoped.

### OA-003 — Existing schema ownership and compatibility boundary

Identify the authorized owner and migration history for the existing
`swarm.training_runs`, `swarm.model_versions`, and `swarm.ab_tests` tables.
Choose whether `learning.v1` adds new durable tables beside them or uses a
documented compatibility adapter. This is a source/authorization discovery
task first; it does not authorize live database writes.

Acceptance: the selected boundary has an additive migration plan, maps legacy
numeric run IDs to UUID jobs, names the schema owner, and prevents the legacy
API from maintaining a second job state machine.

## P1 — durable execution foundation

### OA-010 — Durable job, attempt, and event store

Add additive schema/migrations for `learning_jobs`, `learning_attempts`,
`learning_events`, `learning_schedules`, and `learning_idempotency`. Use UUID
job/experiment/attempt IDs, owner/workspace/project/session scope, immutable
recipe/model/dataset revisions, phase/status, budgets, heartbeats, and event
sequence numbers.

Acceptance: API restart, duplicate delivery, and concurrent launch requests
produce one logical job; snapshot and event replay reconstruct the same state.

### OA-011 — Dedicated worker/supervisor

Move execution outside the interactive API process. The worker claims a job
with a fencing generation, emits heartbeats, owns a bounded process tree, and
commits a phase output manifest before advancing. Keep a local append-only
journal for temporary database outages.

Acceptance: killing the API does not kill the job; killing the worker creates a
new attempt that resumes or safely pauses; an expired lease cannot permit the
old worker to write after reassignment.

### OA-012 — Launcher contract repair

Consolidate `/train` and `/v1/training/start` behind the durable launcher.
Repair the `evict`/`evict_inference` mismatch, make dry-run strictly
non-mutating, perform ownership/admission before eviction, and require
idempotency keys for launch and controls.

Acceptance: unit and integration tests cover dry-run, duplicate launch,
already-running jobs, invalid recipe/model/dataset, cancellation, and restart
reattachment. Existing legacy endpoints either adapt to `learning.v1` or
return a structured unsupported response; they do not maintain a second state
machine.

### OA-013 — Checkpoint and watchdog protocol

Implement atomic checkpoint manifests with temporary write, checksum and
validation, then publish. Include model/tokenizer/recipe/dataset hashes,
optimizer/scheduler/RNG/sampler state, step/epoch, framework/container
versions, and source attempt. Add separate deadlines for preparation,
download, model load, each step/generation, checkpoint, evaluation, export,
and shutdown.

Acceptance: at least two valid checkpoints exist; an interrupted/corrupt latest
checkpoint falls back to the previous valid one; a worker resumes with the
recorded step/optimizer/data position rather than starting a new run.

## P1 — resource and data safety

### OA-020 — Fenced per-GPU leases

Replace the single in-memory mutex with durable per-UUID leases containing
holder, job/attempt, host, expiry, desired inference state, and monotonically
increasing fencing generation. Measure per-device free memory and all known
consumers. Remove index/most-free fallback.

Acceptance: unknown UUID, missing telemetry, protected consumer, or failed
restore blocks admission. A stale worker cannot renew or release a newer
generation. Release restores only recorded, still-authorized Memex inference.

### OA-021 — MemPalace eligibility and outbox

Add owner/workspace/project/session-scoped observation and extraction lineage;
training eligibility (`recall_only`, `approved_example`, `evaluation_only`,
`excluded`, `revoked`); source-run and Pioneer references; extraction version;
and idempotent outbox delivery. Enforce owner scope at the boundary rather than
falling back to broad search.

Acceptance: replay produces no duplicate memory or outbox effect; omitted or
cross-owner scope is rejected; MemPalace outage does not destroy an immutable
dataset snapshot; revocation invalidates future snapshots and identifies
already-trained candidates for retirement/retraining.

### OA-022 — Dataset manifest builder

Build examples from task, relevant context, actions, and verified outcome.
Preserve successful/failed alternatives where preference learning is valid.
Strip secrets/private exclusions, record licenses, hash all inputs and
transformations, and group task families before train/eval splitting.

Acceptance: a bounded snapshot has deterministic hashes, source memory IDs and
revisions, source run IDs, split IDs, eligibility decisions, reward version,
and no train/eval near-duplicate leakage.

## P1 — evaluation and model lifecycle

### OA-030 — Task-verifier reward path

Disable the length/code-marker callback for production adaptation. Implement
independent verifiers for coding, tool/routing, recovery, design, and research
tasks. Treat judge-model scores as evidence, not sole promotion authority.

Acceptance: a correct short task result beats a long code-looking incorrect
answer; prohibited-path or invalid-tool behavior fails; evaluator fixtures are
held out from proposal generation, retrieval, training, and reward tuning.

### OA-031 — Adaptation proposal and rejection ledger

Persist observation, hypothesis, baseline, exact change, target metric,
approval state, evaluation report, rollback reference, and proposal fingerprint.
Record rejected and insufficient-evidence outcomes, not just winners.

Acceptance: harness and model experiments change one factor in the initial
pilot; repeated runs can identify the exact artifact and evidence window that
caused a decision.

### OA-032 — Candidate evaluation, promotion, rollback

Track base, current production, and candidate with identical harness settings.
Keep `completed` training separate from `promoted` production. Require fresh
tasks, correctness gates, regression checks, explicit review, and a reversible
promotion/rollback record.

Acceptance: a regression rejects the candidate and leaves production unchanged;
promotion records evaluation and provenance; rollback restores the previous
known-good model without broad service operations.

## P2 — bounded scheduling and shared surfaces

### OA-040 — Timezone-aware overnight scheduler

Persist schedules in `America/Chicago` (initial proposed window 00:00–06:00),
with DST-aware next-run calculation, 30-minute drain, phase budgets, retry
budgets, and pause/resume across nights. Duplicate schedule delivery maps to
one job idempotency key.

Acceptance: end-of-window drains at a safe boundary, checkpoints, releases
leases, restores allowed Memex inference, and reports the actual checkpoint age
and reason. No eligible work produces a clear skip, not a fake success.

### OA-041 — Training home modernization

Use the existing Training home as canonical. Add tonight's plan, readiness,
eligible lanes/budgets, active and queued jobs, real phase progress, checkpoint
age, retry/block reason, provenance, artifacts, and morning report. Preserve
Launch, History, Model Catalog, and Voice Calibration routes.

Acceptance: loading, empty, stale, disconnected, queued, paused, retrying,
failed, and completed states are distinct; failed requests never become zero
counts or healthy idle; deep links carry job ID and selected view.

### OA-042 — Mission Control organization

Retain current Fleet, Memory, Service Health, Action Queue, and useful
shortcuts. Reorganize the overview around attention required, active work,
next work, and recent results, with links to authoritative Training,
evaluation, memory, and Pioneer details. Move secondary launch shortcuts to a
clearly labeled tools area and restrict maintenance actions to Memex
allowlists.

Acceptance: no existing feature disappears, and every actionable issue shows
cause, affected resource/job, current recovery action, and a detail link.

### OA-043 — Desktop adapters and reconnect

Desktop consumes `learning.v1` through typed adapters. Native presentation owns
layout, shell, and navigation; Core owns the shared contract and web surfaces.
Reconnect by job ID and event cursor after close/reopen, auth refresh, API
restart, or stream loss. Model Arena remains comparative evaluation, not a
duplicate scheduler.

Acceptance: visible installed-desktop tests prove schedule editing, launch,
progress, pause/resume/cancel acknowledgement, checkpoint inspection, result
review, deep linking, back navigation, and no duplicate events or side
effects.

## P2 — qualification and IFM

### OA-050 — Recoverable adapter pilot

Run only after OA-001 through OA-030 gates pass. Use a supported 3–4B model and
one verified eligible 16 GB lane. Interrupt the worker, resume, evaluate, and
restore inference. Measure peak memory rather than assuming fit.

Acceptance: API remains responsive; resumed optimizer/step state is proven;
artifacts and lineage are complete; protected resources are unchanged.

### OA-051 — Progressive overnight qualification

Qualify one hour, one full window, then three consecutive full windows with a
planned recoverable failure. Enable the second 16 GB lane and then an eligible
8 GB lane only after separate admission evidence.

Acceptance: each run completes or pauses intentionally with valid checkpoint,
report, released lease, and restored Memex inference. No unexplained loss or
duplicate work.

### OA-052 — IFM comparative evaluation

Recheck K2 model cards, licenses, tokenizer/template, architecture,
quantization, tool behavior, and trainer compatibility. Recheck `xllm` and
`horizon-post-train` for executable code before adapter integration. Use only
bounded TxT360-v2 samples with provenance and a distinct continued-pretraining
experiment when justified.

Acceptance: IFM is a reproducible comparison artifact or is explicitly
deferred with evidence; no placeholder repository is treated as an available
algorithm, and no large-model or distributed-training claim is made from the
pilot.

## Dependency order

`OA-001/OA-002/OA-003 → OA-010/OA-012 → OA-011/OA-013/OA-020 → OA-021/OA-022 →
OA-030/OA-031/OA-032 → OA-040/OA-041/OA-042/OA-043 → OA-050 → OA-051 → OA-052`.

The desktop may build test-only adapters against frozen fixtures after the
contract is approved, but it may not expose live controls until durable server
acknowledgements and recovery evidence exist.

## Deployment and qualification work still outstanding

- Identify and verify the physical GPU UUID/host ownership and SaltMedia
  isolation. Do not claim the reported 8/16/16 GB mapping is deployment truth.
- Select the durable database/schema migration boundary and worker deployment
  boundary without changing live services in the planning task.
- Decide the authoritative compatibility adapter for existing training APIs.
- Run fault-injection, pilot, desktop visual/interaction, and overnight gates.
- Recheck IFM public sources and record exact revisions before downloading or
  training anything.
