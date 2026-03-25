# Control Plane Security Service - Setup & Integration Guide

## Overview

The Control Plane Security Service is a centralized JWT token issuer running on the Control Plane (<control-node-ip>). It serves tokens to all Execution Planes and validates their requests.

## Architecture

```
┌──────────────────────────────────┐
│  Execution Plane (<execution-node-ip>) │
│  - Agents running                │
│  - Requests tokens               │
│  - Uses JWT for auth             │
└──────────────┬───────────────────┘
               │ HTTP Request to
               │ /api/security/v1/token
               │
               ▼
┌────────────────────────────────────────────┐
│  Control Plane (<control-node-ip>) ⭐          │  
│  ┌──────────────────────────────────────┐  │
│  │  Security Service (Port 8001)        │  │
│  │  - Issues JWT tokens                 │  │
│  │  - Validates tokens                  │  │
│  │  - Revokes tokens                    │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  PostgreSQL Database                 │  │
│  │  - Token storage                     │  │
│  │  - Revocation list                   │  │
│  │  - Audit logs                        │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  SPIRE Server                        │  │
│  │  - Identity validation               │  │
│  │  - Agent certificates                │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  Langfuse                            │  │
│  │  - Audit event logging               │  │
│  │  - Compliance tracking               │  │
│  └──────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Setup

### 1. Start Control Plane

```bash
cd control_plane
docker-compose up -d
```

This starts:
- PostgreSQL (database)
- SPIRE (identity)
- Langfuse (observability)
- **Security Service** (port 8001)

### 2. Verify Service is Running

```bash
curl http://<control-node-ip>:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "control-plane-security",
  "version": "1.0"
}
```

### 3. Get API Documentation

Visit: `http://<control-node-ip>:8001/docs` (Swagger UI)

## API Endpoints

### Issue Token

**Endpoint:** `POST /api/security/v1/token`

Request:
```bash
curl -X POST "http://<control-node-ip>:8001/api/security/v1/token" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "worker-1",
    "capabilities": ["file_read", "file_write", "model_generate"],
    "agent_instance_id": "worker-1-inst-123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "agent_instance_id": "worker-1-inst-123",
  "expires_in": 86400
}
```

### Validate Token

**Endpoint:** `POST /api/security/v1/validate`

Request:
```bash
curl -X POST "http://<control-node-ip>:8001/api/security/v1/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

Response:
```json
{
  "valid": true,
  "agent_name": "worker-1",
  "agent_instance_id": "worker-1-inst-123",
  "capabilities": ["file_read", "file_write", "model_generate"],
  "expires_at": 1710519600
}
```

### Revoke Token

**Endpoint:** `POST /api/security/v1/revoke`

Request:
```bash
curl -X POST "http://<control-node-ip>:8001/api/security/v1/revoke" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "reason": "agent_deactivated"
  }'
```

Response:
```json
{
  "status": "revoked",
  "jti": "abc123def456",
  "reason": "agent_deactivated"
}
```

## Integration with Execution Plane

### In Execution Plane Agents

```python
import requests

# 1. Get token from security service
def get_auth_token(agent_name: str) -> str:
    response = requests.post(
        "http://<control-node-ip>:8001/api/security/v1/token",
        json={
            "agent_name": agent_name,
            "capabilities": [
                "file_read",
                "file_write",
                "model_generate",
                "api_call"
            ]
        },
        timeout=5
    )
    response.raise_for_status()
    return response.json()["access_token"]

