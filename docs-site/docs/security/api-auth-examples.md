---
title: API Contract Validation Examples
---

# API Contract Validation Examples

Executable request/response examples for the endpoint-class and token-profile rules defined in the [API Authentication and Claims Contract](api-auth-contract.md).

| | |
|---|---|
| Document ID | SEC-IDENT-003 |
| Domain | Security |
| Owner | Security |
| Reviewers | Architecture, Platform |
| Status | Approved |
| Version | 1.0 |
| Last Updated | 2026-03-31 |
| Source of Truth | [API Authentication and Claims Contract](api-auth-contract.md) |
| Related Controls | MAESTRO L3, MAESTRO L4 |

## Base URL Guidance

Use the active deployment entrypoint.

- Example from current environment: `http://192.168.2.103:3000`

## Example 1: Public Endpoint (No Token)

Request:

```bash
curl -i "${BASE_URL}/v1/models"
```

Expected:

- HTTP 200
- JSON model list payload

## Example 2: Protected Endpoint Missing Token

Request:

```bash
curl -i "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

Expected (target contract):

- HTTP 401
- Error detail indicating missing or invalid authorization header

## Example 3: User Endpoint with Workload Token (Profile Mismatch)

Request:

```bash
curl -i "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${WORKLOAD_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

Expected (target contract):

- HTTP 401
- Error detail: token profile not allowed for endpoint class

## Example 4: Internal Endpoint with User Token (Profile Mismatch)

Request:

```bash
curl -i "${BASE_URL}/api/v1/identity" \
  -H "Authorization: Bearer ${USER_TOKEN}"
```

Expected (target contract):

- HTTP 401
- Error detail: token profile not allowed for endpoint class

## Example 5: Admin Endpoint Without Required Role

Request:

```bash
curl -i "${BASE_URL}/api/v1/request/REQ-123/status" \
  -X POST \
  -H "Authorization: Bearer ${USER_TOKEN_WITHOUT_ADMIN_ROLE}" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved","note":"approve"}'
```

Expected (target contract):

- HTTP 403
- Error detail: insufficient role/scope for admin endpoint

## Example 6: Invalid Signature

Request:

```bash
curl -i "${BASE_URL}/api/v1/task" \
  -X POST \
  -H "Authorization: Bearer ${TAMPERED_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"task":"test"}'
```

Expected:

- HTTP 401
- Error detail: invalid or malformed token

## Example 7: Governance API Key Validation (Current Enforced Path)

Request:

```bash
curl -i "${BASE_URL}/api/v1/request" \
  -X POST \
  -H "X-Swarm-Source: ${INVALID_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"type":"install_package","description":"example","user":"operator"}'
```

Expected:

- HTTP 401
- Error detail: invalid API key / identity not verified

## Verification Checklist

- [ ] Public endpoint returns 200 without token.
- [ ] User endpoint rejects missing token (401).
- [ ] User endpoint rejects workload token (401).
- [ ] Internal endpoint rejects user token (401).
- [ ] Admin endpoint rejects token without required role/scope (403).
- [ ] Signature failures are rejected (401).
- [ ] Governance API key validation path rejects invalid key (401).

## Contextual Error Logging Template

Use this format when tests fail:

```text
Timestamp: <UTC>
Endpoint: <METHOD URL>
Expected: <status and behavior>
Actual: <status/body>
Context: <env, host, token profile, route class>
Likely Cause: <brief hypothesis>
Action Taken: <next step>
```

## Related

- [API Authentication and Claims Contract](api-auth-contract.md) — the endpoint-class, token-profile, and claims rules these examples validate
- [ADR-001: JWT-ACE Profiles over RBAC](../architecture/decisions/adr-001-jwt-profiles.md) — architectural rationale for the User Access Token (JWT-ACE) profile exercised in Examples 2-5
