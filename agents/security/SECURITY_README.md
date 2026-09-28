# Security System - Complete Reference

## Overview

This directory contains a production-ready JWT-based authorization system with capability gating for the Home_AI_Lab agent infrastructure. The system provides:

- **JWT Token Generation & Validation** - Secure token creation and verification
- **Capability-Based Access Control** - Fine-grained permission system
- **HTTP Authorization Middleware** - Automatic token validation on all API routes
- **Audit Logging** - Comprehensive security event tracking
- **Flexible Integration** - Works with FastAPI, REST APIs, and service-to-service calls

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  HTTP Request to /api/v1/resource                   │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────┐
│  AuthorizationMiddleware             │
│  - Extract JWT from header           │
│  - Validate signature & expiration   │
│  - Create agent_card from token      │
└────────────────┬─────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ Token Valid?       │
        └────┬─────────┬─────┘
      No│    │         │Yes
        │    ▼         ▼
        │  401/403   Agent Card attached
        │  Error     to request.state
        │             │
        │             ▼
        │  ┌──────────────────────────┐
        │  │ Route Handler executes   │
        │  │ (if no @CapabilityRequired)
        │  └──────────────────────────┘
        │             │
        ▼             ▼
    [End]     ┌──────────────────────────┐
              │ @CapabilityRequired?     │
              └────┬─────────────────┬───┘
            No│    │                 │Yes
              │    ▼                 ▼
              │  Execute      Check Capability
              │  Handler      (capability_gate)
              │    │               │
              │    │          ┌────┴────┐
              │    │  Has?    │          │No
              │    │    Yes◄──┘          ▼
              │    │    │           403 Forbidden
              │    │    │
              ▼    ▼    ▼
            [Response to Client]
              + Audit logging
              + Request timing
```

## File Structure

### Core Components

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `token_issuer.py` | JWT generation and validation | `TokenIssuer`, `EphemeralAgentCard`, `get_token_issuer()` |
| `capability_gate.py` | Capability-based access control decorator | `@CapabilityRequired`, `CapabilityValidator` |
| `authorization_middleware.py` | FastAPI middleware for auth enforcement | `AuthorizationMiddleware`, `AuthContext`, `get_auth_context()` |
| `audit_logger.py` | Security event logging | `AuditLogger`, `AuditEventType`, `get_audit_logger()` |
| `INTEGRATION_GUIDE.md` | Setup and usage documentation | Examples and patterns |

### Supporting Files

- `__init__.py` - Package initialization
- `middleware.py` - Additional middleware utilities
- `spiffe_auth.py` - SPIFFE/SPIRE integration (optional)

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi pyjwt uvicorn python-dotenv
```

### 2. Create `.env` File

```
JWT_SECRET_KEY=your-super-secret-key-minimum-32-characters
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### 3. Initialize in FastAPI App

```python
from fastapi import FastAPI
from agents.security.token_issuer import initialize_token_issuer
from agents.security.authorization_middleware import AuthorizationMiddleware

app = FastAPI()
app.add_middleware(AuthorizationMiddleware)

@app.on_event("startup")
async def startup():
    initialize_token_issuer(
        secret_key="your-secret-key",
        expiration_hours=24
    )
```

### 4. Add Authentication Endpoint

```python
from agents.security.token_issuer import get_token_issuer

@app.post("/api/v1/auth/token")
async def get_token(agent_name: str, password: str):
    issuer = get_token_issuer()
    token = issuer.issue_token(
        agent_name=agent_name,
        agent_instance_id=f"{agent_name}-{uuid.uuid4()}",
        capabilities=['file_read', 'file_write', 'model_generate']
    )
    return {"access_token": token, "token_type": "bearer"}
```

### 5. Protect Endpoints

```python
from agents.security.capability_gate import CapabilityRequired

@app.post("/api/v1/write-file")
@CapabilityRequired(capability='file_write')
async def write_file(path: str, content: str, request: Request):
    return {"status": "written", "agent": request.state.agent_name}
