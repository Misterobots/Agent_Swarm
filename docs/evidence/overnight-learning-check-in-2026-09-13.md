# Overnight learning foundation check-in

Date: 2026-09-13

Disposition: local foundation checkpoint; not ready to enable job creation or
deploy for training. The router is disabled by default. Even when explicitly
included, creation returns 409 and capabilities advertise create_job=false.

## Corrections made during review

- Removed client-controlled resource eligibility as authorization to write a
  job. A regression test proves a claimed eligible resource cannot open the store.
- Resolve authentication before store access and exception translation on read
  routes, preserving 401 for unauthenticated snapshot and event requests.
- Reject non-boolean GPU enablement values (including the string "false") and
  missing or malformed consumer inventories. A request cannot lower the
  manifest's minimum free-memory floor.

## Open findings before enablement

1. **P1: concurrent idempotent creation is not serialized for a new key.**
   `LearningStore.create_job` selects an idempotency record FOR UPDATE, but
   when the key is absent neither transaction locks a record. Two concurrent
   callers can both proceed; the loser receives a uniqueness error rather
   than replaying the winning response. Reserve the owner/key atomically
   before inserting a job and test identical and conflicting concurrent
   requests against an isolated Postgres database. HTTP creation is blocked,
   so this is currently a latent store defect.

2. **P1: accepted budgets are not persisted.** The request model accepts budgets,
   and the creation snapshot can contain them, but learning_jobs and its INSERT
   omit them. A later read therefore loses deadlines/retry limits. Persist and
   validate budgets in the selected additive migration and prove restart
   round-trips before a worker can consume jobs.

3. **P2: snapshot/event parity is incomplete.** Creation events include
   experiment_id, but stored/replayed events omit it. Snapshots have no event
   cursor. transition_job accepts arbitrary patch fields while its UPDATE
   persists only a subset, so returned snapshots can disagree with subsequent
   reads. Add an explicit mutable-field contract, consistent event metadata,
   and an atomic snapshot cursor; verify reconstruction and restart behavior.

4. **P1 deployment gate: authenticated identity and scope need integration.**
   The adapter accepts Authentik identity headers without verifying their
   origin itself. Before enabling read access to real data, prove that every
   ingress strips/replaces client headers, or use verified authentication
   middleware. Workspace/project/session authorization is also still missing.
   Header-presence unit tests do not establish this trust boundary.

5. **P2: proposed API contract differs from the adapter.** The specification
   uses flat revision/resource-policy fields; the adapter uses nested objects
   and default Pydantic handling can ignore unsupported fields. Stable error
   envelopes, media types, snapshot schema/cursor, and revision validation
   remain incomplete. Freeze a tested request/response fixture set before
   desktop or legacy-route consumers depend on this version.

## Verification

The focused run of test_learning_contract.py, test_learning_routes.py,
test_learning_resources.py, test_backend_handoff_contract.py, and
test_event_contract.py produced **37 passed, 1 skipped**. Tests used local
pure functions and FastAPI test clients. No Postgres integration, real
authentication, GPU ownership, worker recovery, or overnight run was tested.

No service, container, database, GPU, training job, or SaltMedia resource was
changed during this check-in. Physical ownership and isolation (OA-001),
schema/migration ownership (OA-003), workers/checkpoints/leases, MemPalace
eligibility, evaluation, scheduling, and desktop qualification remain open.

Next local increment: resolve persistence and frozen-contract findings using
isolated database tests, then wire trusted admission and authentication after
their ownership boundaries are verified. Keep live execution disabled until
the backlog's qualification gates pass.
