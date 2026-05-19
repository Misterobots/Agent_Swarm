# ADR-002: Hook Execution Model (Sync Security vs. Async Non-Security)

Document ID: ADR-002
Domain: Architecture / Security
Owner: Architecture
Reviewers: Security, Platform
Status: Accepted
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-06-30
Source of Truth: docs/decisions/
Related Controls: MAESTRO L2 (Observability), L3 (Identity), L4 (Access)
Related Evidence: docs/security/hook_security_execution_policy.md
Supersedes: None

---

## Status
**Accepted** (2026-03-31)

## Context

The system executes hooks at key lifecycle points:
1. **Authentication**: Pre-request, post-request hooks
2. **Task execution**: Pre-task, post-task hooks
3. **Observability**: Logging, tracing hooks
4. **Learning**: Template scoring, training data capture hooks
5. **Session management**: Session creation, state cleanup hooks

Previous implementations had hooks of mixed types executed inline without clear semantics:
- Some hooks were security-critical (auth, ACL check) and had to succeed
- Some hooks were observational (logging, tracing) and could fail without breaking the request
- Hook execution latency impacts user-perceived response time
- Cross-user data leakage possible if hook runs in wrong user context
- Timeout handling unclear; hooks could hang application

---

## Decision

**Implement two-tier hook execution model with strict scope isolation:**

### 1. Hook Categories
Each hook is classified at registration:

| Category | Type | Semantics | Execution | Timeout | Scope | Example |
|---|---|---|---|---|---|---|
| **Security** | Critical | Must succeed; fail-closed | Sync (before response sent) | 2s hard deadline | Isolated; user context enforced | Auth check, ACL validation, secret verification |
| **Observability** | Best-effort | Failure is acceptable | Async (fire-and-forget) | 5s (timeout is graceful) | User context from request | Logging, tracing, metrics emission |
| **Learning** | Best-effort | Failure is acceptable | Async (fire-and-forget) | 30s | Isolated; explicit user_id parameter | Template scoring, training capture |
| **Session** | State | Must update state; fail-closed | Sync (inline) | 2s hard deadline | Session context (cross-user OK) | Session cleanup, state persistence |

### 2. Execution Model

**Security Hooks (Sync, Fail-Closed)**
```
Request arrives
  → Extract user_id from token → Store in request.state.user_id
  → Execute security hooks sequentially
    → Each hook receives (request, user_id)
    → If hook returns false OR times out (>2s) → Return 401 Unauthorized
    → If hook throws exception → Catch, log, return 500 Internal Error
  → If all security hooks pass → Continue to business logic
  → Execute business logic
  → Return response
```

**Non-Security Hooks (Async, Best-Effort)**
```
Response ready to send
  → Capture (request, response, user_id, jti)
  → Queue hook job to async execution engine
  → Return response immediately (200/400/500)
  → Background: Execute each hook with timeout=5s per hook class or 30s per learning hook
    → If hook times out → Log warning, do not retry
    → If hook throws exception → Log error, do not retry
    → If hook completes → Record execution in trace context
```

### 3. Scope Enforcement

Every hook execution receives explicit scope context:

```python
# Example hook invocation (sync security)
class SecurityHook:
    def execute(self, request: Request, user_id: str) -> bool:
        # Hook receives user_id explicitly
        # Cannot access request.state.user_id unless we pass it
        # Memory access is partitioned by user_id at invocation
        return validate_user_permission(user_id, request.path)

# Example hook invocation (async observability)
class ObservabilityHook:
    def execute_async(self, event: HookEvent, user_id: str):
        # Hook runs in asyncio.Task; user_id is explicit
        # Memory queries include user_id filter
        event.user_id = user_id
        log_to_langfuse(event)
```

### 4. Timeout and Failure Isolation

- **Security hook timeout (2s hard deadline)**: If hook doesn't complete in 2s, kill task and return 401 (fail-closed)
- **Observability hook timeout (5s)**: If hook doesn't complete in 5s, mark as timed out and continue (graceful degradation)
- **Learning hook timeout (30s)**: If hook doesn't complete in 30s, mark as timed out and continue
- **Exception isolation**: Each hook wrapped in try-catch; exception in one hook does not affect others
- **Resource limits**: Async hooks run in bounded thread pool; queue size monitored to prevent memory overflow

### 5. Audit Logging

Every hook execution logged:
```json
{
  "event": "hook.executed",
  "hook_name": "acl_check",
  "user_id": "user123",
  "category": "security",
  "success": true,
  "latency_ms": 15,
  "timestamp": "2026-03-31T12:34:56Z",
  "jti": "token_jti_123"
}
```

---

## Rationale

### Why Two Tiers?
- **Security hook failure must block the request**: If ACL check fails, the response must not be sent
- **Observability hook failure should not block**: If logging times out, the business logic result is still valid and should be returned to user
- **Clear semantics enable correct implementation**: Developers know which tier their hook belongs in; framework prevents mistakes

### Why Async for Non-Security?
- **Performance**: User-perceived latency only includes security hooks; observability is background work
- **Resilience**: Logging system outage doesn't take down API
- **Scale**: Can process more requests if observability doesn't block
- **Resource isolation**: Async task failure doesn't corrupt request-scoped state

