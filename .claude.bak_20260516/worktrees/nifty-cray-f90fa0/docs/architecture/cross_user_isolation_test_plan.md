# Cross-user Isolation Test Plan

Document ID: ARCH-SCOPE-002
Domain: Architecture
Owner: Architecture
Reviewers: Security, Platform
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/architecture/multi_user_propagation_trace.md
Related Controls: MAESTRO L3, MAESTRO L5, MAESTRO L7
Related Evidence: docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Define executable tests to validate cross-user isolation controls and expose current-state gaps.

Current execution status:
1. T1-T5 now have executable coverage in `tests/test_cross_user_isolation.py` and related endpoint policy coverage in `tests/test_authorization_middleware.py`.
2. Latest focused execution result: `19 passed` when combined with IoT and endpoint-policy verification slice on 2026-03-31.

## Scope
Covers:
1. Session context isolation (`context_manager.py`).
2. Memory retrieval isolation (`memory_system.py`).
3. Preference isolation model (`preferences.py`).
4. API endpoint class and auth behavior for user vs internal classes.

## Preconditions
1. Test environment with API service reachable.
2. Two test principals: `user_a`, `user_b`.
3. Distinct session IDs: `sess_a`, `sess_b`.
4. Token fixtures where available:
   - `USER_TOKEN_A`
   - `USER_TOKEN_B`
   - `WORKLOAD_TOKEN`

## Test Matrix

| Test ID | Goal | Expected Result | Current-State Risk if Fails |
|---|---|---|---|
| T1 | User A data not readable by User B | Deny/empty for B | Cross-user leakage |
| T2 | Session-scoped context isolated | B cannot read A context | Session collision leakage |
| T3 | Profile mismatch blocked on endpoint class | 401 on wrong token type | Token confusion |
| T4 | Shared memory cannot leak personalized data | No user-specific bleed | Privacy breach |
| T5 | Preference reads enforce owner | B cannot read A preference | Preference leakage |

## Detailed Cases

### T1: Context Session Isolation
Steps:
1. Save pending context for `sess_a` with marker `A_ONLY`.
2. Read pending context for `sess_b`.
3. Read pending context for `sess_a`.

Expected:
- `sess_b` read returns none or unrelated context.
- `sess_a` read returns `A_ONLY`.

Pass Criteria:
- No `A_ONLY` leakage into `sess_b`.

### T2: Session ID Collision Guard
Steps:
1. Simulate two principals using same `session_id` intentionally.
2. Write pending context from principal A.
3. Read from principal B with same `session_id`.

Expected target-state:
- Access denied or partition by `(user_id, session_id)`.

Current-state note:
- Owner-aware partitioning is now implemented for context persistence; remaining risk is older call paths that still omit owner scope.

### T3: Endpoint Class Token Profile Enforcement
Steps:
1. Call user endpoint with `WORKLOAD_TOKEN`.
2. Call internal endpoint with `USER_TOKEN_A`.
3. Call protected endpoints with missing token.

Expected target-state:
- 401 for profile mismatch and missing token on protected classes.

Current-state note:
- Behavior may vary until centralized middleware is mounted and class policy is enforced.

### T4: Memory Isolation Check
Steps:
1. Add synthetic user-tagged rules in controlled fixture (`user_a_style_marker`, `user_b_style_marker`).
2. Query retrieval for user A and B independently through intended isolation adapter.

Expected target-state:
- Retrieval only returns caller-owned records.

Current-state note:
- Session-summary recall now supports owner filtering; domain rule storage remains global shared state and should be partitioned in a later phase if personalized rules move into the same store.

### T5: Preferences Ownership Check
Steps:
1. Create preference for `user_a` using `UserPreferences('user_a')`.
2. Attempt access from `UserPreferences('user_b')`.

Expected:
- `user_b` instance cannot read `user_a` preference values.

Pass Criteria:
- Ownership separation preserved at object/store layer.

## API Smoke Cases (cURL)
```bash
# Public endpoint baseline
curl -i "${BASE_URL}/v1/models"

# User endpoint with missing token (target: 401)
curl -i "${BASE_URL}/v1/chat/completions" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}]}'

# Internal endpoint with user token (target: 401)
curl -i "${BASE_URL}/api/v1/identity" -H "Authorization: Bearer ${USER_TOKEN_A}"
```

## Pytest Skeleton
```python
# tests/test_cross_user_isolation.py

def test_context_collision_should_not_leak_across_principals():
    ...


def test_memory_recall_should_filter_to_caller_owned_records():
    ...
```

## Observability and Evidence Capture
For each test case record:
1. Timestamp (UTC)
2. Principal (`user_a`/`user_b`/workload)
3. Endpoint or module under test
4. Expected vs actual
5. Request/trace identifiers
6. Verdict (pass/fail)

## Contextual Error Logging Template
```text
Timestamp: <UTC>
Test ID: <T1-T5>
Component: <API/router/context/memory/preferences>
Expected: <expected behavior>
Actual: <actual behavior>
Context: <session_id, principal, token profile>
Likely Cause: <brief hypothesis>
Action Taken: <fix or follow-up>
```

## Exit Criteria
1. T1-T5 executed and results captured.
2. Any failing tests converted into tracked remediation tasks.
3. Gap register updated with evidence links and status transition.

Latest result:
1. T1-T5 execution evidence captured on 2026-03-31.
2. Current follow-up remediation is limited to universal authenticated owner propagation and trace correlation, not the tested storage collision cases.

## References
- docs/architecture/multi_user_propagation_trace.md
- docs/security/api_authentication_contract.md
- docs/security/multi_user_identity_scoping_standard.md
