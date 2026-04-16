# JWT-ACE Agent Card Lifecycle — Architecture Deep Dive

```
Document ID: ARCH-JWT-002
Domain: Architecture / Security
Owner: Core Platform
Reviewers: Security Team
Status: Approved
Version: 2.0
Last Updated: 2026-04-16
Supersedes: ARCH-JWT-001 (per-intent issuance model)
```

> **Back to:** [Documentation Index](../INDEX.md) · [Identity Token Trust Standard](../security/identity_token_trust_standard.md)

---

## Purpose

Documents the JWT-ACE (Agent Card Embedded JWT) lifecycle model. Version 2.0 replaces the per-intent token issuance with a session-level card architecture that uses per-intent capability scoping and parent-child card derivation for sub-agents.

---

## Source References

| Source | Type | Relevance |
|--------|------|-----------|
| [RFC 7519 — JSON Web Tokens](https://datatracker.ietf.org/doc/html/rfc7519) | IETF Standard | JWT structure, claims, expiry, signature |
| [RFC 7515 — JSON Web Signature](https://datatracker.ietf.org/doc/html/rfc7515) | IETF Standard | HS256/RS256 signing algorithms |
| [RFC 6749 — OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749) | IETF Standard | Scope model inspiration for active_scope narrowing |
| [SPIFFE / SPIRE](https://spiffe.io/) | CNCF project | Workload identity, RS256 key source in production |
| [Capability-Based Security (Dennis & Van Horn, 1966)](https://en.wikipedia.org/wiki/Capability-based_security) | CS foundational | Principle that capabilities are unforgeable tokens of authority |
| [PyJWT Library](https://pyjwt.readthedocs.io/) | Open source (pip) | JWT encode/decode implementation |
| [Principle of Least Privilege (Saltzer & Schroeder, 1975)](https://en.wikipedia.org/wiki/Principle_of_least_privilege) | CS foundational | Design basis for scope narrowing and child card intersection |

---

## Changelog: Source → Hive Implementation

<details markdown>
<summary><strong>View full changelog table</strong> (click to expand)</summary>

| Feature | Standard / Source | Hive Implementation | Delta |
|---------|-------------------|---------------------|-------|
| Token structure | RFC 7519 standard claims (iss, sub, exp, etc.) | Standard claims + custom `template_id`, `activated_capabilities`, `security_level` | Extended payload with agent-specific claims |
| Scope model | OAuth 2.0 scopes (space-delimited string) | `active_scope` per-intent list, checked by capability gate | List-based, server-side enforcement (not client-requested) |
| Token lifetime | RFC 7519 `exp` claim, single expiry | Session-level expiry (up to 4h) + child card TTL capped to parent remaining | Hierarchical expiry with parent→child inheritance |
| Signing | RS256 or HS256 per RFC 7515 | RS256 (prod via SPIRE) / HS256 (dev) with auto-fallback | Environment-adaptive signing |
| Parent-child tokens | Not in JWT spec | `derive_child_card()` with capability intersection + level capping | Novel: hierarchical token derivation |
| Validation caching | Not in JWT spec (always verify) | LRU cache (128 entries, 60s TTL) | Performance optimization — trades freshness for speed |
| Fail behavior | Spec says reject invalid tokens | Fail-open: JWT errors never block agent execution | Availability over strict security (configurable) |
| Thread safety | Not addressed by JWT spec | `threading.local()` for token + scope per thread | Thread-isolated context for concurrent workers |
| Identity persistence | One token per request (typical) | One session card, scope narrows per intent | Reduced issuance overhead (1 vs N per session) |

</details>

---

## Design Principles

1. **One card per session** — An agent's identity persists for its lifetime, not per-intent.
2. **Scope narrows, never widens** — Active scope restricts card capabilities per intent, never adds them.
3. **Children inherit, never escalate** — Child cards are strict subsets of parent capabilities and security level.
4. **Fail-open for availability** — JWT failures never block agent execution (parse-only mode default).
5. **Cache to avoid redundant crypto** — Validation cache (60s TTL) prevents repeated signature verification.

---

<details markdown>
<summary><strong>Card Lifecycle Diagram</strong> (click to expand)</summary>

```
Session Start
    │
    ▼
┌─────────────────────────────────┐
│  _issue_session_card()          │  ← Union of ALL intent capabilities
│  security_level = max(all)      │
│  expiry = max(all)              │
│  set_current_token(token)       │
└──────────────┬──────────────────┘
               │
    Intent Routing (per message)
               │
               ▼
┌─────────────────────────────────┐
│  set_active_scope(intent_caps)  │  ← Narrow to this intent's capabilities
│  (same token, different scope)   │
└──────────────┬──────────────────┘
               │
    ┌──────────┴──────────┐
    │ Normal Route         │ Coordinator Route
    │ (single agent)       │ (multi-worker)
    │                      │
    │                      ▼
    │         ┌─────────────────────────┐
    │         │ derive_child_card()      │
    │         │ caps ⊆ parent caps       │
    │         │ level ≤ parent level     │
    │         │ parent_id = parent UUID  │
    │         │ task_description set     │
    │         └────────┬────────────────┘
    │                  │
    │              Workers (threads)
    │              set_current_token(child_token)
    │                  │
    └──────────┬───────┘
               │
    Session End (finally block)
               │
               ▼
┌─────────────────────────────────┐
│  clear_active_scope()           │
│  clear_current_token()          │
└─────────────────────────────────┘
```

</details>

---

<details markdown>
<summary><strong>EphemeralAgentCard Dataclass</strong> (click to expand)</summary>

```python
@dataclass
class EphemeralAgentCard:
    template_id: str                    # "session_agent", "code_developer", etc.
    template_version: str               # "1.0", "1.3"
    agent_name: str                     # "SessionAgent", "Worker:analyst"
    agent_instance_id: str              # UUID (auto-generated)
    activated_capabilities: List[str]   # ["file_read", "model_generate", ...]
    security_level: str                 # L1_PUBLIC .. L4_SYSTEM
    user_id: Optional[str]              # Owner identity
    session_id: Optional[str]           # Session link
    parent_id: Optional[str]            # Parent card UUID (child cards only)
    metadata: Dict[str, Any]            # task_description, parent_template_id
    issued_at: datetime                 # UTC timestamp
    expiry_hours: int                   # TTL
```

### JWT Payload (Signed)

```json
{
  "iss": "home-ai-lab-token-issuer",
  "aud": "home-ai-lab-agents",
  "sub": "<agent_instance_id>",
  "iat": 1713250000,
  "exp": 1713264400,
  "template_id": "session_agent",
  "template_version": "1.0",
  "agent_name": "SessionAgent",
  "activated_capabilities": ["file_read", "file_write", "model_generate", "..."],
  "security_level": "L3_ADMIN",
  "user_id": "user123",
  "session_id": "sess-abc",
  "parent_id": null,
  "metadata": {}
}
```

</details>

---

## Session Card (Router)

Issued once per `chat_swarm()` call via `_issue_session_card()`:

| Property | Value |
|----------|-------|
| `template_id` | `session_agent` |
| `capabilities` | Union of ALL intents (currently 22 unique capabilities) |
| `security_level` | Highest across all intents (`L3_ADMIN`) |
| `expiry_hours` | Longest across all intents (4h from COORDINATE) |

This broad card is stored in thread-local context for the session duration.

---

## Active Scope (Per-Intent Narrowing)

When an intent is classified, `set_active_scope()` narrows what the session card is allowed to do:

```python
# Example: IMAGE intent
set_active_scope(["image_generate", "image_upload", "file_read", "model_generate"])
```

The capability gate checks **both**:
1. Is the capability in the card? (broad identity)
2. Is the capability in the active scope? (intent-specific)

A request for `terminal_exec` would be **denied** even though the session card has it, because the IMAGE intent scope doesn't include it.

### Scope Lifecycle

| Event | Scope State |
|-------|-------------|
| Session start | `None` (no restriction) |
| Intent classified | Set to intent's capabilities |
| Session end (finally) | Cleared to `None` |

---

## Child Card Derivation (Coordinator)

When the coordinator spawns worker agents, each receives a derived child card:

```python
child_card = derive_child_card(
    parent_card=session_card,
    child_template_id="coordinator_worker_analyst",
    child_agent_name="Worker:analyst",
    child_capabilities=["model_generate", "api_call", "file_read"],
    child_security_level="L2_USER",
    task_description="Research authentication patterns",
)
child_token = issuer.issue_token(child_card)
```

<details markdown>
<summary><strong>Derivation Rules</strong> (click to expand)</summary>

| Property | Rule |
|----------|------|
| `capabilities` | `child ∩ parent` — intersection, never exceeds parent |
| `security_level` | `min(child_requested, parent_level)` — capped |
| `parent_id` | Set to parent's `agent_instance_id` |
| `session_id` | Inherited from parent |
| `user_id` | Inherited from parent |
| `expiry_hours` | Parent's remaining TTL (minimum 1h) |
| `metadata.parent_template_id` | Parent's template ID |
| `metadata.task_description` | Worker's specific task |

</details>

<details markdown>
<summary><strong>Worker Role → Capabilities</strong> (click to expand)</summary>

| Role | Capabilities |
|------|-------------|
| architect | file_read/write, terminal_exec/read, model_generate, git_read/write |
| coder | file_read/write, terminal_exec/read, model_generate, git_read |
| devops | file_read/write, terminal_exec/read, api_call, resource_access |
| analyst | model_generate, api_call, file_read |
| researcher | model_generate, api_call, file_read |
| verifier | model_generate, file_read |

</details>

---

## Validation Cache

`TokenValidator` includes an in-memory LRU cache to avoid repeated JWT signature verification:

| Parameter | Value |
|-----------|-------|
| Max entries | 128 |
| TTL | 60 seconds |
| Key derivation | First 16 + last 16 chars + length |
| Eviction | Oldest entry when at capacity |

Cache hits skip `jwt.decode()` entirely, returning the previously validated `EphemeralAgentCard`. Expired cache entries are evicted on access.

---

## Execution Context (Thread-Local)

Two thread-local values are managed:

| Variable | Set by | Read by | Cleared by |
|----------|--------|---------|------------|
| `token` | `set_current_token()` | `get_current_token()` | `clear_current_token()` |
| `active_scope` | `set_active_scope()` | `get_active_scope()` | `clear_active_scope()` |

Both are stored in `threading.local()` and are safe for concurrent worker threads — each thread gets its own values.

---

## Capability Gate (Enforcement)

<details markdown>
<summary><strong>Capability Gate Flow Diagram</strong> (click to expand)</summary>

```
Request for "terminal_exec"
    │
    ▼
Card has "terminal_exec"?
    ├─ No → DENY
    ├─ Yes ─┐
    │       ▼
    │   Active scope set?
    │       ├─ No (None) → ALLOW
    │       ├─ Yes: "terminal_exec" in scope?
    │       │       ├─ No → DENY (not in intent scope)
    │       │       └─ Yes → ALLOW
    │       └─ Fallback capability check (same logic)
    └─ Fallback capability check (same logic)
```

</details>

---

## Signing Methods

| Environment | Algorithm | Key Source |
|------------|-----------|-----------|
| Production | RS256 | SPIRE workload private key |
| Development | HS256 | `EPHEMERAL_AGENT_JWT_SECRET` env var |
| Fallback | HS256 | `"dev-insecure-secret-key-change-in-production"` |

> [!NOTE]
> The development fallback key is insecure by design. Set `EPHEMERAL_AGENT_JWT_SECRET` in production.

---

## Migration from v1 (Per-Intent)

<details markdown>
<summary><strong>Migration Comparison: v1 vs v2</strong> (click to expand)</summary>

| Aspect | v1 | v2 (Current) |
|--------|-----|-------------|
| Card issuance | Once per intent | Once per session |
| Identity persistence | Per-intent UUID | Session-stable UUID |
| Capability restriction | Full card per intent | Session card + active scope |
| Sub-agent cards | Not supported | `derive_child_card()` |
| Validation caching | None | LRU 128/60s |
| Coordinator workers | Inherit parent token as-is | Receive derived child tokens |

</details>

### Backward Compatibility

`_issue_ephemeral_token()` (per-intent) is **retained** for any callers that still need per-intent cards. The router now uses `_issue_session_card()` by default.

---

## Maintenance & Update Guide

### Adding New Capabilities

1. Add the capability string to the relevant intent(s) in `agents/intent_capabilities.py`.
2. If needed, add a new role in `agents/coordinator.py` `_ROLE_CAPS` mapping.
3. The session card auto-includes all intent capabilities — no card template changes needed.
4. Update the capability gate if the new capability requires special enforcement logic.

### Changing Security Levels

Security levels are ordered: `L1_PUBLIC` < `L2_USER` < `L3_ADMIN` < `L4_SYSTEM`.

To change an intent's security level, update the `INTENT_TOKENS` mapping in `agents/intent_capabilities.py`. The session card takes the maximum.

### Tuning the Validation Cache

Edit `agents/security/token_issuer.py`:

```python
# In TokenValidator.__init__()
self._cache_maxsize = 128   # Max cached tokens
self._cache_ttl = 60        # Seconds before re-validation
```

- **Increase TTL** for lower-traffic environments (reduces CPU).
- **Decrease TTL** for higher-security environments (faster revocation detection).
- **Increase maxsize** if running many concurrent coordinator workers.

### Rotating Signing Keys

| Environment | Rotation Steps |
|------------|----------------|
| Development | Change `EPHEMERAL_AGENT_JWT_SECRET` env var, restart server |
| Production | Rotate SPIRE workload key via `spire-server entry update`, agents auto-pick up new key |

See [Key Lifecycle and Rotation Runbook](../security/key_lifecycle_rotation_runbook.md) for full procedure.

### Switching Fail Mode

To change from fail-open (default) to fail-closed, edit `agents/security/capability_gate.py` to raise exceptions rather than logging warnings on JWT validation failures.

---

## Functionality Testing

### Running Existing Tests

```bash
pytest tests/test_jwt_lifecycle.py -v
```

The existing test suite covers:
- Token issuance and signature verification
- Capability checking against card claims
- Token expiry validation

### Recommended Additional Tests

```bash
# tests/test_jwt_session_cards.py (to be created)
# - Session card contains union of all intent capabilities
# - Active scope narrows effective capabilities
# - derive_child_card() intersects capabilities correctly
# - derive_child_card() caps security level
# - Child card has parent_id set
# - Validation cache returns same result within TTL
# - Validation cache evicts after TTL
# - Thread-local context is isolated between threads
```

### Manual Verification

| Test Case | Steps | Expected Result |
|-----------|-------|----------------|
| Session card | Send any chat message; inspect logs | Single card issued at session start |
| Scope narrowing | Send IMAGE intent; check capability gate logs | Only image-related capabilities allowed |
| Child derivation | Trigger COORDINATE intent; check worker logs | Each worker gets unique child token with `parent_id` |
| Capability denied | Modify active_scope to exclude needed cap | Gate logs: "Capability X not in active scope" |
| Cache hit | Send two messages rapidly; check validator logs | Second validation says "cache hit" |
| Fail-open | Set invalid JWT secret; send message | Agent executes normally, warning logged |

### Security Audit Testing

```bash
# Verify child cannot exceed parent
python -c "
from agents.security.token_issuer import TokenIssuer, derive_child_card, EphemeralAgentCard
from datetime import datetime

parent = EphemeralAgentCard(
    template_id='session', template_version='1.0',
    agent_name='Parent', agent_instance_id='p-1',
    activated_capabilities=['file_read'],
    security_level='L2_USER', parent_id=None,
    metadata={}, issued_at=datetime.utcnow(), expiry_hours=4
)
child = derive_child_card(parent, 'child_tmpl', 'Child',
    child_capabilities=['file_read', 'terminal_exec'],  # escalation attempt
    child_security_level='L3_ADMIN')                      # escalation attempt
assert 'terminal_exec' not in child.activated_capabilities, 'ESCALATION BUG'
assert child.security_level == 'L2_USER', 'LEVEL ESCALATION BUG'
print('ALL SECURITY CHECKS PASSED')
"
```

---

<details markdown>
<summary><strong>Source of Truth</strong> (click to expand)</summary>

| Component | File |
|-----------|------|
| Card dataclass + derive + cache | `agents/security/token_issuer.py` |
| Execution context (token + scope) | `agents/security/execution_context.py` |
| Capability gate (two-stage check) | `agents/security/capability_gate.py` |
| Authorization middleware | `agents/security/authorization_middleware.py` |
| Intent → capability mapping | `agents/intent_capabilities.py` |
| Session card issuance + scope | `agents/router.py` |
| Child card derivation for workers | `agents/coordinator.py` |
| Audit logging | `agents/security/audit_logger.py` |

</details>

---

## Related Documents

- [Identity Token Trust Standard](../security/identity_token_trust_standard.md)
- [API Authentication Contract](../security/api_authentication_contract.md)
- [Router Intent Token Flow Deep Dive](router_intent_token_flow_deep_dive.md)
- [JWT Ephemeral Agents Research](../JWT_EPHEMERAL_AGENTS_RESEARCH.md)