```

## Core Concepts

### JWT Token Structure

```python
{
    "agent_name": "worker-agent-1",
    "agent_instance_id": "worker-agent-1-a1b2c3d4",
    "activated_capabilities": ["file_read", "file_write", "model_generate"],
    "iss": "home_ai_lab",
    "exp": 1234567890,
    "iat": 1234567800,
    "jti": "unique-token-id"
}
```

### Capabilities

Standard capabilities defined in `capability_gate.STANDARD_CAPABILITIES`:

**File Operations:**
- `file_read` - Read files
- `file_write` - Write files
- `file_delete` - Delete files

**Execution:**
- `terminal_exec` - Execute commands
- `model_generate` - Generate with ML models

**API:**
- `api_call` - Make external calls
- `git_write` - Git operations

**System:**
- `resource_access` - GPU/memory
- `audit_read` - Read audit logs
- `db_admin` - Database admin

### Agent Card

Represents authenticated agent information:

```python
class EphemeralAgentCard:
    agent_name: str                        # Name of agent
    agent_instance_id: str                 # Unique instance ID
    activated_capabilities: List[str]      # Granted capabilities
    issued_at: float                       # Token creation time
    expiration_time: float                 # Token expiration
    # ... other fields
```

## Integration Patterns

### Pattern 1: HTTP Endpoint Protection

```python
@app.post("/api/v1/sensitive")
@CapabilityRequired(capability='file_write')
async def sensitive(request: Request):
    # Automatically validates JWT and capability
    agent = request.state.agent_name
    return {"status": "ok", "agent": agent}
```

### Pattern 2: Access Control in Handler

```python
from agents.security.authorization_middleware import get_auth_context

@app.get("/api/v1/data")
async def get_data(request: Request):
    auth = get_auth_context(request)
    
    if auth.has_capability('admin'):
        # Return sensitive data
        return {"data": "secret"}
    else:
        return {"data": "public"}
```

### Pattern 3: Service-to-Service

```python
from agents.security.capability_gate import CapabilityValidator

def internal_operation(token: str):
    validator = CapabilityValidator()
    if validator.check_capability(token, 'file_write'):
        # Proceed with operation
        pass
    else:
        raise PermissionError("Insufficient capabilities")
```

### Pattern 4: Audit Logging

```python
from agents.security.audit_logger import get_audit_logger

audit = get_audit_logger()
audit.log_operation_executed(
    agent_name="agent-1",
    agent_id="inst-123",
    operation="delete",
    resource="/data/file.csv",
    success=True
)
```

## API Reference

### Token Issuer

```python
# Issue token
token = issuer.issue_token(
    agent_name="worker-1",
    agent_instance_id="inst-123",
    capabilities=['file_read', 'file_write']
)

# Validate token
agent_card = issuer.validate_token(token)

# Revoke token
issuer.revoke_token(jti="token-id", reason="compromised")

# Check if token revoked
is_revoked = issuer.is_token_revoked(jti="token-id")
```

### Capability Gate

```python
# As decorator
@CapabilityRequired(capability='file_write', fallback_capability='admin')
async def protected_handler(request: Request):
    pass

# Programmatic validation
validator = CapabilityValidator()
has_capability = validator.check_capability(token, 'file_write')
```

### Authorization Middleware

```python
# Middleware auto-attaches to request.state:
# request.state.agent_card      # Full agent card
# request.state.agent_name      # Agent name
# request.state.agent_id        # Agent instance ID
# request.state.request_id      # Unique request ID

# Or use context helper
auth = get_auth_context(request)
auth.agent_name
auth.agent_id
auth.has_capability('file_write')
auth.get_capability_level()  # Returns: 'admin', 'operator', 'observer', 'none'
```

### Audit Logger

```python
audit = get_audit_logger()

# Log authentication
audit.log_auth_success(agent_name, agent_id, token_jti)
audit.log_auth_failed(reason="invalid_token")

# Log capability checks
audit.log_capability_granted(agent_name, agent_id, capability, resource)
audit.log_capability_denied(agent_name, agent_id, capability, resource)

# Log operations
audit.log_operation_executed(
    agent_name, agent_id, operation, resource, success=True
)

