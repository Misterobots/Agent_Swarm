# Control Plane Security Service - Implementation

## 📋 Overview

This directory contains the centralized JWT authentication system for the Home AI Lab multi-plane architecture. The security service runs on the Control Plane (192.168.2.102) and provides token issuance, validation, and capability management for all Execution Planes.

## 🏗️ Architecture

```
Execution Planes            Control Plane              External Services
───────────────             ─────────────              ─────────────────

Agent 1 ────┐                                 
Agent 2 ────┼─── (Request Token) ──────────► Security Service
Agent N ────┘                                   (8001)
                                                 │
                                            ┌────┴────┬───────┐
                                            ▼         ▼       ▼
                                        PostgreSQL  SPIRE  Langfuse
                                        (Storage)  (ID)    (Audit)
```

**Key Benefits:**
- ✅ Single source of truth for authentication
- ✅ Centralized token revocation
- ✅ Unified audit logging
- ✅ Scales to multiple execution planes
- ✅ Integrates with SPIRE identity
- ✅ PostgreSQL persistence
- ✅ Langfuse observability

## 📁 File Structure

```
control_plane/security/
├── main.py                 # FastAPI service
├── token_issuer.py         # Token generation/validation
├── client.py              # Execution plane client library
├── Dockerfile             # Container image
├── requirements.txt       # Python dependencies
├── .env                   # Configuration
├── SETUP.md              # Setup instructions
└── README.md             # This file
```

## 🚀 Quick Start

### 1. Start Control Plane

```bash
cd control_plane
docker-compose up -d
```

### 2. Verify Running

```bash
curl http://192.168.2.102:8001/health
```

Response: `{"status": "healthy", "service": "control-plane-security", "version": "1.0"}`

### 3. In Execution Plane Agent

```python
from control_plane_security import SecurityClient

# Connect to security service
client = SecurityClient("http://192.168.2.102:8001")

# Get token
token = client.issue_token(
    agent_name="my-agent",
    capabilities=["file_read", "file_write"]
)

# Use token in requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(endpoint, headers=headers)
```

## 📡 API Endpoints

All endpoints are HTTP POST (except health check)

### POST /api/security/v1/token
Issue JWT token for agent

**Request:**
```json
{
  "agent_name": "worker-1",
  "capabilities": ["file_read", "file_write"],
  "agent_instance_id": "optional-id"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "agent_instance_id": "worker-1-...",
  "expires_in": 86400
}
```

### POST /api/security/v1/validate
Validate JWT token

**Request:**
```json
{
  "token": "eyJhbGc..."
}
```

**Response:**
```json
{
  "valid": true,
  "agent_name": "worker-1",
  "capabilities": ["file_read", "file_write"],
  "expires_at": 1710519600
}
```

### POST /api/security/v1/revoke
Revoke token (for deactivated agents)

**Request:**
```json
{
  "token": "eyJhbGc...",
  "reason": "agent_deactivated"
}
```

**Response:**
```json
{
  "status": "revoked",
  "jti": "abc123",
  "reason": "agent_deactivated"
}
```

### GET /health
Health check

**Response:**
```json
{
  "status": "healthy",
  "service": "control-plane-security",
  "version": "1.0"
}
```

## 🔧 Configuration

Edit `control_plane/security/.env`:

```env
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-minimum-32-characters
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_URL=postgresql://langfuse:langfuse_password@postgres:5432/langfuse

# Logging
LOG_LEVEL=INFO
```

**Important:** Keep `JWT_SECRET_KEY` secret! Never commit to git.

## 💾 Database

The service creates two tables in PostgreSQL:

### security_tokens
Stores issued tokens for revocation checking

| Column | Type | Purpose |
|--------|------|---------|
| jti | UUID | Unique token ID |
| agent_name | String | Agent name |
| agent_instance_id | String | Unique instance ID |
| capabilities | JSON | Granted capabilities list |
| issued_at | Timestamp | Token creation time |
| expires_at | Timestamp | Token expiration |
| status | String | 'active' or 'revoked' |

### security_audit
Logs all security events

| Column | Type | Purpose |
|--------|------|---------|
| id | Serial | Event ID |
| timestamp | Timestamp | Event time |
| event_type | String | TOKEN_ISSUED, AUTH_FAILED, etc |
| agent_name | String | Agent involved |
| agent_id | String | Agent instance ID |
| details | JSON | Event details |
| success | Boolean | Whether successful |

## 📦 Client Library (client.py)

Use in Execution Planes to interact with security service.

### Basic Usage

```python
from control_plane_security import SecurityClient

client = SecurityClient("http://192.168.2.102:8001")

# Issue token
token = client.issue_token(
    agent_name="worker-1",
    capabilities=["file_read", "file_write"]
)

# Validate token
if client.validate_token(token):
    print("Token valid!")

# Get token details
details = client.validate_token_detailed(token)
print(f"Agent: {details['agent_name']}")
print(f"Capabilities: {details['capabilities']}")

# Revoke token
client.revoke_token(token, reason="agent_deactivated")
```

### Authenticated Requests

```python
from control_plane_security import AuthenticatedRequest

# Create authenticated request helper
auth = AuthenticatedRequest(
    client=client,
    agent_name="worker-1",
    capabilities=["file_read", "file_write"]
)

# Automatic token handling
response = auth.get("http://api.example.com/data")
response = auth.post("http://api.example.com/action", json={"key": "value"})
```

## 🔐 Security Features

