# API Authentication and Claims Contract

Document ID: SEC-IDENT-002
Domain: Security
Owner: Security
Reviewers: Architecture, Platform, Compliance
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: agents/main.py, agents/security/authorization_middleware.py
Related Controls: MAESTRO L3, MAESTRO L4, MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Define endpoint classes, token profile requirements, and claims validation rules for Home AI Lab APIs.

## Implementation Reality (Current State)
1. `AuthorizationMiddleware` is mounted in `agents/main.py` with staged rollout mode via `AUTH_ENFORCEMENT_MODE` (`parse` default, `soft`, `hard`).
2. Active authentication protections in `agents/main.py` are currently:
   - `GET /api/v1/identity`: optional `SpiffeJWTBearer(auto_error=False)`.
   - `POST /api/v1/request`: API key required via `X-Swarm-Source` header and `VALID_API_KEYS` env map.
3. Current middleware enforcement includes endpoint classification, explicit user-vs-workload profile mismatch rejection, and admin capability checks.

## Endpoint Classes

| Endpoint Class | Description | Required Auth Profile | Example Routes |
|---|---|---|---|
| Public | Public read-only or utility endpoints | None | `/`, `/v1/models`, `/metrics`, `/voice_samples/{filename}` |
| User | User-facing operations and UI actions | User Access Token | `/v1/chat/completions`, `/v1/voice/chat`, `/v1/art/*`, `/v1/training/*`, `/v1/memory/*` |
| Admin | Governance or privileged config actions | User Access Token + elevated claims | `/api/v1/request/{id}/status` |
| Internal | Service-to-service and workload endpoints | Workload Identity Token | `/api/v1/identity`, internal `/api/*` service calls |

## Token Profiles

### Workload Identity Token (SPIFFE)
- Issuer: SPIRE/SPIFFE trust domain
- Typical algorithm: RS256
- Primary use: service-to-service identity
- Required claims:
  - `iss`
  - `sub` (SPIFFE ID)
  - `aud`
  - `exp`
  - `iat`
  - `nbf`

### User Access Token (JWT-ACE)
- Issuer: Home AI Lab security service
- Typical algorithm: HS256 (or RS256 if moved to asymmetric user-token signing)
- Primary use: user-scoped request authorization
- Required claims:
  - `iss`
  - `sub` (user_id)
  - `aud`
  - `exp`
  - `iat`
  - `nbf`
  - `jti`
- Optional claims:
  - `roles`
  - `scope`
  - `session_id`

## Endpoint Class to Token Type Matrix

| Endpoint Class | Allowed Token Type | Rejected Token Type | Notes |
|---|---|---|---|
| Public | None (or optional workload for telemetry) | User token for elevated behavior | Public endpoints must not grant privileged actions from token presence alone |
| User | User Access Token | Workload token | Prevent token confusion and cross-profile misuse |
| Admin | User Access Token with admin role/scope | Workload token, user token lacking role/scope | Enforce role claim validation and deny by default |
| Internal | Workload Identity Token | User token | Internal-only endpoints trust workload identity chain |

## Claims Validation Matrix

| Claim | Public | User | Admin | Internal | Validation Rule |
|---|---|---|---|---|---|
| `iss` | Optional | Required | Required | Required | Must match profile-specific pinned issuer |
| `sub` | Optional | Required (`user_id`) | Required (`user_id`) | Required (`spiffe_id`) | Must be non-empty, profile-consistent subject type |
| `aud` | Optional | Required | Required | Required | Must match endpoint class audience |
| `exp` | Optional | Required | Required | Required | Must be in future; reject expired tokens |
| `iat` | Optional | Required | Required | Required | Must be valid issuance time |
| `nbf` | Optional | Required | Required | Required | Must be valid not-before time |
| `jti` | Optional | Required | Required | Optional | Required for replay-resistant user tokens |
| `roles` | Optional | Optional | Required | Optional | Admin endpoints require role or scope grant |
| `scope` | Optional | Optional | Required | Optional | Scope must authorize target operation |

## Validation Rule Chain
1. Determine endpoint class from route map.
2. Extract bearer token (if required by class).
3. Verify signature with profile-appropriate verifier.
4. Validate temporal claims (`exp`, `iat`, `nbf`).
5. Validate issuer/audience against pinned values.
6. Enforce profile compatibility (user vs workload mutual exclusion).
7. Enforce privileged claims for Admin class (`roles` or `scope`).
8. Attach validated identity context to request state.
9. Log success/failure with request ID and rejection reason.

## Error Contract

| Failure Condition | HTTP | Error Detail |
|---|---|---|
| Missing token on protected class | 401 | `Missing or invalid authorization header` |
| Token expired | 401 | `Token has expired` |
| Invalid/malformed token | 401 | `Invalid or malformed token` |
| Wrong token profile for class | 401 | `Token profile not allowed for endpoint class` |
| Missing admin claim | 403 | `Insufficient role/scope for admin endpoint` |
| Internal validation error | 500 | `Error validating authorization` |

## Migration and Enforcement Plan
1. Parse-only mode: classify endpoint and token profile, log mismatches, do not block.
2. Soft-enforce mode: block profile mismatches while allowing controlled fallback under feature flag.
3. Hard-enforce mode: full mutual exclusion and claim enforcement by endpoint class.
4. Rollback: revert to soft-enforce while preserving issuer and audience pinning.

## Required Implementation Tasks (GAP-001)
1. Mount `AuthorizationMiddleware` (or equivalent) in `agents/main.py`.
2. Add explicit endpoint class map for all route groups.
3. Split validators by profile and enforce class-policy checks.
4. Standardize 401/403 responses with deterministic error messages.
5. Add unit and integration tests for matrix coverage.

## References
- docs/security/identity_token_trust_standard.md
- agents/main.py
- agents/security/authorization_middleware.py