# 2. Use token in requests
def make_authenticated_request(endpoint: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(endpoint, headers=headers)
    return response.json()

# 3. Usage
token = get_auth_token("agent-worker-1")
result = make_authenticated_request(
    "http://<execution-node-ip>:8008/api/v1/models",
    token
)
```

## Standard Capabilities

| Capability | Description |
|------------|-------------|
| `file_read` | Read files from filesystem |
| `file_write` | Write files to filesystem |
| `file_delete` | Delete files |
| `model_generate` | Generate with ML models |
| `terminal_exec` | Execute shell commands |
| `api_call` | Make external API calls |
| `git_write` | Push to git repositories |
| `resource_access` | Access GPU/memory resources |
| `audit_read` | Read audit logs |
| `db_admin` | Database administrative access |

Assign only the capabilities each agent needs (principle of least privilege).

## Configuration

Edit `control_plane/security/.env`:

```
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-minimum-32-characters
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_URL=postgresql://langfuse:langfuse_password@postgres:5432/langfuse

# Logging
LOG_LEVEL=INFO
```

## Monitoring

### View Token Audit Logs

```bash
# Connect to PostgreSQL
docker exec -it postgres psql -U langfuse -d langfuse

# View audit events
SELECT * FROM security_audit ORDER BY timestamp DESC LIMIT 20;

# View issued tokens
SELECT jti, agent_name, capabilities, issued_at, expires_at, status 
FROM security_tokens 
ORDER BY issued_at DESC;
```

### View in Langfuse Dashboard

1. Go to `http://<gateway-node-ip>:3000` (Langfuse on Gateway Node)
2. Token issuance events appear as traces
3. Failed authentications logged as errors
4. Capability denials tracked for compliance

## Troubleshooting

### Service Not Starting

```bash
# Check logs
docker logs control-security

# Verify database connection
docker exec control-security psql -c "SELECT 1" postgresql://langfuse:langfuse_password@postgres:5432/langfuse
```

### Token Generation Fails

**Issue:** `Cannot connect to database`

**Solution:**
1. Verify PostgreSQL is running: `docker ps | grep postgres`
2. Check .env has correct DATABASE_URL
3. Restart service: `docker restart control-security`

### Token Validation Always Fails

**Issue:** `Invalid or expired token`

**Solution:**
1. Verify JWT_SECRET_KEY is same where token was issued
2. Check token hasn't expired (`exp` claim)
3. Verify no typos in Authorization header

## Security Best Practices

1. **Keep JWT_SECRET_KEY secure**
   - Never commit to git
   - Use strong random key (32+ characters)
   - Rotate periodically

2. **Use HTTPS in production**
   - Security service should only be accessed via HTTPS
   - Set up TLS certificates

3. **Short token expiration**
   - 24 hours for long-lived agents
   - 1 hour for short-lived tasks
   - Implement refresh mechanism

4. **Revoke tokens for deactivated agents**
   - Call `/revoke` when agent is deactivated
   - Prevents unauthorized access

5. **Monitor audit logs**
   - Check for failed authentication attempts
   - Alert on suspicious patterns
   - Review regularly

## Integration with SPIRE (Advanced)

The security service can validate SPIRE identities before issuing tokens:

```python
# In token_issuer.py
def issue_token(..., spire_svid: Optional[str] = None):
    if spire_svid:
        # Validate SPIRE identity
        validate_spire_certificate(spire_svid)
    # ... then issue token
```

This provides:
- Cryptographic identity verification
- Automatic certificate rotation
- Agent workload attestation

## Database Schema

The security service creates two tables:

### security_tokens
```sql
CREATE TABLE security_tokens (
    jti VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255),
    agent_instance_id VARCHAR(255),
    capabilities TEXT,  -- JSON array
    issued_at TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR(50),  -- 'active' or 'revoked'
    revoked_at TIMESTAMP,
    revoke_reason TEXT
);
```

### security_audit
```sql
CREATE TABLE security_audit (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    event_type VARCHAR(50),  -- TOKEN_ISSUED, AUTH_FAILED, etc
    agent_name VARCHAR(255),
    agent_id VARCHAR(255),
    details JSONB,
    success BOOLEAN
);
```

## Scaling

As you add more execution planes:

1. All planes authenticate to **single Control Plane**
2. No state sync needed (stateless JWT)
3. Database handles revocation list
4. Audit logs centralized in Langfuse

```
┌─────────────────────────┐
│ Control Plane (8001)    │
│ (Single source of truth)│
└────────┬────────┬───────┘
         │        │
         ▼        ▼
    ┌────────┐ ┌────────┐
    │ Exec 1 │ │ Exec 2 │
    │        │ │        │
    │ Agents │ │ Agents │
    └────────┘ └────────┘
    
    Future: Add Exec 3, 4, ... easily
```

## Support

For issues:
1. Check service logs: `docker logs control-security`
2. Verify database access: `docker exec -it postgres psql ...`
3. Check Langfuse traces: `http://<gateway-node-ip>:3000`
4. Review this guide's troubleshooting section

---

**Status:** ✅ Production Ready

**Version:** 1.0

**Location:** Control Plane (<control-node-ip>:8001)
