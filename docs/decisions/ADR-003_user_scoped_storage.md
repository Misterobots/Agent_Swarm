# ADR-003: User-Scoped Storage Pattern

Document ID: ADR-003
Domain: Architecture / Security
Owner: Architecture
Reviewers: Security, Platform
Status: Accepted
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-06-30
Source of Truth: docs/decisions/
Related Controls: MAESTRO L3 (Identity), L5 (Data)
Related Evidence: docs/security/multi_user_identity_scoping_standard.md
Supersedes: None

---

## Status
**Accepted** (2026-03-31)

## Context

The system serves multiple users concurrently; each user interacts with the API independently. The system stores:
- User preferences and session state
- Conversation memory (chat history, context)
- Task execution results
- Training data and model weights (per-user scoped)

Previous implementations had shared data structures without explicit user scoping:
- Risk of cross-user access if queries don't include user_id filter
- Difficult to audit which user accessed which data
- No clear ownership model; hard to delete user's data on request
- Trace logs don't correlate to user; hard to debug per-user issues

---

## Decision

**Implement hard user-scoped storage with explicit ownership checks at every access:**

### 1. User ID Extraction at Ingress

Every API request extracts user_id from JWT at ingress:

```python
# AuthorizationMiddleware
token = extract_bearer_token(request)
validated_token = validate_token(token)  # Returns EphemeralAgentCard
user_id = validated_token.sub  # Extract from JWT "sub" claim
request.state.user_id = user_id  # Store in request context
```

- User ID is **immutable for the duration of the request**
- User ID is **thread-local** (stored in AsyncVar or request.state)
- User ID **cannot be overridden** by endpoint parameters or headers

### 2. Propagation Contract

User ID must be propagated through all subsystems without loss:

| Subsystem | Propagation Mechanism | Guarantee |
|---|---|---|
| Router | Request.state.user_id → session_id context → intent passing | Router methods receive user_id parameter; pass to subordinates |
| Memory System | user_id in context → read/write filters | All queries filter by user_id; return 0 results if mismatch |
| Preferences | user_id in context → scoped reads/writes | Preferences keyed by (user_id, preference_name) |
| Hooks | user_id parameter to hook.execute() | Hook cannot access request state; user_id is explicit |
| Traces | user_id in Langfuse context | Every trace entry tagged with user_id |
| Storage (PostgreSQL) | (user_id, entity_id) composite primary key | Queries always include user_id in WHERE clause |

### 3. Storage Partitioning

Data models include user_id as part of the primary key:

```python
# Example: Conversation memory
class ConversationEntry:
    user_id: str  # Required; immutable
    session_id: str  # User-scoped session
    turn_number: int
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    
    # Composite primary key: (user_id, session_id, turn_number)

# Example query: VALID
SELECT * FROM conversation_entries 
WHERE user_id = 'user123' AND session_id = 'sess456'

# Example query: INVALID (missing user_id filter)
SELECT * FROM conversation_entries 
WHERE session_id = 'sess456'  -- ❌ Would return data from ALL users
```

### 4. Ownership Verification

Every read/write operation enforces ownership:

```python
# Example: Safe read
def get_user_preferences(user_id: str, pref_key: str):
    prefs = storage.get(f"{user_id}:{pref_key}")  # Composite key
    assert prefs.user_id == user_id  # Ownership check
    return prefs

# Example: Safe write
def set_user_preference(user_id: str, pref_key: str, value: str):
    assert user_id is not None  # Cannot set for unknown user
    prefs = UserPreference(user_id=user_id, key=pref_key, value=value)
    storage.put(f"{user_id}:{pref_key}", prefs)
    
# Example: UNSAFE read ❌
def get_conversation_history(session_id: str):
    history = storage.query("SELECT * FROM conversations WHERE session_id = ?", session_id)
    # ❌ Could return data from multiple users if session_id is not unique per user
```

### 5. Trace Correlation

Every trace entry includes user_id:

```python
from langfuse import Langfuse

logger = Langfuse()

def chat_endpoint(request: Request):
    user_id = request.state.user_id
    jti = request.state.agent_card.jti
    
    # Langfuse trace includes user_id in metadata
    with logger.trace(
        name="chat_endpoint",
        user_id=user_id,  # Explicitly set
        metadata={"jti": jti}
    ):
        response = process_chat(request)
        logger.event(name="response_sent", metadata={"user_id": user_id})
        return response
```

### 6. User Data Deletion

On user deletion request, can efficiently clean up all data:

```python
async def delete_user(user_id: str):
    # Delete all records for this user across all tables
    await db.execute(
        "DELETE FROM conversation_entries WHERE user_id = ?", user_id
    )
    await db.execute(
        "DELETE FROM preferences WHERE user_id = ?", user_id
    )
    await db.execute(
        "DELETE FROM session_state WHERE user_id = ?", user_id
    )
    # Single query per table; no cross-user leakage possible
```

---

## Rationale

### Why Composite Keys?
- **Simplicity**: Composite keys force user_id to be present in every query
- **Enforcement**: Database-level constraint; cannot forget WHERE clause
- **Query transparency**: Every query is obvious about which user's data it's accessing

