"""
SECURITY SYSTEM INTEGRATION GUIDE
==================================

This guide shows how to integrate all security components into your FastAPI
application for comprehensive JWT-based authorization with capability gating.

Complete Feature Set:
✓ JWT token generation (token_issuer.py)
✓ Token validation and verification (token_issuer.py)
✓ Capability-based access control (capability_gate.py)
✓ HTTP middleware authorization (authorization_middleware.py)
✓ Comprehensive audit logging (audit_logger.py)
"""

# ============================================================================
# 1. QUICK START
# ============================================================================

"""
MINIMAL SETUP FOR FASTAPI APPLICATION:

from fastapi import FastAPI, Request
from agents.security.token_issuer import TokenIssuer, get_token_issuer
from agents.security.authorization_middleware import AuthorizationMiddleware
from agents.security.capability_gate import CapabilityRequired

app = FastAPI()

# Add authorization middleware (runs on every request)
app.add_middleware(AuthorizationMiddleware)

# Now all /api/* routes require valid JWT token

@app.post("/api/v1/authenticate")
async def authenticate(agent_name: str, agent_id: str) -> dict:
    # Issue token for agent
    issuer = get_token_issuer()
    token = issuer.issue_token(
        agent_name=agent_name,
        agent_instance_id=agent_id,
        capabilities=['file_read', 'file_write']
    )
    return {"token": token, "type": "bearer"}

@app.get("/api/v1/protected")
async def protected_endpoint(request: Request):
    # request.state.agent_card contains validated agent info
    agent_name = request.state.agent_name
    return {"message": f"Hello, {agent_name}!"}

@app.post("/api/v1/sensitive")
@CapabilityRequired(capability='file_write')
async def sensitive_operation(request: Request, data: str):
    # Only executes if JWT has 'file_write' capability
    return {"status": "success", "agent": request.state.agent_name}
"""


# ============================================================================
# 2. SETUP STEPS
# ============================================================================

"""
Step 1: Initialize token issuer in your app startup
---------------------------------------------------
"""

from fastapi import FastAPI
from agents.security.token_issuer import initialize_token_issuer, get_token_issuer

def init_security():
    # Initialize token issuer (call once during app startup)
    initialize_token_issuer(
        secret_key="your-secret-key-keep-this-safe",
        expiration_hours=24,
        algorithm="HS256"
    )
    
    print("Security system initialized")

# Call during app startup
app = FastAPI()

@app.on_event("startup")
async def startup():
    init_security()


"""
Step 2: Add authorization middleware
------------------------------------
"""

from agents.security.authorization_middleware import AuthorizationMiddleware

app.add_middleware(AuthorizationMiddleware)

# Now all requests to /api/* routes will go through authorization


"""
Step 3: Add authentication endpoint
-----------------------------------
"""

from agents.security.token_issuer import get_token_issuer

@app.post("/api/v1/auth/token")
async def get_auth_token(agent_name: str, agent_id: str) -> dict:
    """
    Issue JWT token for agent.
    
    In production:
    - Verify agent credentials
    - Check agent exists in system
    - Get allowed capabilities from agent database
    """
    issuer = get_token_issuer()
    
    # Get capabilities for agent (from your agent database)
    capabilities = ['file_read', 'file_write', 'model_generate']
    
    token = issuer.issue_token(
        agent_name=agent_name,
        agent_instance_id=agent_id,
        capabilities=capabilities
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400  # seconds
    }


"""
Step 4: Protect endpoints with capability requirements
-----------------------------------------------------
"""

from agents.security.capability_gate import CapabilityRequired
from fastapi import Request

@app.post("/api/v1/files/write")
@CapabilityRequired(capability='file_write')
async def write_file(path: str, content: str, request: Request):
    # Only executes if JWT has 'file_write' capability
    agent = request.state.agent_name
    return {"file": path, "status": "written", "agent": agent}

@app.delete("/api/v1/files/{file_id}")
@CapabilityRequired(capability='file_delete', fallback_capability='admin')
async def delete_file(file_id: str, request: Request):
    # Executes if JWT has 'file_delete' OR 'admin' capability
    return {"file_id": file_id, "status": "deleted"}

@app.get("/api/v1/models/generate")
@CapabilityRequired(capability='model_generate')
async def generate_with_model(prompt: str, request: Request):
    # Only for agents with model_generate capability
    return {"prompt": prompt, "output": "generated content"}


"""
Step 5: Access agent information in handlers
--------------------------------------------
"""

from agents.security.authorization_middleware import get_auth_context

@app.get("/api/v1/status")
async def status(request: Request):
    auth = get_auth_context(request)
    
    return {
        "agent_name": auth.agent_name,
        "agent_id": auth.agent_id,
        "request_id": auth.request_id,
        "capabilities": ["check via agent_card"],
        "capability_level": auth.get_capability_level()
    }


