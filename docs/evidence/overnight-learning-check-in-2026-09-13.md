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

## Findings addressed in this increment

- Idempotent creation now reserves `(owner_id, idempotency_key)` with an
  atomic `INSERT ... ON CONFLICT DO NOTHING` before creating the job. The
  losing transaction locks and replays the completed response, or reports a
  fingerprint conflict.
- Budgets are validated by the contract and included in the new learning job
  table, insert, update, and snapshot conversion paths.
- Stored events retain `experiment_id`; job snapshots retain an
  `event_cursor`; and transition patches are restricted to an explicit set of
  persisted mutable fields. The explicit initializer also adds these columns
  to existing `learning_*` tables and backfills cursors from their events; it
  never alters the legacy `swarm.*` tables.

These changes still need an isolated PostgreSQL integration test. The local
tests exercise the contract, store conversions, and route boundary without
opening a database.

## Open findings before enablement

1. **P1 deployment gate: authenticated identity and scope need integration.**
   The adapter accepts Authentik identity headers without verifying their
   origin itself. Before enabling read access to real data, prove that every
   ingress strips/replaces client headers, or use verified authentication
   middleware. Workspace/project/session authorization is also still missing.
   Header-presence unit tests do not establish this trust boundary.

2. **P2: proposed API contract differs from the adapter.** The specification
   uses flat revision/resource-policy fields; the adapter uses nested objects
   and default Pydantic handling can ignore unsupported fields. Stable error
   envelopes, media types, snapshot schema/cursor, and revision validation
   remain incomplete. Freeze a tested request/response fixture set before
   desktop or legacy-route consumers depend on this version.

## Verification

The focused run of test_learning_contract.py, test_learning_routes.py,
test_learning_resources.py, test_learning_store_contract.py,
test_backend_handoff_contract.py, and test_event_contract.py produced **41
passed, 1 skipped**. Tests used local
pure functions and FastAPI test clients. No Postgres integration, real
authentication, GPU ownership, worker recovery, or overnight run was tested.

No service, container, database, GPU, training job, or SaltMedia resource was
changed during this check-in. Physical ownership and isolation (OA-001),
schema/migration ownership (OA-003), workers/checkpoints/leases, MemPalace
eligibility, evaluation, scheduling, and desktop qualification remain open.

Next local increment: add isolated PostgreSQL concurrency and restart tests,
freeze request/response fixtures, and verify trusted authentication and scope
before wiring admission. Keep live execution disabled until the backlog's
qualification gates pass.
