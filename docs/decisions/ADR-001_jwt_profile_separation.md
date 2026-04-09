# ADR-001: JWT Profile Separation (Workload vs. User Tokens)

Document ID: ADR-001
Domain: Architecture / Security
Owner: Security
Reviewers: Architecture, Platform
Status: Accepted
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-06-30
Source of Truth: docs/decisions/
Related Controls: MAESTRO L3 (Identity), L4 (Access)
Related Evidence: docs/security/identity_token_trust_standard.md
Supersedes: None

---

## Status
**Accepted** (2026-03-31)

## Context

The system operates at the intersection of two identity scenarios:
1. **Service-to-service**: Workload identity using SPIFFE X.509 certificates (short-lived SVIDs)
2. **User interactions**: Per-request capability tokens using JWT-ACE (ephemeral user-scoped tokens)

Previous architecture had these token types mixed in validation logic, leading to risk of:
- Token confusion (accepting workload token where user token required, or vice versa)
- Cross-user access if user token validation logic was bypassed
- Unclear audit trail on which identity type was used

The system has multiple endpoint classes:
- **Public endpoints**: No authentication (e.g., health check, status page)
- **Authenticated endpoints**: User token required (e.g., chat, task completion)
- **Admin endpoints**: User token + role claim required (e.g., configuration changes)
- **Internal endpoints**: Workload token required (e.g., service-to-service communication from Execution node)

---

## Decision

**Implement strict mutual exclusion between workload and user token profiles:**

1. **Endpoint-class routing** determines acceptable token type(s):
   - Public endpoints: Accept no token (or optional workload token for observability)
   - Authenticated endpoints: Accept user token ONLY; reject all workload tokens
   - Admin endpoints: Accept user token + role claim ONLY
   - Internal endpoints: Accept workload token ONLY; reject all user tokens

2. **Token type is determined at issuance**, not at validation:
   - Workload tokens: Issued by SPIRE server; signed with RS256 (private key on SPIRE server only)
   - User tokens: Issued by JWT-ACE issuer; signed with HS256 (shared secret, rotated quarterly)

3. **Validation is mutually exclusive** at the AuthorizationMiddleware layer:
   - Extract token from Authorization header
   - Determine endpoint-class from request path
   - If endpoint-class == "Authenticated": Validate ONLY as user token; reject if RS256 or contains workload claims
   - If endpoint-class == "Internal": Validate ONLY as workload token (SPIFFE X.509 or RS256); reject if HS256 or contains user claims
   - If validation succeeds, create request.state.agent_card with token_type field (set to "workload" or "user")
   - If validation fails, return 401 Unauthorized and log classification attempt

4. **Required claims per profile**:
   - Workload token (RS256): `iss` (SPIRE server), `sub` (SPIFFE ID), `aud` (service name), `exp`, `iat`, `nbf`
   - User token (HS256): `iss` (JWT-ACE issuer), `sub` (user_id), `aud` (intended audience), `exp`, `iat`, `nbf`, `jti` (unique per request)

5. **Rollback-safe migration path**:
   - **Week 0 (Parse-only)**: Deploy code that logs token classification but does not enforce validation
   - **Week 1 (Soft-enforce)**: Deploy code that returns 401 for token confusion but allows both types on endpoints that need migration
   - **Week 2 (Hard-enforce)**: Deploy code with strict mutual exclusion; any token on wrong endpoint class returns 401

---

## Rationale

### Why Strict Mutual Exclusion?
- **Token confusion is high-severity**: Accepting workload token on user endpoint could allow cross-user access if attacker can obtain any valid workload token
- **Mutually exclusive validation is testable**: Each token type has distinct claims; validation logic can be proven complete
- **Audit trail clarity**: If a 401 happens, we can determine immediately whether the issue was "wrong token type" vs. "invalid claims for correct type"

### Alternatives Considered

**Alternative A: Unified validation with role-based differentiation**
- Single validation path; check claims (iss field) to distinguish profile
- ❌ **Rejected**: More complex; harder to prove correctness; token confusion bugs more likely

**Alternative B: Hard-coded endpoint → token type mapping in a config file**
- Central config file defines which endpoints accept which token types
- ✅ **Considered**: Better for operations (no code redeploy for endpoint-class changes)
- ⚠️ **Risk**: Out-of-sync with actual code; requires config validation and testing
- 🔄 **Future work**: Config file approach + hardcoded fallback for first 6 months

**Alternative C: Multiple token types on same endpoint with scoring**
- Accept both token types on all endpoints; score based on token type and claims
- ❌ **Rejected**: High risk of token confusion; violates principle of least privilege