### Why Scope Isolation?
- **Multi-tenancy safety**: Even if hook has a bug, it cannot access different user's data
- **Auditability**: Trace shows explicitly which user_id each hook ran with
- **Testing**: Easier to test hook behavior in isolation with explicit parameters

### Why Different Timeouts?
- **Security (2s)**: Must be fast; if auth check takes >2s, probably in infinite loop; fail-closed
- **Observability (5s)**: Slower than security; allows database writes; if timeout, acceptable to drop this log entry
- **Learning (30s)**: Much slower; template scoring can involve model inference; timeout is graceful

### Alternatives Considered

**Alternative A: All hooks sync, fail-closed**
- Simpler mental model; all hooks have same semantics
- ❌ **Rejected**: Logging system outage would cause API outage; unacceptable

**Alternative B: All hooks async, best-effort**
- Maximum throughput
- ❌ **Rejected**: Security hooks cannot be async; ACL check must block response

**Alternative C: Hook priority queue with auto-scaling**
- Prioritize security hooks over observability
- ✅ **Considered but deferred**: More complex; start with sync/async split first

---

## Consequences

### Positive
- ✅ **Security (High)**: Security hooks guaranteed to run before response sent; fail-closed semantics prevent bypasses
- ✅ **Performance (High)**: Observability hooks don't block user requests; response time is only security hook + business logic
- ✅ **Resilience (High)**: Observability system failures (logging down, tracing timeout) don't cascade to API
- ✅ **Auditability (High)**: Every hook execution logged with explicit user_id; audit trail is complete
- ✅ **Multi-tenancy (High)**: Scope isolation prevents cross-user data leakage in hooks
- ✅ **Developer experience (Medium)**: Clear categories make it obvious which tier a new hook belongs in

### Negative
- ⚠️ **Debugging difficulty (Medium)**: Non-security hooks run asynchronously; harder to debug; requires good logging and tracing
- ⚠️ **Consistency (Low)**: Observability data may be incomplete if async hook times out; need alerts for high timeout rate

### Neutral / Ongoing
- 🔄 **Resource limits tuning**: Async thread pool size needs tuning based on load; monitor queue depth
- 🔄 **Hook registration API**: Need clear interface for registering hooks with category and timeout; prevent bugs at registration time
- 🔄 **Testing**: Need test templates for both sync and async hook execution; require developers to test timeout scenarios

---

## Evidence / Verification

### Test Plan
1. **Unit tests**: Hook execution logic with mock security/observability/learning hooks
   - Security hook timeout → 401
   - Observability hook timeout → response still sent, timeout logged
   - Scope isolation: Hook cannot access other user's data

2. **Integration tests**: Full request flow with hooks
   - Security hook failure → 401, no response body
   - Observability hook failure → 200 with response, hook error logged
   - Hook async execution verified by checking Langfuse trace

3. **Security tests**: Hook bypass scenarios
   - Attempt to fork hook execution to other user → fails (scope isolation)
   - Attempt to make async security hook → framework prevents registration
   - Attempt to register observability hook as security → framework prevents registration

4. **Load tests**: Hook execution under load
   - Security hook latency p99 < 100ms (latency budget for other operations)
   - Async hook queue depth under 10,000 items; no memory growth
   - No cascading failures when logging system slow

### Metrics to Track
- `hooks.security.latency_p99` (Histogram): 99th percentile latency for security hooks; target <100ms
- `hooks.observability.timeout_count` (Counter): Number of asynchronous observability hooks that timeout
- `hooks.scope_violation_attempt` (Counter): Number of times hook tried to access out-of-scope data; should be 0
- `hooks.async_queue_depth` (Gauge): Current depth of async hook execution queue

### Verification Schedule
- **Week 0**: Unit tests pass; scope isolation verified via code review
- **Week 1**: Integration tests pass; timeout behavior verified with manual testing
- **Week 2**: Production canary; monitor metrics for 48 hours
- **Week 3**: Full production rollout; establish alerting on scope violation attempts and timeouts

---

## Implementation Checklist

- [ ] Hook base class updated with category parameter (SECURITY/OBSERVABILITY/LEARNING/SESSION)
- [ ] Hook registration API validates category at registration time
- [ ] Security hook executor: Sync execution, 2s timeout, fail-closed
- [ ] Observability hook executor: Async execution, 5s timeout, best-effort
- [ ] Learning hook executor: Async execution, 30s timeout, best-effort
- [ ] Scope isolation enforced: Hook receives user_id explicitly, not from request state
- [ ] Audit logging implemented for all hook executions
- [ ] Exception handling and timeout handling tested
- [ ] Async thread pool created and monitored
- [ ] Hook timeout alerts configured
- [ ] Developer documentation and examples created
- [ ] Code review process updated to catch misclassified hooks

---

## Related Decisions
- [ADR-003: User-Scoped Storage Pattern](ADR-003_user_scoped_storage.md) (scope isolation from memory system)
- [Standard: Hook Security and Execution Policy](../security/hook_security_execution_policy.md) (operational procedures)

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
**History**: Created as part of Sprint 2 ADR foundation; captures existing intent from hook_security_execution_policy.md and router.py hook invocation logic