# ============================================================================
# 3. USAGE PATTERNS
# ============================================================================

"""
PATTERN 1: Validate token programmatically (non-HTTP)
----------------------------------------------------
"""

from agents.security.capability_gate import CapabilityValidator

def validate_agent_action(token: str, required_capability: str) -> bool:
    validator = CapabilityValidator()
    return validator.check_capability(
        token=token,
        required_capability=required_capability
    )


"""
PATTERN 2: Log audit events
---------------------------
"""

from agents.security.audit_logger import get_audit_logger

def audit_sensitive_operation():
    audit = get_audit_logger()
    
    # Log operation execution
    audit.log_operation_executed(
        agent_name="agent-1",
        agent_id="inst-123",
        operation="delete",
        resource="/data/sensitive.csv",
        success=True,
        request_id="req-123",
        details={"reason": "cleanup"}
    )
    
    # Log capability grant
    audit.log_capability_granted(
        agent_name="agent-2",
        agent_id="inst-456",
        capability="file_write",
        resource="/api/v1/files/write",
        endpoint="/api/v1/files/write"
    )


"""
PATTERN 3: Extract auth context in middleware/handler
-----------------------------------------------------
"""

from agents.security.authorization_middleware import AuthContext
from fastapi import Request

async def my_handler(request: Request):
    auth = AuthContext(request)
    
    # Check if agent has capability
    if auth.has_capability('admin'):
        # Allow admin-only action
        pass
    
    # Get capability level
    level = auth.get_capability_level()  # 'admin', 'operator', 'observer', 'none'
    
    # Access agent card directly
    if auth.agent_card:
        print(f"Agent: {auth.agent_card.agent_name}")
        print(f"Capabilities: {auth.agent_card.activated_capabilities}")


"""
PATTERN 4: Service-to-service authorization
--------------------------------------------
"""

def service_call_with_auth(token: str, required_capability: str):
    from agents.security.capability_gate import CapabilityValidator
    
    validator = CapabilityValidator()
    
    # Check if token grants required capability
    if validator.check_capability(token, required_capability):
        # Proceed with operation
        return perform_operation()
    else:
        raise PermissionError(f"Token missing {required_capability}")


# ============================================================================
# 4. COMPLETE EXAMPLE APPLICATION
# ============================================================================

"""
See below for a complete working example
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

# Create app
app = FastAPI(title="Secure Agent API")

# Add middleware
from agents.security.authorization_middleware import AuthorizationMiddleware
app.add_middleware(AuthorizationMiddleware)

# Initialize security on startup
@app.on_event("startup")
async def startup_event():
    from agents.security.token_issuer import initialize_token_issuer
    initialize_token_issuer(
        secret_key="dev-secret-key-change-in-production",
        expiration_hours=24
    )


# Public endpoints (bypass authentication middleware)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/api/v1/auth/token")
async def issue_token(agent_name: str, password: str) -> dict:
    """
    Issue authentication token.
    In production, verify password before issuing.
    """
    # Simplified - in production verify credentials
    if not agent_name or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing agent_name or password"
        )
    
    from agents.security.token_issuer import get_token_issuer
    issuer = get_token_issuer()
    
    # Determine capabilities based on agent type
    capabilities = ['file_read', 'file_write', 'model_generate']
    
    token = issuer.issue_token(
        agent_name=agent_name,
        agent_instance_id=f"{agent_name}-{__import__('uuid').uuid4()}",
        capabilities=capabilities
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400
    }


# Protected endpoints (require valid JWT)

@app.get("/api/v1/self")
async def get_self_info(request: Request):
    """Get information about authenticated agent."""
    from agents.security.authorization_middleware import get_auth_context
    
    auth = get_auth_context(request)
    
    return {
        "agent_name": auth.agent_name,
        "agent_id": auth.agent_id,
        "request_id": auth.request_id,
        "level": auth.get_capability_level()
    }


@app.get("/api/v1/data")
async def get_data(request: Request):
    """
    Get sensitive data (requires file_read capability).
    """
    from agents.security.capability_gate import CapabilityRequired
    
    auth_context = request.state
    print(f"Agent {auth_context.agent_name} reading data")
    
    return {"data": "sensitive information"}


@app.post("/api/v1/write-file")
@CapabilityRequired(capability='file_write')
async def write_file(path: str, content: str, request: Request):
    """
    Write file to disk (requires file_write capability).
    The @CapabilityRequired decorator enforces the requirement.
    """
    return {
        "status": "success",
        "path": path,
        "size": len(content),
        "agent": request.state.agent_name
    }


@app.post("/api/v1/generate")
@CapabilityRequired(capability='model_generate')
async def generate_content(prompt: str, request: Request):
    """
    Generate content with model (requires model_generate capability).
    """
    return {
        "prompt": prompt,
        "output": f"Generated content for: {prompt}",
        "agent": request.state.agent_name
    }


# Run app
if __name__ == "__main__":
    # Use: uvicorn agents.security.integration_guide:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ============================================================================
# 5. TESTING THE SECURITY SYSTEM
# ============================================================================

"""
TEST SCRIPT:

