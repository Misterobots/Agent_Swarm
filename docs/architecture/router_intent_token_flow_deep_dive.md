# Router Intent Classification and Token Issuance Flow Deep Dive

Document ID: ARCH-DD-001
Domain: Architecture
Owner: Architecture
Reviewers: Security, Platform
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Source of Truth: agents/router.py, agents/main.py, agents/security/authorization_middleware.py

## Purpose
Describe the end-to-end routing pipeline from request ingress through intent classification, context propagation, and token issuance hooks.

## Entry Points
- `POST /v1/chat/completions`
- `POST /v1/voice/chat`
- `POST /api/v1/request`

## Request Lifecycle
1. Ingress request arrives in FastAPI app (`agents/main.py`).
2. Authorization middleware classifies endpoint class and token profile (`agents/security/authorization_middleware.py`).
3. Request-scoped identity context is attached to request state (including `owner_id` when available).
4. Router receives normalized request and performs intent classification (`agents/router.py`).
5. Router resolves session context and dispatches to orchestrated handlers.
6. Trace metadata is emitted with session and owner context for observability.

## Endpoint Class to Routing Behavior
- Public: utility/read endpoints with no privileged action.
- User: interactive user workflows routed through user-scoped context.
- Admin: privileged status/management operations requiring elevated claims.
- Internal: service-to-service paths constrained to workload identity.
- API key: controlled ingestion path mapped to known source identities.

## Token Issuance and Validation Touchpoints
- User and workload profile validation is split in `agents/security/token_issuer.py`.
- Middleware rejects profile mismatch before handler execution.
- Admin capability checks are enforced before privileged route access.

## Failure Modes and Controls
- Missing/malformed auth header: 401.
- Profile mismatch for endpoint class: 401.
- Missing admin role/scope for admin route: 403.
- Validation internal errors: 500 with request identifier for debugging.

## Evidence
- `tests/test_authorization_middleware.py`
- `tests/test_jwt_lifecycle.py`
- `docs/security/api_authentication_contract.md`
- `docs/security/api_contract_validation_examples.md`

## Open Follow-Ups
- Operational rollout from parse mode to soft/hard enforcement is tracked in governance closure packet residuals.