### Why Thread-Local User ID?
- **Non-invasive**: Don't need to pass user_id through every function signature
- **Immutability**: User ID extracted at ingress; cannot be changed mid-request
- **Auditability**: Langfuse trace can always access user_id from context

### Why Ownership Assertions?
- **Defense in depth**: Even if composite key constraint is missed, assertion catches the bug
- **Explicit**: Code shows clearly that we're checking ownership
- **Testable**: Can write tests that verify ownership assertions work

### Alternatives Considered

**Alternative A: Row-level security (RLS) in database**
- Database enforces ownership at query time
- ✅ **Considered**: Better for large datasets; prevents SQL injection from bypassing partitioning
- 🔄 **Future work**: Add RLS as second layer of defense after application-level checks

**Alternative B: Separate databases per user**
- Each user's data in isolated PostgreSQL schema
- ❌ **Rejected**: Overkill for current scale; high operational complexity

**Alternative C: User ID as optional parameter**
- Endpoints can query data for any user if they have permission
- ❌ **Rejected**: Violates principle of least privilege; increases risk of cross-user bugs

---

## Consequences

### Positive
- ✅ **Security (Critical)**: Cross-user access impossible without code bug that fails at ownership assertion
- ✅ **Auditability (High)**: Every data access correlated to user_id in trace; audit trail is complete
- ✅ **Data deletion (High)**: User data deletion is efficient single query per table; GDPR/privacy-compliant
- ✅ **Testing (High)**: Cross-user isolation can be tested systematically; add test for each new endpoint
- ✅ **Operations (Medium)**: Debugging per-user issues easy; filter logs by user_id

### Negative
- ⚠️ **Performance (Low)**: Additional composite key overhead negligible
- ⚠️ **Development friction (Low)**: Developers must remember to include user_id in every query; mitigated by helpers/ORM

### Neutral / Ongoing
- 🔄 **ORM integration**: Need ORM helpers that automatically include user_id in queries; prevent bugs at ORM level
- 🔄 **Query result validation**: Consider always asserting ownership of returned rows at application layer
- 🔄 **Migration to RLS**: Plan for adding database-level RLS (PostgreSQL row_security policy) in 6+ months

---

## Evidence / Verification

### Test Plan
1. **Unit tests**: User scoping in memory/preferences/storage
   - get() with wrong user_id returns empty or throws
   - set() without user_id throws assertion error
   - delete_user() only deletes that user's data

2. **Integration tests**: Cross-user isolation
   - User A creates preference → User B cannot read it
   - User A writes to conversation → User B cannot read it
   - User A deletes account → Data completely gone

3. **Security tests**: Cross-user access attempts
   - Forge JWT with different user_id → Rejected (token validation)
   - Query database directly with wrong user_id filter → No results
   - Call storage helper without user_id → Assertion error

4. **Trace tests**: User ID correlation
   - Every log entry includes user_id
   - Langfuse trace searchable by user_id
   - Deleted user's traces can be purged

### Metrics to Track
- `storage.ownership_assertion_failure_count` (Counter): Should be 0; any non-zero is a bug
- `storage.cross_user_query_attempt_count` (Counter): Should be 0; detects missing user_id filters
- `user_data_deletion_latency_p99` (Histogram): Should be <1s (single query per table)

### Verification Schedule
- **Week 0**: Unit tests pass; storage.py helpers reviewed and approved
- **Week 1**: Integration tests pass; cross-user isolation verified
- **Week 2**: Security tests pass; no ownership assertion failures in canary
- **Week 3**: Production rollout; monitor ownership_assertion_failure_count continuously

---

## Implementation Checklist

- [ ] User ID extraction added to AuthorizationMiddleware
- [ ] User ID stored in request.state (thread-local) for duration of request
- [ ] Storage schema updated with (user_id, entity_id) composite keys
- [ ] All existing queries updated to include user_id in WHERE clause
- [ ] ORM helpers created to enforce user_id in queries
- [ ] Ownership assertion added to all read/write operations
- [ ] Langfuse context integration includes user_id by default
- [ ] User data deletion procedure implemented and tested
- [ ] Unit tests written for storage isolation
- [ ] Integration tests written for cross-user isolation
- [ ] Security review of scoping logic completed
- [ ] Database indexes optimized for (user_id, entity_id) composite keys
- [ ] Runbook created for "cross-user access incident response"

---

## Related Decisions
- [ADR-001: JWT Profile Separation](ADR-001_jwt_profile_separation.md) (user_id extraction from user token)
- [ADR-002: Hook Execution Model](ADR-002_hook_execution_model.md) (user_id parameter to hooks)
- [Standard: Multi-user Scoping](../security/multi_user_identity_scoping_standard.md) (operational procedures)

## Reviewers and Approval
| Role | Name | Approved | Date |
|---|---|---|---|
| Architecture Lead | [To be assigned] | [ ] | — |
| Security Lead | [To be assigned] | [ ] | — |
| Platform Lead | [To be assigned] | [ ] | — |

---

**Document Owner**: Architecture  
**Last Review**: 2026-03-31  
**Next Review**: 2026-06-30  
**History**: Created as part of Sprint 2 ADR foundation; captures intent from multi_user_identity_scoping_standard.md and context_manager.py user propagation logic
