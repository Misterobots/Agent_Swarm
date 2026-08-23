---
title: Multi-user Identity Scoping Standard
---

# Multi-user Identity Scoping Standard

**Status**: Approved
**Document ID**: SEC-SCOPE-001
**Domain**: Security
**Owner**: Architecture
**Reviewers**: Security, Platform, Compliance
**Version**: 1.0
**Last Updated**: 2026-03-31
**Review Due**: 2026-04-30
**Source of Truth**: `docs/admin/design_framework.md`
**Related Controls**: MAESTRO L7, MAESTRO L2
**Related Evidence**: `docs/compliance/eval_identity_security.md`
**Supersedes**: None

## Purpose

Define mandatory user scoping controls to prevent cross-user data leakage from ingress through routing, memory, storage, and trace layers.

## Scoping Contract

1. `user_id` is extracted only from validated user token claims.
2. `user_id` is bound to request context at ingress and never replaced by client payload.
3. `user_id` must be propagated through router, context manager, memory, and preference paths.
4. All storage reads and writes must include user ownership checks.

## Storage Partitioning Requirements

1. Session context files must be partitioned by user scope.
2. Preference records must be keyed by user scope.
3. Episodic and training references must include user ownership metadata.
4. Cross-user reads are denied by default.

## Trace and Audit Requirements

1. Traces must include user scope metadata.
2. Security events must log user scope and request ID.
3. Any cross-user access denial must be auditable.

## Verification

1. Cross-user isolation tests for session and preference paths.
2. Negative tests proving user A cannot retrieve user B context.
3. Trace checks for user scope metadata completeness.

## Implementation References

- `docs/architecture/multi_user_propagation_trace.md`
- `docs/architecture/cross_user_isolation_test_plan.md`

## Related

- [Architecture: Security Model](../architecture/security-model.md) — general security architecture (SPIFFE/SPIRE, JWT-ACE, MAESTRO layers)
- [ADR-001: JWT-ACE Profiles over RBAC](../architecture/decisions/adr-001-jwt-profiles.md) — per-request capability tokens referenced by the scoping contract