# Log token lifecycle
audit.log_token_issued(agent_name, agent_id, jti, capabilities, expires_at)
audit.log_token_revoked(agent_name, agent_id, jti, reason)

# Log configuration changes
audit.log_config_changed(agent_name, agent_id, key, old_value, new_value)
```

## Security Best Practices

### 1. Secret Key Management
- Generate strong random keys: `openssl rand -hex 32`
- Store in environment variables, never in code
- Rotate keys periodically
- Different keys for dev/staging/production

### 2. Token Lifecycle
- Keep expiration time short (1-24 hours)
- Implement token revocation for compromised tokens
- Auto-revoke on agent deactivation
- Provide refresh mechanism for long-running operations

### 3. Capability Design
- Use principle of least privilege
- Grant only necessary capabilities
- Review capability grants regularly
- Audit all capability changes

### 4. HTTPS/TLS
- Always use HTTPS in production
- Use strong TLS certificates (TLS 1.2+)
- Implement HSTS headers
- Keep certificates current

### 5. Rate Limiting
- Limit authentication attempts
- Protect against brute force attacks
- Rate limit per agent
- Monitor for suspicious patterns

### 6. Error Handling
- Never expose sensitive info in error messages
- Return generic errors to clients
- Log detailed errors server-side
- Monitor error patterns for attacks

### 7. Logging & Monitoring
- Log all authentication events
- Log all capability decisions
- Monitor audit logs for suspicious activity
- Set up alerts for failures

## Troubleshooting

### "Missing or invalid authorization header"
- Ensure client sends: `Authorization: Bearer <token>`
- Verify token is valid (not corrupted)
- Check token hasn't expired

### "Token has expired"
- Get new token from `/api/v1/auth/token`
- Implement token refresh mechanism
- Or increase expiration (if appropriate)

### "Insufficient capabilities"
- Verify token includes required capability
- Check capability name matches exactly (case-sensitive)
- Request admin to grant capability

### "Internal error: Request object not found"
- Decorator only works with async functions
- Ensure `request` parameter exists in signature
- Verify middleware is installed

### Audit logs not created
- Check log directory exists and writable
- Verify `get_audit_logger()` called
- Check file system permissions
- Try with absolute path

## Environment Variables

```
# JWT Configuration
JWT_SECRET_KEY=<your-secret-key>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Token Revocation
ENABLE_TOKEN_REVOCATION=true
REVOCATION_DB_PATH=./data/revoked_tokens.db

# Audit Logging
AUDIT_LOG_PATH=./logs/audit/audit.log

# Security
ENABLE_RATE_LIMITING=true
MAX_REQUESTS_PER_MINUTE=60
```

## Testing

Run the test script to verify the system:

```python
import requests

BASE = "http://localhost:8000"

# Get token
resp = requests.post(f"{BASE}/api/v1/auth/token", 
    params={"agent_name": "test", "password": "test"})
token = resp.json()["access_token"]

# Test protected endpoint
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(f"{BASE}/api/v1/self", headers=headers)
print(resp.json())

# Test capability gate
resp = requests.post(f"{BASE}/api/v1/write-file", headers=headers,
    params={"path": "/tmp/test.txt", "content": "hello"})
print(resp.json())
```

## File Size Reference

- `token_issuer.py`: ~500 lines (token generation, validation, revocation)
- `capability_gate.py`: ~400 lines (capability checking, decorator)
- `authorization_middleware.py`: ~350 lines (HTTP middleware, context)
- `audit_logger.py`: ~450 lines (event logging, audit trail)
- `INTEGRATION_GUIDE.md`: ~400 lines (setup and examples)

**Total: ~2,100 lines of production-ready security code**

## License

Part of Home_AI_Lab project. See project LICENSE file.

## Support

For issues or questions:
1. Check INTEGRATION_GUIDE.md for examples
2. Review code comments and docstrings
3. Check audit logs for security events
4. Consult troubleshooting section above

---

**Last Updated:** 2024
**Status:** Production Ready
**Version:** 1.0