import requests
import json

BASE_URL = "http://localhost:8000"

# Step 1: Get token
print("1. Getting authentication token...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/token",
    params={"agent_name": "test-agent", "password": "test"}
)
token = response.json()["access_token"]
print(f"   Token: {token[:20]}...")

# Step 2: Use token to access protected endpoint
print("\\n2. Accessing protected endpoint...")
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/api/v1/self", headers=headers)
print(f"   Response: {json.dumps(response.json(), indent=2)}")

# Step 3: Call capability-gated endpoint
print("\\n3. Writing file (requires file_write)...")
response = requests.post(
    f"{BASE_URL}/api/v1/write-file",
    headers=headers,
    params={"path": "/tmp/test.txt", "content": "Hello"}
)
print(f"   Response: {json.dumps(response.json(), indent=2)}")

# Step 4: Test with expired token
print("\\n4. Testing with invalid token...")
bad_headers = {"Authorization": "Bearer invalid.token.here"}
response = requests.get(f"{BASE_URL}/api/v1/self", headers=bad_headers)
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
"""


# ============================================================================
# 6. CONFIGURATION REFERENCE
# ============================================================================

"""
ENVIRONMENT CONFIGURATION:

Create .env file with:

    # JWT Configuration
    JWT_SECRET_KEY=your-super-secret-key-here
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

Then load with:

    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    secret = os.getenv("JWT_SECRET_KEY")
    expiration = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
"""


# ============================================================================
# 7. BEST PRACTICES
# ============================================================================

"""
SECURITY BEST PRACTICES:

1. SECRET KEY MANAGEMENT
   ✓ Generate strong random secret key (>32 characters)
   ✓ Store in environment variables (never in code)
   ✓ Rotate periodically (create new keys, keep old for validation)
   ✓ Never commit .env files to git

2. CAPABILITY DESIGN
   ✓ Use principle of least privilege (minimal capabilities)
   ✓ Group related operations into single capability
   ✓ Document purpose of each capability
   ✓ Review capability grants regularly

3. TOKEN LIFECYCLE
   ✓ Keep expiration time short (1-24 hours)
   ✓ Implement token revocation for compromised tokens
   ✓ Auto-revoke on user/agent deactivation
   ✓ Provide token refresh mechanism

4. AUDIT LOGGING
   ✓ Log all authentication events
   ✓ Log all capability grants/denials
   ✓ Log sensitive operations
   ✓ Review audit logs regularly for suspicious activity

5. HTTPS/TLS
   ✓ Always use HTTPS in production (never HTTP)
   ✓ Use strong TLS certificates
   ✓ Keep certificates current
   ✓ Implement HSTS headers

6. RATE LIMITING
   ✓ Limit authentication attempts
   ✓ Rate limit per agent
   ✓ Block excessive failures (DoS protection)
   ✓ Allow legitimate traffic

7. ERROR HANDLING
   ✓ Never expose sensitive info in error messages
   ✓ Return generic error messages to clients
   ✓ Log detailed errors server-side
   ✓ Monitor for suspicious error patterns
"""


# ============================================================================
# 8. TROUBLESHOOTING
# ============================================================================

"""
COMMON ISSUES AND SOLUTIONS:

Issue: "Missing or invalid authorization header"
Solution:
  - Client must send: Authorization: Bearer <token>
  - Check token is valid (not corrupted)
  - Verify token not expired

Issue: "Token has expired"
Solution:
  - Get new token from /api/v1/auth/token
  - Implement token refresh mechanism
  - Increase expiration if too short (in production)

Issue: "Insufficient capabilities"
Solution:
  - Check token includes required capability
  - Verify capability name matches exactly
  - Ask admin to grant capability to agent
  - Check token was issued with right capabilities

Issue: "Internal server error: Request object not found"
Solution:
  - Ensure decorator is applied to async functions
  - Verify request parameter exists in function signature
  - Check middleware is installed (app.add_middleware)

Issue: "Audit logs not being created"
Solution:
  - Check log directory exists and is writable
  - Verify audit logger initialized (get_audit_logger())
  - Check file system permissions
  - Try with absolute path to log file

"""

print("=" * 70)
print("SECURITY SYSTEM INTEGRATION GUIDE")
print("=" * 70)
print("See documentation above for setup and usage instructions.")
print("\nKey Files:")
print("  - token_issuer.py: JWT generation and validation")
print("  - capability_gate.py: Capability-based access control")
print("  - authorization_middleware.py: HTTP middleware")
print("  - audit_logger.py: Security event logging")
print("=" * 70)