### Why This Order of Consequences?
The consequences are ordered by impact tier: Critical (security) first, then Significant (architecture), then Operational.

---

## Consequences

### Positive
- ✅ **Security (High impact)**: Token confusion eliminated; workload tokens cannot be accepted where user tokens required
- ✅ **Audit clarity**: Every 401 response includes token classification attempt in logs; easy to debug
- ✅ **Test completeness**: Each endpoint-class can be tested with both correct and incorrect token types
- ✅ **Multi-tenancy assurance**: User endpoint validation now guaranteed to reject cross-workload tokens
- ✅ **Future-proof**: Architecture ready for optional additional token types (e.g., API keys, OAuth device flow) with same mutual-exclusion pattern

### Negative
- ⚠️ **Operational complexity (Medium impact)**: AuthorizationMiddleware becomes more complex; requires careful unit testing
- ⚠️ **Rollback difficult (Medium impact)**: Once hard-enforced in production, any endpoint-class misclassification will cause outage; requires careful migration plan
- ⚠️ **Performance (Low impact)**: Additional claim inspection per request (~1ms overhead per request)

### Neutral / Ongoing
- 🔄 **Configuration management**: Endpoint-class definitions currently hardcoded in agents/main.py routes; may need refactoring to config file later
- 🔄 **SPIRE server dependency**: RS256 validation requires SPIRE server reachability; graceful fallback to offline verification cache needed
- 🔄 **Monitoring and alerting**: Need alerts for "token type mismatch" pattern to detect attacks or misconfiguration early

---

## Evidence / Verification

### Test Plan
1. **Unit tests** (Unit): Test AuthorizationMiddleware validation logic with matrices of (endpoint_class, token_type) pairs
   - Valid combinations pass validation
   - Invalid combinations return 401 with correct error code
   - Claim validation works independently of token type

2. **Integration tests** (Integration): Test actual API endpoints with both token types
   - User endpoint rejects workload token
   - Internal endpoint rejects user token
   - Public endpoint accepts no token

3. **Security tests** (Security): Test attack scenarios
   - Forged workload token with user claims → 401
   - Forged user token with admin role → 401 (if not authorized)
   - Token signature validation failures → 401

4. **Load tests** (Performance): Measure authorization latency with strict validation
   - Baseline: <5ms per request for valid token
   - No performance regression from claim inspection

### Metrics to Track
- `auth.token_type_mismatch_count` (Counter): Number of tokens rejected due to type mismatch; should be 0 after migration
- `auth.validation_latency_p99` (Histogram): 99th percentile of authorization middleware latency; target <5ms
- `auth.endpoint_class_coverage` (Manual check): % of endpoints with explicit endpoint-class annotation

### Verification Schedule
- **Week 0 (Parse-only)**: Deploy logs; review token classification patterns daily
- **Week 1 (Soft-enforce)**: Track 401 rates by endpoint-class; review with API team
- **Week 2 (Hard-enforce)**: Confirm 0 token_type_mismatch errors for 48 hours post-deploy; monitor for user-facing 401s

---

## Implementation Checklist

- [ ] AuthorizationMiddleware updated with endpoint-class routing logic
- [ ] Token validation split into workload vs. user functions
- [ ] Endpoint-class annotations added to all routes in agents/main.py
- [ ] Claim validation matrices documented (see identity_token_trust_standard.md)
- [ ] Unit tests created for all validation paths
- [ ] Integration tests created for all endpoint classes
- [ ] Security review of validation logic passed
- [ ] Logging added for token classification attempts
- [ ] Migration schedule (Week 0/1/2) communicated to operations
- [ ] Runbook created for "token type mismatch" incidents

---

## Related Decisions
- [ADR-003: User-Scoped Storage Pattern](ADR-003_user_scoped_storage.md) (user_id extraction from user token)
- [Standard: Identity Token Trust](../security/identity_token_trust_standard.md) (token profiles and claims)
- [Standard: Multi-user Scoping](../security/multi_user_identity_scoping_standard.md) (user token claims and propagation)

## Reviewers and Approval
| Role | Name | Approved | Date |
|---|---|---|---|
| Security Lead | [To be assigned] | [ ] | — |
| Architecture Lead | [To be assigned] | [ ] | — |
| Platform Lead | [To be assigned] | [ ] | — |

---

**Document Owner**: Security  
**Last Review**: 2026-03-31  
**Next Review**: 2026-06-30  
**History**: Created as part of Sprint 2 ADR foundation; captures existing and intended design from identity_token_trust_standard.md
