# Architecture Decision Records (ADR) Index

Document ID: DOC-ARCH-001
Domain: Architecture
Owner: Architecture
Reviewers: Security, Platform, Compliance
Status: Active
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-05-31
Source of Truth: docs/decisions/
Related Controls: MAESTRO L2-L4
Related Evidence: docs/evidence/adr_decisions_log.md
Supersedes: None

## Purpose
Central index and template for Architecture Decision Records (ADRs). ADRs formalize design decisions that have significant architectural, security, or operational implications.

## ADR Process

### When to Write an ADR
Write an ADR when:
1. **Security impact**: Decision affects authentication, authorization, cryptography, or data isolation
2. **Architecture impact**: Decision affects system topology, component boundaries, or communication patterns
3. **Long-term commitment**: Decision commits resources or changes the baseline for future work
4. **Reversibility**: Decision is costly to reverse and needs explicit justification
5. **Team alignment**: Decision has cross-team implications and needs formal buy-in

### When NOT to Write an ADR
- Routine implementation details (function signature, variable naming)
- Temporary workarounds (use comments instead)
- Platform-specific tool selection (use a separate tools matrix)
- Minor refactorings for code hygiene

### ADR Format (Template)

```markdown
# ADR-NNN: [Decision Title in Present Tense]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
[What was the situation that motivated this decision? What constraints do we face?]

## Decision
[What decision have we made? State it as an imperative action.]

## Rationale
[Why this decision? What alternatives did we consider? Why did we pick this one?]

## Consequences
### Positive
- ...
### Negative
- ...
### Neutral / Ongoing
- ...

## Evidence / Verification
[How will we verify this decision is working as intended? What metrics/tests?]

## Related Decisions
- [Links to related ADRs]

## Reviewers
- ...
```

### ADR Status Lifecycle
1. **Proposed**: Open for discussion; not yet decided
2. **Accepted**: Approved by Architecture and Security leads; implementation can begin
3. **Deprecated**: Superseded or no longer relevant; keep for historical reference
4. **Superseded by ADR-XXX**: Replaced by a newer decision; link to successor

---

## Active ADRs

### ADR-001: JWT Profile Separation (Workload vs. User Tokens)
- **Status**: Accepted
- **Date**: 2026-03-31
- **Owner**: Security
- **Summary**: Implement strict mutual exclusion between workload tokens (SPIFFE X.509, service-to-service) and user tokens (ephemeral JWT, per-request capability). Endpoint-class routing determines acceptable token type.
- **Impact**: Security (token confusion), Architecture (validation policy)
- **Link**: [Full Decision](ADR-001_jwt_profile_separation.md)

### ADR-002: Hook Execution Model (Sync Security vs. Async Non-Security)
- **Status**: Accepted
- **Date**: 2026-03-31
- **Owner**: Architecture
- **Summary**: Execute security hooks (auth, ACL, validation) synchronously with fail-closed semantics. Execute non-security hooks (observability, learning, session) asynchronously with bounded timeout (5s) and graceful degradation. Enforce scope isolation per request user context.
- **Impact**: Security (fail-closed), Architecture (hook semantics), Operations (timeout tuning)
- **Link**: [Full Decision](ADR-002_hook_execution_model.md)

### ADR-003: User-Scoped Storage Pattern
- **Status**: Accepted
- **Date**: 2026-03-31
- **Owner**: Architecture
- **Summary**: Implement user-scoped storage with hard ownership checks at every read/write. user_id extracted from validated JWT at ingress, stored in thread-local context, propagated through router/memory/preferences/traces. Storage partitioning enforced via composite keys (user_id + entity_id). Cross-user access via direct query invalid.
- **Impact**: Security (multi-tenancy), Architecture (context propagation), Operations (trace correlation)
- **Link**: [Full Decision](ADR-003_user_scoped_storage.md)

### ADR-004: MarsRL Inference-Time Verification Loop
- **Status**: Accepted
- **Date**: 2026-03-31
- **Owner**: Architecture
- **Summary**: Implement three-stage inference loop: Solver (generate), Verifier (validate correctness), Corrector (fix errors). Each stage produces artifacts for audit trail. Verifier and Corrector run synchronously at inference time; results propagated to Langfuse trace for debugging and template evolution scoring.
- **Impact**: Architecture (inference time), Observability (trace completeness), Learning (template scoring)
- **Link**: [Full Decision](ADR-004_marsrl_inference_verification.md)

---

## Deprecated / Superseded ADRs
(None yet)

---

## ADR Review Board

### Review Criteria
1. **Security implications**: Does this affect authentication, authorization, encryption, or isolation?
2. **Architectural impact**: Does this affect system topology, component boundaries, or data flow?
3. **Reversibility**: How costly is it to change this decision later?
4. **Rationale completeness**: Are alternatives considered and trade-offs explicit?
5. **Evidence plan**: Is there a clear way to verify the decision is working?

### Required Approvals
All ADRs require approval from:
1. Architecture Lead
2. Security Lead
3. One additional lead (Platform, Compliance, or ML depending on scope)

### Review SLA
- **Proposed**: 5 business days for comments
- **Community Review**: 3 business days for feedback
- **Acceptance**: Final decision after review period closes

---

## See Also
- [Canonical Security Standards](../security/)
- [Design Framework](../admin/design_framework.md)
- [System Component Catalog](../catalog/system_component_service_catalog.md)
