# JWT-Based Ephemeral Agent Credentialling: Research & Architecture

**Date**: March 14, 2026  
**Status**: Research Phase — Pre-Implementation Specification  
**User Goal**: Use JWT tokens to credential dynamic/ephemeral agents with embedded agent cards for auth, logging, rewards, security, and guardrails.

---

## Executive Summary

Proposal: **Agent Card Embedded JWT (ACE-JWT)** — A zero-trust credential system where:
1. **At creation**: Ephemeral agent receives JWT containing AgentCard + operational scope
2. **At execution**: Agent presents token in all API calls (authorization header)
3. **At audit**: Token claims are logged with every action, creating audit trail
4. **At reward**: Langfuse traces link back to agent_id from token, enabling per-agent training
5. **At guardrails**: Token claims are evaluated for permission before tool execution

---

## Part 1: Current State Analysis

### Your Existing Infrastructure ✅

**SPIFFE/SPIRE Integration** (`agents/security/spiffe_auth.py`):
- ✅ X.509 SVID fetching (mTLS certificates)
- ✅ JWT-SVID generation (short-lived JWTs signed by SPIRE)
- ✅ Peer identity verification
- ✅ Automatic credential rotation

**AgentCard Registry** (`agents/registry.py`):
```python
class AgentCard(BaseModel):
    id: str                           # UUID
    name: str                         # "Code Developer"
    role: str                         # "Full Stack & System Engineer"
    description: str
    security_level: str               # L1_PUBLIC, L2_USER, L3_ADMIN, L4_SYSTEM
    capabilities: List[str]           # ["file_ops.write", "terminal.exec", ...]
    endpoint: str                     # "local://agents.architect_agent"
```

**Current JWT Usage** (`agents/security/middleware.py`):
- FastAPI SpiffeJWTBearer security scheme
- Verifies "Authorization: Bearer {token}" header
- Extracts SPIFFE ID from claims
- Returns claims dict to endpoint

### Limitations (for ephemeral agents) ❌

1. **Static Registration**: AgentCard must exist in registry.py before startup
   - Problem: Ephemeral agents are created at runtime, not pre-registered
   - Solution needed: Dynamic card generation + JWT embedding

2. **Claims Not Structured for Authorization**: Current JWT has SPIFFE ID only
   - Problem: No explicit capability/permission claims in token
   - Solution needed: Extend JWT claims with capabilities, security_level, activated_parameters

3. **No Audit Trail Connection**: Tokens are verified but claims aren't logged per-action
   - Problem: Hard to trace which agent performed which action in logs
   - Solution needed: Middleware to inject token claims into log context

4. **No Relationship to Tools/Permissions**: Agent capabilities listed in registry, but not enforced at tool invocation
   - Problem: Tools don't check if agent token permits access
   - Solution needed: Capability-gating decorator for tools

5. **No Training Dataset Linkage**: MarsRL loops don't know which agent executed them
   - Problem: Can't attribute rewards to specific agent instances
   - Solution needed: Agent_id in Langfuse metadata from token

---

## Part 2: JWT-Based Ephemeral Agent System Design

### 2.1 Extended JWT Claims Structure

**Standard SPIFFE Claims** (existing):
```json
{
  "iss": "spiffe://home-ai-lab",
  "sub": "spiffe://home-ai-lab/agent/router",
  "aud": ["spiffe://home-ai-lab/api/dispatch"],
  "exp": 1700000000,
  "iat": 1700000000
}
```

