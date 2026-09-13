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
- Learning routes now consume `request.state.owner_id` populated by validated
  JWT authorization middleware; they do not trust raw Authentik headers.
  `/api/v1/learning/*` is classified as a user endpoint, and trusted JWT
  metadata is required for workspace/project/session scope when the feature is
  enabled.
- The vendor JSON media type is enforced for learning responses, and frozen
  capabilities/dry-run fixtures cover the response shape.

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

An opt-in integration module now covers concurrent idempotent creation and
restart round-trip. It requires an explicit disposable
`LEARNING_TEST_POSTGRES_DSN`, refuses `AGNO_DB_URL`, and was skipped in this
workstation run because no such DSN was configured.

## Open findings before enablement

1. **P1 deployment gate: authenticated identity and scope need deployment
   verification.** The local route and middleware contract now requires
   validated JWT state and trusted `learning_scope` metadata. Before enabling
   read access to real data, verify the deployed ingress and token issuer
   provide that state and scope for every learning request. Header-presence
   unit tests do not establish this deployment boundary.

2. **P2: proposed API contract still needs request validation alignment.** The
   specification uses flat revision/resource-policy fields while the adapter
   uses nested objects. Stable error envelopes and revision validation remain
   incomplete. The capabilities and dry-run response shapes are fixture-tested;
   freeze the mutating and snapshot/event fixture set before desktop or
   legacy-route consumers depend on this version.

## Verification

The focused run of test_learning_contract.py, test_learning_routes.py,
test_learning_resources.py, test_learning_store_contract.py,
test_learning_fixtures.py, test_authorization_middleware.py,
test_backend_handoff_contract.py, test_event_contract.py, and the opt-in
Postgres module produced **57 passed, 3 skipped**. Tests used local pure
functions, FastAPI test clients, and middleware fixtures. No real Postgres
integration, deployed authentication, GPU ownership, worker recovery, or
overnight run was tested.

No service, container, database, GPU, training job, or SaltMedia resource was
changed during this check-in. Physical ownership and isolation (OA-001),
schema/migration ownership (OA-003), workers/checkpoints/leases, MemPalace
eligibility, evaluation, scheduling, and desktop qualification remain open.

Next qualification step: run the opt-in PostgreSQL module against a disposable
database, then verify the deployed JWT scope metadata and freeze the remaining
request/snapshot fixtures. Keep live execution disabled until the backlog's
qualification gates pass.
