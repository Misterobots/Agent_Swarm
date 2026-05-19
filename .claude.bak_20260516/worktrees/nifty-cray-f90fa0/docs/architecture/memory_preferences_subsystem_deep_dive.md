# Memory System and User-Scoped Preferences Deep Dive

Document ID: ARCH-DD-003
Domain: Architecture
Owner: Architecture
Reviewers: Platform, Security
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Source of Truth: agents/memory_system.py, agents/preferences.py, agents/context_manager.py

## Purpose
Explain data isolation and retrieval behavior for conversational memory and user preferences.

## Scope
- Session summary memory retrieval and storage behavior.
- User preference read/write pathways.
- Owner-aware context partitioning semantics.

## Context and Identity Model
- Context manager partitions active context by `(owner_id, session_id)` with controlled fallback behavior.
- Memory summaries carry owner tags and are filtered on recall.
- Preferences are resolved against user identity to prevent cross-user leakage.

## Data Access Rules
1. Reads must include user/owner-scoped filtering.
2. Writes must preserve owner/session ownership metadata.
3. Missing ownership context is treated as non-authoritative for protected flows.

## Isolation Guarantees
- Same-session cross-principal collisions are blocked.
- Owner-filtered recall prevents cross-user memory bleed.
- Separate user preference instances do not share values.

## Evidence
- `tests/test_cross_user_isolation.py`
- `docs/architecture/multi_user_propagation_trace.md`
- `docs/architecture/cross_user_isolation_test_plan.md`

## Open Follow-Ups
- Partition global rule-memory stores by owner in Sprint 2 memory hardening.