**Extended with Agent Card Claims** (proposed):
```json
{
  "iss": "spiffe://home-ai-lab",
  "sub": "spiffe://home-ai-lab/agent/router",
  "aud": ["spiffe://home-ai-lab/api/dispatch"],
  "exp": 1700000000,
  "iat": 1700000000,
  
  "agent_id": "uuid-ephemeral-12345",
  "agent_name": "Code Developer",
  "agent_role": "Full Stack & System Engineer",
  "agent_description": "...",
  "security_level": "L3_ADMIN",
  "capabilities": [
    "file_ops.write",
    "file_ops.read",
    "terminal.exec"
  ],
  "activated_parameters": {
    "max_iterations": 2,
    "temperature": 0.7,
    "model": "qwen2.5-coder:14b",
    "tools_enabled": ["file_ops", "terminal"],
    "workspace_root": "/workspace"
  },
  "parent_trace_id": "langfuse-trace-xyz",
  "session_id": "user-session-456",
  "created_by": "spiffe://home-ai-lab/agent/router",
  "created_at": 1700000000,
  "expires_at": 1700000600,
  "revocation_check_required": false
}
```

### 2.2 Responsibility Alignment: Issuer vs. Bearer

**Who Issues the Token?**
```
User Input → Router Agent
           → (validates intent via semantic_router)
           → Decides: "I need to spawn a Code Developer agent for THIS task"
           → Calls: issuer = TokenIssuer(spiffe_auth)
           → Calls: ephemeral_card = create_ephemeral_card(
                      template="Code Developer",
                      activated_capabilities=["file_ops.write", "file_ops.read"],
                      activated_parameters={"max_iterations": 2}
                    )
           → Calls: token = issuer.issue_token(ephemeral_card, parent_trace_id)
           → Spawns: ephemeral_agent = CodeDeveloper(token=token)
```

**Who Uses the Token?**
```
Ephemeral Agent (running CodeDeveloper loop):
    → Receives token at init time
    → Stores token in memory (runtime)
    → Before EVERY tool call:
        - Extracts capabilities from token.claims["capabilities"]
        - Checks: "Is 'file_ops.write' in my capabilities?"
        - If NO: Raises PermissionError (guardrail)
        - If YES: Proceeds with tool call
    → Logs action with token.claims["agent_id"]
      → Langfuse middleware picks up agent_id from logging context
      → Attaches to trace: {agent_id: UUID, agent_name: "Code Developer"}
    → On completion: Token discarded (ephemeral auth lifetime ends)
```

---

## Part 3: Implementation Architecture

### 3.1 Core Components

**File: `agents/security/token_issuer.py`** (NEW)
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import jwt
import uuid
import logging
from .spiffe_auth import get_spiffe_auth
from registry import AgentCard

logger = logging.getLogger(__name__)

class EphemeralAgentCard(AgentCard):
    """Extended AgentCard with runtime activation metadata"""
    instance_id: str                    # Unique per ephemeral spawn
    activated_capabilities: List[str]   # Subset of card.capabilities
    activated_parameters: Dict[str, Any]
    parent_trace_id: Optional[str]     # Langfuse trace this agent is part of
    session_id: Optional[str]
    created_by: str                     # SPIFFE ID of parent agent
    ttl_seconds: int = 600              # 10 minutes default
    
