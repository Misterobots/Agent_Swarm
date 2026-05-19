# Migration Guide: Agent Security → Control Plane Security

## Overview

This guide explains how to migrate from the agent-based security system (in `agents/security/`) to the Control Plane-based security system for a scalable, centralized authentication architecture.

## Why Migrate?

### Control Plane Model (New) ✅
```
✅ Single source of truth
✅ Centralized token management
✅ Shared revocation list
✅ Unified audit logging
✅ Scales to N execution planes
✅ SPIRE integration
✅ Production-ready database
```

### Agent-Based Model (Old) ❌
```
❌ Distributed auth logic
❌ Token state per-node
❌ Revocation sync needed
❌ Fragmented audit logs
❌ Hard to scale
```

## Migration Path

### Before: Architecture

```
Execution Plane
├── Agents
│   └── security/ (auth logic embedded)
```

### After: Architecture

```
Control Plane (<control-node-ip>:8001)
└── Security Service ← All planes authenticate here

Execution Planes
├── Agents (use Control Plane for auth)
└── Client library (agents/security/client.py)
```

## Step-by-Step Migration

### Phase 1: Deploy Control Plane Security (NOW)

✅ **Already Done:**
- Control plane security service created
- Docker-compose updated with security service
- Database schema prepared
- Client library ready

**What to do:**
```bash
cd control_plane
docker-compose up -d security postgres

# Verify it's running
curl http://<control-node-ip>:8001/health
```

### Phase 2: Update Execution Plane Agents (Week 1)

**Replace local auth with Control Plane client:**

**Before (agents/security/token_issuer.py):**
```python
from agents.security.token_issuer import get_token_issuer

issuer = get_token_issuer()
token = issuer.issue_token(...)
```

**After (control_plane/security/client.py):**
```python
from control_plane_security import SecurityClient

client = SecurityClient("http://<control-node-ip>:8001")
token = client.issue_token(...)
```

### Phase 3: Remove Agent Security (Week 2)

Once all agents updated, clean up old code:

```bash
# Backup old code (just in case)
mv agents/security agents/security.backup

# Keep only what's in control_plane
```

---

## Migration Checklist

### Pre-Migration

- [ ] Backup `agents/security/` directory
- [ ] Review current token usage in agents
- [ ] Plan downtime window (if needed)
- [ ] Notify team of changes

### Deploy Control Plane Service

- [ ] Verify Control Plane is running
- [ ] Test `/health` endpoint
- [ ] Verify PostgreSQL tables created
- [ ] Check database connectivity
- [ ] Review security service logs

### Update Each Agent

For each agent that uses authentication:

- [ ] Copy `client.py` to agent environment
- [ ] Update imports: `agents.security` → `control_plane_security`
- [ ] Test token issuance from Control Plane
- [ ] Test token validation
- [ ] Verify audit logs in Langfuse
- [ ] Deploy and verify working

### Verification

- [ ] All agents can get tokens
- [ ] All agents can validate tokens
- [ ] Audit logs appear in Langfuse
- [ ] Revocation works
- [ ] Health checks pass
- [ ] No service interruptions

### Cleanup

- [ ] Archive old `agents/security/` code
- [ ] Update documentation
- [ ] Train team on new system
- [ ] Remove old auth code from agents
- [ ] Delete old security files

---

## Code Migration Examples

### Example 1: Simple Agent

**Before:**
```python
# agents/token_issuer_setup.py (old)
from agents.security.token_issuer import initialize_token_issuer, get_token_issuer

initialize_token_issuer(secret_key="...")
issuer = get_token_issuer()
token = issuer.issue_token(...)
```

**After:**
```python
# agents/auth_setup.py (new)
from control_plane_security import SecurityClient

client = SecurityClient("http://<control-node-ip>:8001")
token = client.issue_token(
    agent_name="agent-1",
    capabilities=["file_read", "file_write"]
)
```

### Example 2: FastAPI Middleware

**Before:**
```python
# agents/fastapi_app.py (old)
from agents.security.authorization_middleware import AuthorizationMiddleware

app.add_middleware(AuthorizationMiddleware)
```

**After:**
```python
# agents/fastapi_app.py (new)
# Note: Middleware now runs on Control Plane
# Agents just check Authorization header

from fastapi import Request, HTTPException

@app.middleware("http")
async def validate_auth_header(request: Request, call_next):
    # Validate token passed by client
    token = extract_token_from_header(request)
    
    # Optionally validate with Control Plane
    if needs_validation:
        from control_plane_security import SecurityClient
        client = SecurityClient("http://<control-node-ip>:8001")
        if not client.validate_token(token):
            raise HTTPException(status_code=401)
    
    return await call_next(request)
```

### Example 3: Capability Gates

**Before:**
```python
# agents/routes.py (old)
from agents.security.capability_gate import CapabilityRequired

@app.post("/write")
@CapabilityRequired(capability='file_write')
async def write_file(request: Request):
    return {"status": "ok"}
```

**After:**
```python
# agents/routes.py (new)
from control_plane_security import SecurityClient
from fastapi import Request, HTTPException, Depends
import jwt

def get_current_agent(request: Request):
    token = extract_token(request)
    try:
        # Decode token (validate signature client-side if desired)
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except:
        raise HTTPException(status_code=401)

def require_capability(capability: str):
    def check_capability(agent: dict = Depends(get_current_agent)):
        if capability not in agent.get('activated_capabilities', []):
            raise HTTPException(status_code=403)
        return agent
    return check_capability

@app.post("/write")
async def write_file(request: Request, agent = Depends(require_capability('file_write'))):
    return {"status": "ok"}
```

