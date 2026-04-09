# Multi-user Propagation Trace (Current State and Target Controls)

Document ID: ARCH-SCOPE-001
Domain: Architecture
Owner: Architecture
Reviewers: Security, Platform, Compliance
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: agents/main.py, agents/router.py, agents/context_manager.py, agents/memory_system.py, agents/preferences.py
Related Controls: MAESTRO L2, MAESTRO L3, MAESTRO L5, MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Document the actual identity/context propagation path and identify gaps between current implementation and target multi-user isolation controls.

## Executive Summary
1. Request context supports owner-aware scoping via `owner_id` propagated from API payload or authenticated request state, and user-token cards now support a canonical `user_id` field.
2. `AuthorizationMiddleware` is mounted in FastAPI app startup path with staged enforcement (`AUTH_ENFORCEMENT_MODE`, default `parse`).
3. `SpiffeJWTBearer` is only directly used on `/api/v1/identity` and is optional there (`auto_error=False`).
4. `context_manager.py` stores pending context by `(owner_id, session_id)` when an owner is supplied, with a legacy shared-session fallback for older call paths.
5. `memory_system.py` persists shared `skills_memory.json`, but session summaries now carry `owner_id` and support owner-filtered recall.
6. `preferences.py` has a `user_id` model field, while `main.py` now resolves an owner key from request payload or authenticated request state for chat and memory-summary paths.

## Step-by-Step Propagation Path (Current)

### Step 1: Ingress and Identity Extraction
- `agents/main.py` mounts `AuthorizationMiddleware` for centralized request classification and staged enforcement.
- `agents/security/authorization_middleware.py` defines token extraction and validation logic for `/api/*` pattern.
- `agents/security/middleware.py` provides `SpiffeJWTBearer` and `SpiffeAuthMiddleware`; only `SpiffeJWTBearer` dependency is used on `/api/v1/identity`.

Current behavior:
1. In default `parse` mode, endpoints can execute without blocking on missing bearer token while policy mismatches are logged.
2. Governance endpoint `/api/v1/request` enforces API key via `X-Swarm-Source`, separate from JWT user identity.

### Step 2: Router Context Propagation
- `chat_swarm(user_input, session_id=..., history=..., memory_enabled=..., owner_id=...)` propagates both session continuity and optional owner scope.
- Router metadata and trace attributes include `session_id`.
- JWT-ACE card issuance includes `session_id` and template metadata.

Current behavior:
1. Session continuity is propagated.
2. Owner scope is propagated to context-manager and memory-summary recall when available.
3. Router tracing now includes `owner_id` metadata where Langfuse tracing is enabled.
4. Canonical authenticated `user_id` is now supported in user token cards, but rollout consistency depends on issuers populating this field for all protected call paths.

### Step 3: Context Manager Persistence
- `agents/context_manager.py` stores pending context in `agents/context_sessions/<owner_id>/<session_id>.json` when owner scope is supplied.
- Session and owner identifiers are sanitized and truncated for filesystem safety.

Current behavior:
1. Partitioning boundary is `(owner_id, session_id)` when owner scope is present.
2. Legacy shared-session fallback remains available for older call paths that do not yet supply owner scope.

### Step 4: Memory System Access
- `agents/memory_system.py` persists to shared file `agents/skills_memory.json`.
- Domain rule storage (`visual_rules`, `coding_rules`, `general_rules`) is global.
- Session summaries exist as a single list under `session_summaries`, now with optional `owner_id` tags and owner-filtered retrieval.

Current behavior:
1. Session-summary recall can now be filtered by owner.
2. Rule retrieval remains keyword/domain-based and global, not user ownership-based.

### Step 5: Preferences Access
- `agents/preferences.py` defines `UserPreferences(user_id)` with in-memory dictionary.
- Includes serialization helpers, but no mandatory wiring that binds request identity to persistent store in this module.

Current behavior:
1. Preference model is user-aware in structure.
2. End-to-end enforcement from ingress token to persisted user-owned records is not uniformly implemented.

### Step 6: Hooks and Extensions
- No explicit hook execution bus/pipeline is implemented in current source paths inspected.
- Existing mention of "hook" in router is A/B routing comment, not a general hook framework execution path.

Current behavior:
1. Hook security policy exists as documentation baseline.
2. Runtime hook isolation controls are not represented as a central hook executor in the inspected code.

### Step 7: Trace Correlation
- Router attaches `session_id` metadata to Langfuse spans where enabled.
- No guaranteed universal `user_id` trace metadata for all request paths.

Current behavior:
1. Trace continuity by session exists.
2. Owner correlation is attached in router spans when available.
3. Hard universal authenticated user-scoped audit correlation still depends on complete token issuer adoption of canonical `user_id`.

## Sequence Diagram (Current)
```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI (main.py)
    participant Router as chat_swarm (router.py)
    participant Ctx as context_manager.py
    participant Mem as memory_system.py
    participant Pref as preferences.py
    participant Trace as Langfuse

    Client->>API: POST /v1/chat/completions (session_id, user_id?, messages)
    API->>Router: chat_swarm(user_input, session_id, owner_id)
    Router->>Ctx: get_pending_context(session_id, owner_id)
    Ctx-->>Router: owner-aware pending context
    Router->>Mem: get_recent_summaries(owner_id)/get_relevant_rules()
    Mem-->>Router: global/shared memory results
    Router->>Trace: span metadata {session_id, owner_id}
    Router-->>API: streamed response chunks
    API-->>Client: assistant response

    Note over API,Router: owner-aware scoping and owner trace metadata exist; canonical user_id rollout remains issuer-dependent
```

## Target Control Delta
To satisfy strict multi-user isolation:
1. Mount centralized auth middleware and extract `user_id` at ingress for protected classes.
2. Enforce `user_id` propagation through router and all downstream handlers.
3. Partition context storage by `(user_id, session_id)`.
4. Partition memory and preferences by `user_id` ownership checks.
5. Require `user_id` in trace metadata on all protected request paths.

## Contextual Error and Gap Log
1. Finding: No listener dependency issue for this doc path; analysis is static code inspection.
2. Gap with context: middleware is mounted, but default parse mode allows non-blocking behavior; hard enforcement and workload/user mutual exclusion remain pending hardening tasks.
3. Gap with context: owner-aware scoping and owner trace metadata are implemented for chat and memory-summary flows, but authenticated user identity extraction is still not a guaranteed prerequisite for every non-identity endpoint.

## Verification Pointers
- See docs/architecture/cross_user_isolation_test_plan.md for executable tests.
- See docs/security/api_authentication_contract.md for endpoint class and token policy.
- See docs/security/multi_user_identity_scoping_standard.md for target-state policy.