class TokenIssuer:
    """Issues JWT tokens for ephemeral agents"""
    
    def __init__(self, spiffe_auth=None):
        self.spiffe_auth = spiffe_auth or get_spiffe_auth()
        self.signing_key = None         # Lazy-loaded from SPIFFE
    
    def issue_token(self, 
                   ephemeral_card: EphemeralAgentCard,
                   parent_trace_id: str = None,
                   ttl_seconds: int = 600) -> str:
        """
        Issue JWT for ephemeral agent.
        
        Token is signed by SPIFFE (using our X.509 SVID private key)
        and contains full AgentCard as claims.
        """
        # 1. Get our SPIFFE identity
        our_identity = self.spiffe_auth.get_spiffe_id()
        
        # 2. Build JWT claims
        now = datetime.utcnow()
        claims = {
            # Standard SPIFFE claims
            "iss": f"spiffe://home-ai-lab",
            "sub": f"spiffe://home-ai-lab/agent/ephemeral/{ephemeral_card.instance_id}",
            "aud": ["spiffe://home-ai-lab/api/dispatch"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
            
            # Agent Card claims
            "agent_id": ephemeral_card.instance_id,
            "agent_name": ephemeral_card.name,
            "agent_role": ephemeral_card.role,
            "security_level": ephemeral_card.security_level,
            "capabilities": ephemeral_card.activated_capabilities,
            "activated_parameters": ephemeral_card.activated_parameters,
            
            # Context linkage
            "parent_trace_id": parent_trace_id,
            "session_id": ephemeral_card.session_id,
            "created_by": ephemeral_card.created_by,
        }
        
        # 3. Sign with SPIFFE private key
        token = jwt.encode(
            claims,
            self.spiffe_auth.get_private_key(),  # From X.509 SVID
            algorithm="RS256"
        )
        
        logger.info(f"Issued ephemeral token for agent {ephemeral_card.instance_id}")
        return token

class TokenValidator:
    """Validates and extracts claims from ephemeral agent tokens"""
    
    def __init__(self, spiffe_auth=None):
        self.spiffe_auth = spiffe_auth or get_spiffe_auth()
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT signature and return claims.
        
        Signature verified using SPIFFE's public key (from SPIRE).
        """
        try:
            claims = jwt.decode(
                token,
                self.spiffe_auth.get_public_key(),  # From SPISSE bundle
                algorithms=["RS256"],
                audience="spiffe://home-ai-lab/api/dispatch"
            )
            return claims
        except jwt.InvalidTokenError as e:
            logger.error(f"Token validation failed: {e}")
            return None
```

**File: `agents/security/capability_gate.py`** (NEW)
```python
from functools import wraps
from typing import List
import logging

logger = logging.getLogger(__name__)

class CapabilityRequired:
    """
    Decorator: Enforce capability check at tool invocation.
    
    Usage:
        @CapabilityRequired("file_ops.write")
        def write_file(path: str, content: str, agent_token: str):
            ...
    """
    
    def __init__(self, required_capability: str):
        self.required_capability = required_capability
    
    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, agent_token: str = None, **kwargs):
            if not agent_token:
                raise PermissionError(
                    f"{func.__name__} requires agent_token parameter"
                )
            
            # 1. Get token claims (assuming token validator in context)
            from .token_issuer import TokenValidator
            validator = TokenValidator()
            claims = validator.validate_token(agent_token)
            
            if not claims:
                raise PermissionError(f"Invalid token for {func.__name__}")
            
            # 2. Check capability
            capabilities = claims.get("capabilities", [])
            if self.required_capability not in capabilities:
                logger.warning(
                    f"Agent {claims['agent_id']} denied {self.required_capability}: "
                    f"has {capabilities}"
                )
                raise PermissionError(
                    f"Agent lacks capability: {self.required_capability}"
                )
            
            # 3. Log action with agent context
            logger.info(
                f"[{claims['agent_id']}] Authorized action: {func.__name__}",
                extra={
                    "agent_id": claims["agent_id"],
                    "agent_name": claims["agent_name"],
                    "capability": self.required_capability,
                    "trace_id": claims.get("parent_trace_id")
                }
            )
            
            # 4. Execute
            return await func(*args, **kwargs)
        
        return wrapper
```

### 3.2 Agent Initialization: Receiving the Token

**File: `agents/architect_agent.py`** (MODIFIED)
```python
from phi.agent import Agent
from security.token_issuer import TokenValidator
import logging

class ArchitectAgent(Agent):
    def __init__(self, token: str = None):
        """Initialize with ephemeral token"""
        self.agent_token = token
        self.token_claims = None
        
        if token:
            # Validate token and extract claims
            validator = TokenValidator()
            self.token_claims = validator.validate_token(token)
            
            if not self.token_claims:
                raise ValueError("Invalid ephemeral agent token")
            
            # Extract metadata from token for logging
            self.agent_id = self.token_claims["agent_id"]
            self.parent_trace_id = self.token_claims.get("parent_trace_id")
            
            logging.info(
                f"ArchitectAgent initialized as ephemeral instance {self.agent_id}",
                extra={"agent_id": self.agent_id, "trace_id": self.parent_trace_id}
            )
        
        # Initialize parent Agent
        super().__init__(
            name="Code Developer",
            model=...,
            tools=[
                # Tools that are gated
            ]
        )
    
    async def run(self, task: str) -> str:
        """Execute task with token context"""
        # Pass token to all tool invocations
        result = await super().run(task)
        
        # Log completion with agent context
        logging.info(
            f"Task completed by {self.agent_id}",
            extra={
                "agent_id": self.agent_id,
                "trace_id": self.parent_trace_id
            }
        )
        
        return result
```

---

## Part 4: Integration with Router + MarsRL

### 4.1 Ephemeral Agent Creation Flow

**File: `agents/router.py`** (MODIFIED)
```python
from security.token_issuer import TokenIssuer, EphemeralAgentCard
import uuid

async def route_and_execute(user_input: str, session_id: str):
    """
    Router orchestrates intent classification → ephemeral agent creation → execution
    """
    
    # 1. Classify intent
    router = get_semantic_router()
    intent = router.route(user_input)  # Returns {"intent": "CODE", ...}
    
    # 2. Based on intent, decide which agent template to use
    if intent["intent"] == "CODE":
        agent_template = "Code Developer"
        activated_capabilities = [
            "file_ops.write",
            "file_ops.read", 
            "terminal.exec"
        ]
        activated_parameters = {
            "max_iterations": 2,
            "temperature": 0.7,
            "model": "qwen2.5-coder:14b",
        }
    
    # 3. Create Langfuse trace (for MarsRL)
    if USE_LANGFUSE:
        trace = langfuse.trace(
            name=f"route_and_execute/{intent['intent']}",
            session_id=session_id
        )
        parent_trace_id = trace.id
    
    # 4. Create ephemeral agent card
    ephemeral_card = EphemeralAgentCard(
        id=str(uuid.uuid4()),
        instance_id=f"{agent_template}-{uuid.uuid4().hex[:8]}",
        name=agent_template,
        role="Full Stack & System Engineer",
        security_level="L3_ADMIN",
        capabilities=["file_ops.write", "file_ops.read", "terminal.exec", "git.ops"],
        activated_capabilities=activated_capabilities,  # Task-specific subset
        activated_parameters=activated_parameters,
        session_id=session_id,
        created_by=get_spiffe_auth().get_spiffe_id(),
        parent_trace_id=parent_trace_id
    )
    
    # 5. Issue JWT token
    issuer = TokenIssuer()
    token = issuer.issue_token(ephemeral_card, parent_trace_id, ttl_seconds=600)
    
    # 6. Spawn ephemeral agent with token
    if agent_template == "Code Developer":
        agent = ArchitectAgent(token=token)
    
    # 7. Run MarsRL loop with agent
    mars_loop = MarsRLLoop(
        solver=agent,
        verifier=get_verifier(),
        corrector=get_corrector()
    )
    
    # 8. Execute with stream callback
    result = mars_loop.run(
        task=user_input,
        event_callback=lambda e: {
            **e,
            "agent_id": ephemeral_card.instance_id,
            "trace_id": parent_trace_id
        }
    )
    
    return result
```

---

## Part 5: Integration with Guardrails & Rewards

### 5.1 Guardrail Enforcement via Token Claims

**File: `agents/security_agent.py`** (MODIFIED)
```python
class SecurityAgent:
    """Enhanced with token-based capability awareness"""
    
    def scan_workflow(self, agent_token: str, task: str) -> SecurityCheckResult:
        """
        Scan task for unsafe patterns, aware of agent capabilities.
        """
        claims = TokenValidator().validate_token(agent_token)
        capabilities = claims["capabilities"]
        
        # Check 1: Does task ask agent to do something outside its capabilities?
        if "write file" in task and "file_ops.write" not in capabilities:
            return SecurityCheckResult(
                status="UNSAFE",
                reason="Task requires file_ops.write, agent lacks capability"
            )
        
        # Check 2: Pattern-based scanning (existing logic)
        for pattern in self.cmd_blocklist:
            if re.search(pattern, task):
                return SecurityCheckResult(
                    status="UNSAFE",
                    reason=f"Blocked pattern: {pattern}"
                )
        
        return SecurityCheckResult(status="SAFE")
```

### 5.2 Training Dataset Export with Agent Attribution

**File: `agents/mars_loop.py`** (MODIFIED)
```python
@observe(name="mars_loop")
def run(self, task: str, agent_token: str = None, ...):
    """MarsRL loop aware of agent identity"""
    
    # Extract agent metadata from token
    if agent_token:
        claims = TokenValidator().validate_token(agent_token)
        agent_id = claims["agent_id"]
        agent_name = claims["agent_name"]
    else:
        agent_id = "unknown"
        agent_name = "unknown"
    
    # Create trace with agent metadata
    trace = langfuse.trace(
        name="mars_loop",
        metadata={
            "agent_id": agent_id,
            "agent_name": agent_name,
            "capabilities": claims.get("capabilities"),
            "session_id": claims.get("session_id")
        }
    )
    
    for iteration in range(self.max_iter):
        solver_out = self.solver.run(task)
        langfuse.span(
            name="solver",
            output=solver_out,
            metadata={"agent_id": agent_id}
        )
        
        verifier_result = self.verifier.verify(solver_out)
        langfuse.span(
            name="verifier",
            score=verifier_result.score,
            metadata={"agent_id": agent_id}
        )
    
    return {...}

def export_training_dataset(self, session_id: str, agent_filter: str = None):
    """Export traces, optionally filtered by agent_id"""
    traces = langfuse.fetch_session_traces(session_id)
    
    dataset = []
    for trace in traces:
        agent_id = trace.metadata.get("agent_id")
        
        if agent_filter and agent_id != agent_filter:
            continue
        
        dataset.append({
            "agent_id": agent_id,
            "agent_name": trace.metadata.get("agent_name"),
            "input": trace.input,
            "solver_output": trace.steps[0].output,
            "verifier_score": trace.steps[1].metadata.score,
            "final_output": trace.output,
            "iterations": len(trace.steps) - 2
        })
    
    return dataset
```

---

## Part 6: Security Considerations

### 6.1 Token Lifetime Management

**Problem**: Ephemeral agents should have short-lived tokens to minimize blast radius

**Solution**:
```python
# Default: 10 minutes
token = issuer.issue_token(ephemeral_card, ttl_seconds=600)

# Task-specific override
if task_is_simple:
    token = issuer.issue_token(ephemeral_card, ttl_seconds=300)  # 5 min
elif task_is_complex:
    token = issuer.issue_token(ephemeral_card, ttl_seconds=1800) # 30 min
```

### 6.2 Privilege Escalation Protection

**Problem**: Rogue ephemeral agent tries to add new capabilities to itself

**Solution**:
```python
# Token is READ-ONLY
# Ephemeral agent can ONLY read capabilities from token

@CapabilityRequired("file_ops.write")
async def write_file(path, content, agent_token):
    # validator strictly checks token.claims["capabilities"]
    # Agent CANNOT modify claims, only present token as-is
    ...

# If agent tries: claims["capabilities"].append("git.ops")
# → Token signature becomes invalid (HMAC mismatch)
# → Next use of token fails
```

---

## Part 7: Comparison Matrix: JWT vs. Alternatives

| Approach | Complexity | Performance | Auditability | Scalability | Fits MAESTRO? |
|----------|-----------|-------------|-------------|------------|--------------|
| **JWT (Proposed)** | Medium | O(1) verify | ✅ Rich claims | ✅ Stateless | ✅ YES |
| **OAuth2 Client Credentials** | High | O(n) revocation check | ⚠️ Limited claims | ⚠️ Needs revocation server | ✅ Moderate |
| **Capability-Based Security** | Very High | O(k) cap traversal | ✅ Very rich | ✅ Composable | ✅ YES (overkill) |
| **API Keys only** | Very Low | O(1) lookup | ❌ No context | ❌ Requires central DB | ❌ NO |
| **Session-based (cookies)** | Low | O(n) session lookup | ⚠️ Limited | ❌ Stateful, doesn't scale | ❌ NO |

**Recommendation**: **JWT (Proposed)** — Best fit for your stateless, distributed swarm model

---

## Part 8: Open Questions for Detailed Design

### 1. Token Storage in Ephemeral Agent

**Options**:
- **In-memory only** (Lost on restart)
- **In Redis with short TTL** (Survives temporary pause)
- **In encrypted config file** (Persists across container restarts)

**Recommendation**: In-memory only for stateless ephemeral agents. If agent is paused/resumed, create new token.

### 2. Multi-Hop Spawning

**Question**: Can ephemeral agent "Code Developer" spawn a child ephemeral "Code Reviewer"?

**Recommendation**: Yes, but child token should:
- Inherit parent's trace_id (for atomicity)
- Have reduced capabilities (least privilege)
- Have shorter TTL (5 min vs. 10 min parent)

### 3. Capability Inheritance Hierarchy

**Question**: If parent has `["file_ops.write", "file_ops.read"]`, can child request only `["file_ops.read"]`?

**Recommendation**: Yes. Use `activated_capabilities` field for this. Child must be subset of parent.

### 4. Human-in-the-Loop Reward Injection

**Question**: When user submits manual reward via React, which token signs the update?

**Options**:
- User's token (from React auth)
- Ephemeral agent's token
- Separate "reward token" issued by auth system

**Recommendation**: Separate "human_reward_token" issued by auth middleware. More auditable.

### 5. Audit Log Retention

**Question**: How long to keep logs with agent_id, trace_id, capability, action?

**Recommendation**: Same as Langfuse retention (configurable, default 90 days). Consider GDPR limits.

### 6. Gradual Rollout

**Question**: Immediately wrap existing agents? Or convert to ephemeral spawning in Phase 2?

**Recommendation**: Wrap existing agents NOW for audit trail + guardrails. Convert to full ephemeral spawning during deployment Phase 1.

---

## Summary

**ACE-JWT provides**:
- ✅ Fine-grained capability enforcement (guardrails)
- ✅ Audit trail (every action tagged with agent_id)
- ✅ Training dataset attribution (per-agent performance)
- ✅ Stateless verification (SPIFFE-signed, offline-verifiable)
- ✅ Seamless MAESTRO integration (L7 identity at token creation, L4 at tool execution)

**Implementation Roadmap**:
1. **Phase 0**: Implement `token_issuer.py` and `capability_gate.py`
2. **Phase 1**: Integrate with router.py, extend SPIFFE signing
3. **Phase 2**: Link to MarsRL for training dataset export
4. **Phase 3**: Hardening (revocation list, HITL reward tokens)

**Next Step**: Answer Part 8 design questions, then proceed with implementation.

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `agents/security/token_issuer.py` | Implementation | JWT-ACE token issuance (implemented from this research) |
| `agents/security/capability_gate.py` | Implementation | Capability validation |
| `agents/security/execution_context.py` | Implementation | Thread-local token storage |
| [RFC 7519 — JWT](https://tools.ietf.org/html/rfc7519) | Standard | JSON Web Token specification |
| [SPIFFE](https://spiffe.io/) | Standard | Workload identity framework |

</details>

<details>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance notes |
| 2026-02-20 | AI-Copilot | JWT-ACE research and architecture spec |

</details>

---

## Maintenance Notes

This is a **research document**. The design questions in Part 8 have been answered during Phase 5 implementation. See `docs/specs/identity_layer_spec.md` for the final specification.