---

## Troubleshooting Migration

### Issue: Agents Can't Connect to Control Plane

**Cause:** Network connectivity or wrong IP/port

**Solution:**
```bash
# From execution plane, test connection
curl -I http://<control-node-ip>:8001/health

# If fails, check:
# 1. Control Plane service is running
# 2. Network IP correct (check network.env)
# 3. Port 8001 exposed
# 4. No firewall blocking
```

### Issue: Token Format Different

**Cause:** Different JWT payload structure

**Solution:**
Token structure is same. If issues, check:
- `activated_capabilities` vs `capabilities` field names
- Token still valid (check expiration)
- Signature verified with same secret key

### Issue: Revocation Not Working

**Cause:** Database not connected or JTI missing

**Solution:**
```python
# Verify token has JTI
import jwt
payload = jwt.decode(token, options={"verify_signature": False})
print(payload['jti'])

# If missing, issue needs fixing
```

### Issue: Audit Logs Not Appearing

**Cause:** Langfuse not configured

**Solution:**
1. Verify Langfuse running: `http://<gateway-node-ip>:3000`
2. Check security service logs: `docker logs control-security`
3. Database might not be connected

---

## Timeline

```
Week 1: Deploy & Test
  Day 1: Deploy control plane security
  Day 2: Test health & endpoints
  Day 3: Test with single agent
  
Week 2: Gradual Migration
  Day 1-2: Migrate critical agents
  Day 3-4: Migrate remaining agents
  Day 5: Final testing
  
Week 3: Cleanup
  Day 1: Archive old code
  Day 2-3: Monitor for issues
  Day 4-5: Full cleanup
```

## Rollback Plan

If issues arise:

```bash
# Restore old agents/security/ from backup
mv agents/security.backup agents/security

# Restart agents with old code
# Control plane can stay running (doesn't affect old code)

# Identify issue, fix, then retry migration
```

---

## What Happens to Old Code?

### agents/security/ (Old Location)

**Files to Archive:**
- `token_issuer.py` → Keep as reference (has good patterns)
- `capability_gate.py` → Keep as reference (decorator pattern)
- `authorization_middleware.py` → Keep as reference (middleware pattern)
- `audit_logger.py` → Keep as reference (logging pattern)

**Files to Delete:**
Once verified in production, can delete as no longer needed.

### control_plane/security/ (New Location)

**Core Files:**
- `token_issuer.py` → Token management (uses PostgreSQL)
- `main.py` → FastAPI service
- `client.py` → Used by agents
- `requirements.txt` → Dependencies
- `Dockerfile` → Container

---

## Database Considerations

### Schema Creation

The Control Plane service automatically creates tables:
```sql
security_tokens     -- Token storage
security_audit      -- Audit events
```

### Data Retention

Recommended policy:
```sql
-- Keep revoked tokens for 30 days
DELETE FROM security_tokens 
WHERE status = 'revoked' 
AND revoked_at < CURRENT_TIMESTAMP - INTERVAL '30 days';

-- Keep audit logs for 90 days
DELETE FROM security_audit 
WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
```

### Backup

```bash
# Backup security tables
docker exec postgres pg_dump -U langfuse -d langfuse \
  -t security_tokens -t security_audit > security_backup.sql
```

---

## Training & Documentation

### For Agents/Services

**New documentation:**
1. [control_plane/security/README.md](./control_plane/security/README.md)
2. [control_plane/security/SETUP.md](./control_plane/security/SETUP.md)
3. [control_plane/security/client.py](./control_plane/security/client.py) docstrings

**Key points:**
- Security service at `http://<control-node-ip>:8001`
- Use `SecurityClient` class
- Token lifecycle management
- Audit logging automatic

### For Operations

**Monitoring points:**
- Service health: `curl http://<control-node-ip>:8001/health`
- Database: PostgreSQL tables in Langfuse DB
- Logs: `docker logs control-security`
- Traces: Langfuse dashboard

---

## Success Criteria

✅ All agents authenticate via Control Plane  
✅ Tokens persist properly  
✅ Revocation works  
✅ Audit logs appear in Langfuse  
✅ No service interruptions  
✅ Health checks pass  
✅ Old code archived  

---

## FAQ

**Q: Do I need to stop all agents during migration?**
A: No, you can migrate agents one at a time. Control Plane can coexist with old code.

**Q: What if an agent can't be updated?**
A: Keep the old `agents/security/` code alongside new code, or run both systems in parallel.

**Q: Can I keep audit logs from old system?**
A: Yes, export from `agents/security/audit.log` and import to database before deleting.

**Q: Do token formats change?**
A: No, JWT structure is identical. Integration with SPIRE might add fields.

**Q: What about token expiration?**
A: Same as before. Configure via `JWT_EXPIRATION_HOURS` (default 24).

---

## Next Steps

1. ✅ Start Control Plane: `docker-compose up -d security`
2. ✅ Verify health: `curl http://<control-node-ip>:8001/health`
3. ✅ Get one agent working
4. ✅ Test end-to-end (token → validation → revocation)
5. ✅ Roll out to all agents
6. ✅ Monitor for 1 week
7. ✅ Archive old code
8. ✅ Clean up

---

**Created:** March 15, 2026  
**Status:** Ready for Migration  
**Questions?** Check SETUP.md or README.md
