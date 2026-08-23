---
title: "ADR-001: JWT-ACE Profiles over RBAC"
---

# ADR-001: JWT-ACE Profiles over RBAC

**Status**: Accepted  
**Date**: 2025-12

## Context

Memex agents need per-request authorization that controls which tools, models, and actions are available. Traditional RBAC (Role-Based Access Control) assigns static permissions to user roles. However, in an AI agent system:

- The same user may issue requests requiring wildly different permissions (code execution vs. reading a file)
- Agents act autonomously and need fine-grained, ephemeral permissions
- Permissions should expire with the request, not persist across sessions
- The system must be auditable — every capability decision needs a trace

## Decision

Use **JWT-ACE** (Authorization for Constrained Environments) ephemeral capability tokens instead of RBAC.

Each request receives a JWT token that encodes:

- **Intent-specific tools**: Only the tools needed for the classified intent
- **Security level**: L1–L7 graduated access
- **Expiration**: Token dies with the request/session
- **Audit trail**: Token is logged in Langfuse traces

The Token Issuer generates tokens based on the Semantic Router's intent classification:

```
Intent=CODE → tools=[file_ops, terminal, ast_tool], level=L4
Intent=CONVERSATION → tools=[search], level=L1
Intent=IOT_CONTROL → tools=[ha_call_service, ha_turn_on], level=L5
```

## Token Trust & Validation Rules

JWT-ACE tokens are issued and validated against the production token identity trust standard (`docs/security/identity_token_trust_standard.md`, SEC-IDENT-001):

- **Token profiles must not be mixed**: Workload Identity Token (SPIFFE JWT-SVID, service-to-service) and User Access Token (user-scoped, multi-user routing state) are distinct profiles, validated independently.
- **Validation requirements**: signature checked against allowlisted algorithms per profile; `iss`, `sub`, `aud`, `exp`, `iat`, `nbf` are all required and verified; token type must match route-class.
- **Prohibited patterns**: `none` algorithm in production; accepting both HS and RS validation on the same endpoint path; trusting dynamic key URLs from token headers unless explicitly allowlisted.
- **Route-class policy**: internal workload endpoints accept the workload identity profile only; user interaction endpoints accept the user access profile only; mixed acceptance is prohibited except in an explicit, feature-flagged migration mode.
- **Rollback-safe migration**: enforcement rolls out parse-only → soft-enforce → hard-enforce; rollback returns to soft-enforce while preserving issuer and audience checks.

## Consequences

### Positive

- **Least privilege by default**: Agents only get what they need for each request
- **No role explosion**: No need to define roles for every combination of capabilities
- **Auditability**: Every token is traceable; security reviews can see exactly what was permitted
- **Dynamic**: Permissions adapt to intent, not static user roles
- **Time-bounded**: Tokens expire, reducing blast radius of compromised credentials

### Negative

- **Complexity**: Token issuance adds a step to every request pipeline
- **Latency**: ~5ms overhead for token generation and validation
- **Intent dependency**: Security depends on correct intent classification — misclassification could over-scope a token
- **Custom implementation**: JWT-ACE is not a standard library; we maintain the issuer and validator

## Related

- [Architecture: Security Model](../security-model.md) — full security architecture
- `agents/security/token_issuer.py` — Token Issuer implementation
- `agents/security/capability_gate.py` — Token validation and enforcement


