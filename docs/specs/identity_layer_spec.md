# Specification: Identity Layer (MAESTRO L7)

**Version**: 2.0
**Date**: 2026-03-17
**Status**: Implemented

## 1. Overview

The Identity Layer enforces strict authentication for all external entities (IDEs, CI/CD pipelines) communicating with the Agent Swarm. It moves beyond "trusting the network" to "trusting the credential".

## 2. Architecture

### 2.1 Credential Injection

- **Source**: Docker Compose (`execution_plane/docker-compose.yml`)
- **Mechanism**: Environment Variables
  - `agent-runtime`: `VALID_API_KEYS={"key": "identity"}`
  - `agent_ide_coding`: `SWARM_API_KEY=sk-coder-...`
- **Security**: Secrets are not committed to code (except dev defaults in this repo).

### 2.2 Transport Security

- **Protocol**: HTTP (Internal Docker Network)
- **Header**: `X-Swarm-Source` containing the API Key.

### 2.3 Enforcement Logic

- **Component**: `agents/main.py` (FastAPI)
- **Flow**:
  1.  Request arrives at `/api/v1/request`.
  2.  `create_request` handler extracts `X-Swarm-Source`.
  3.  Validates key against loaded `VALID_API_KEYS`.
  4.  If Valid -> Resolves `user_id` (e.g. `coding_user`).
  5.  If Invalid -> Returns 401 Unauthorized.
  6.  System forwards resolved `user_id` to Governance Manager.

## 3. Data Model

### API Key Map

```json
{
  "sk-coder-identity": "coding_user",
  "sk-devops-identity": "devops_user"
}
```

## 4. Usage

### Client (Python)

```python
import os, urllib.request
headers = {'X-Swarm-Source': os.getenv('SWARM_API_KEY')}
req = urllib.request.Request(url, headers=headers)
```

## 5. JWT-ACE: Agent Card Embedded JWT (Phase 5)

### 5.1 Overview

JWT-ACE extends the identity layer from static API keys to per-request ephemeral tokens with embedded agent capability claims. Each agent request gets a short-lived JWT containing:

- Template ID and version
- Activated capabilities list
- Security level (L1_PUBLIC through L4_SYSTEM)
- Agent instance ID (unique per request)
- Expiry (default 1 hour)

### 5.2 Token Architecture

- **Signing**: HS256 with shared secret (SPIRE RS256 fallback when available)
- **Issuer**: `home-ai-lab-token-issuer`
- **Audience**: `home-ai-lab-agents`
- **Claims**: template_id, template_version, agent_name, agent_instance_id, activated_capabilities, security_level, session_id, metadata

### 5.3 Token Flow

1. User request arrives at router
2. Semantic router classifies intent (CODE, IMAGE, 3D, etc.)
3. Intent mapped to capabilities via `intent_capabilities.py`
4. TokenIssuer creates JWT with capability claims
5. Token set in thread-local execution context
6. Agent executes with token available for tool gating
7. Token cleared after execution

### 5.4 Capability Enforcement

- CapabilityValidator checks JWT claims against required capabilities
- Tools can optionally validate via thread-local token context
- Fallback capabilities supported (e.g., db_admin satisfies db_write)
- Non-breaking: tools work unchanged if no token is set

### 5.5 Security Levels

| Level | Name | Description |
|-------|------|-------------|
| L1_PUBLIC | Public | Read-only, model_generate only |
| L2_USER | User | Standard tool access |
| L3_ADMIN | Admin | File write, terminal exec, git operations |
| L4_SYSTEM | System | Full access including system operations |

### 5.6 Intent-to-Capability Mapping

8 intents mapped: CODE (L3_ADMIN), IMAGE (L2_USER), 3D (L2_USER), RESEARCH (L1_PUBLIC), DOCUMENTATION (L2_USER), TRAIN (L2_USER), IOT_CONTROL (L2_USER), IOT_DEV (L3_ADMIN)

### 5.7 Implementation Files

- `agents/security/token_issuer.py` — TokenIssuer, TokenValidator, EphemeralAgentCard
- `agents/security/capability_gate.py` — CapabilityValidator, @CapabilityRequired decorator
- `agents/security/execution_context.py` — Thread-local token storage
- `agents/intent_capabilities.py` — Intent-to-capability mapping
- `agents/router.py` — Token issuance integration point