### Token Design
- **JWT-based:** Industry standard, stateless
- **Expiration:** Short-lived (default 24 hours)
- **Revocation:** Blacklist in PostgreSQL
- **Audit:** Every operation logged

### Capability System
Standard capabilities:
- `file_read`, `file_write`, `file_delete`
- `model_generate`, `terminal_exec`
- `api_call`, `git_write`
- `resource_access`, `audit_read`, `db_admin`

Custom capabilities can be added as needed.

### Best Practices
1. ✅ Use strong secret key (32+ random characters)
2. ✅ Keep secrets in environment variables
3. ✅ Use HTTPS in production
4. ✅ Short token expiration (1-24 hours)
5. ✅ Principle of least privilege
6. ✅ Monitor audit logs
7. ✅ Revoke tokens for deactivated agents

## 📊 Monitoring

### Docker Logs

```bash
docker logs control-security
```

### Database Queries

```bash
# Connect to DB
docker exec -it postgres psql -U langfuse -d langfuse

# View recent audit events
SELECT * FROM security_audit ORDER BY timestamp DESC LIMIT 20;

# View active tokens
SELECT agent_name, capabilities, expires_at, status 
FROM security_tokens 
WHERE status = 'active' AND expires_at > CURRENT_TIMESTAMP;

# View token revocations
SELECT * FROM security_tokens WHERE status = 'revoked';
```

### Langfuse Integration

All security events are logged to Langfuse (192.168.2.103:3000):
- Token issuance
- Authentication failures
- Audit events
- Compliance tracking

## 🜔 Troubleshooting

### Service Won't Start

**Error:** `Cannot connect to database`

**Solution:**
```bash
# Check database is running
docker ps | grep postgres

# Verify DATABASE_URL in .env
# Should be: postgresql://langfuse:langfuse_password@postgres:5432/langfuse

# Restart service
docker restart control-security
```

### Token Generation Fails

**Error:** `HTTP 500 Internal Server Error`

**Solution:**
1. Check logs: `docker logs control-security`
2. Verify .env variables are set
3. Verify PostgreSQL accessibility
4. Check JWT_SECRET_KEY is not empty

### Token Validation Always Fails

**Error:** `Invalid or expired token`

**Solution:**
1. Verify JWT_SECRET_KEY is identical
2. Check token hasn't expired (decode and check `exp`)
3. Verify Authorization header format: `Bearer <token>`

## 🚀 Scaling

The design scales to multiple execution planes:

```
Control Plane (Single)
    ↓
    ├─→ Execution Plane 1
    ├─→ Execution Plane 2
    ├─→ Execution Plane 3
    └─→ ... N planes

Token storage centralized in PostgreSQL
Audit logs centralized in Langfuse
```

No changes needed - just add more execution planes!

## 📚 Integration Examples

### Example 1: Agent with Fixed Capabilities

```python
def initialize_agent():
    client = SecurityClient("http://192.168.2.102:8001")
    
    # Get token once
    token = client.issue_token(
        agent_name="data-processor",
        capabilities=["file_read", "file_write"]
    )
    
    # Store for session
    return token

def do_work(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://api.internal/data", headers=headers)
    return response.json()
```

### Example 2: Service-to-Service Call

```python
def call_other_service(agent_name):
    client = SecurityClient("http://192.168.2.102:8001")
    
    # Get token with required capabilities
    token = client.issue_token(
        agent_name=agent_name,
        capabilities=["api_call"]
    )
    
    # Make authenticated call
    auth = AuthenticatedRequest(client, agent_name, ["api_call"])
    response = auth.post(
        "http://other-service:8000/api/action",
        json={"data": "value"}
    )
    
    return response.json()
```

### Example 3: Temporary Token for Task

```python
def run_temporary_task(task_id):
    client = SecurityClient("http://192.168.2.102:8001")
    
    # Issue short-lived token for task
    token = client.issue_token(
        agent_name=f"task-{task_id}",
        capabilities=["file_read"]
    )
    
    try:
        # Run task with token
        result = process_with_token(token)
        return result
    finally:
        # Revoke token when done
        client.revoke_token(token, reason=f"task_{task_id}_complete")
```

## 📖 Documentation

- `SETUP.md` - Detailed setup and integration guide
- `token_issuer.py` - Token generation/validation (docstrings)
- `main.py` - FastAPI service (docstrings)
- `client.py` - Client library (docstrings)

## 🎯 Testing the Service

```bash
# Test with curl
curl -X POST "http://192.168.2.102:8001/api/security/v1/token" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "test-agent",
    "capabilities": ["file_read", "file_write"]
  }'

# Test with Python client
python -m control_plane.security.client http://192.168.2.102:8001
```

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-15 | Initial release, JWT token service |

## ✅ Status

- **Status:** Production Ready
- **Location:** Control Plane (192.168.2.102:8001)
- **Database:** PostgreSQL in Control Plane
- **Observability:** Langfuse integration
- **Scaling:** Ready for multiple execution planes

## 🤝 Contributing

To extend the security service:

1. Add new capabilities to `STANDARD_CAPABILITIES` in token_issuer.py
2. Add new audit event types to client.py
3. Create custom decorators for FastAPI routes
4. Update DATABASE_URL for new database locations

## 📞 Support

For issues:
1. Check service logs: `docker logs control-security`
2. Check database access: `docker exec postgres psql ...`
3. Review SETUP.md troubleshooting section
4. Check Configuration section of this README

---

**Created:** March 15, 2026  
**Status:** ✅ Production Ready  
**Version:** 1.0
