"""
Control Plane Security Service
==============================

FastAPI service for centralized JWT token issuance and validation.
Runs on Control Plane and serves all execution planes.

Endpoints:
- POST /api/security/v1/token - Issue token
- POST /api/security/v1/validate - Validate token
- POST /api/security/v1/revoke - Revoke token
- GET /health - Health check
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging
import os
from typing import Optional
import uuid

try:
    # Package-style import (e.g., python -m)
    from .token_issuer import initialize_token_issuer, get_token_issuer
except ImportError:
    # Script-style import used by container command: uvicorn main:app
    from token_issuer import initialize_token_issuer, get_token_issuer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app
app = FastAPI(
    title="Control Plane Security Service",
    description="Centralized JWT token issuer for Home AI Lab",
    version="1.0"
)


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize security system."""
    logger.info("Control Plane Security Service starting...")

    jwt_secret_key = os.getenv('JWT_SECRET_KEY')
    if not jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY must be set")
    
    config = {
        'secret_key': jwt_secret_key,
        'algorithm': os.getenv('JWT_ALGORITHM', 'HS256'),
        'expiration_hours': int(os.getenv('JWT_EXPIRATION_HOURS', 24)),
        'db_url': os.getenv('DATABASE_URL', 'postgresql://langfuse:langfuse_password@postgres:5432/langfuse'),
        'langfuse_client': None,  # Would be initialized here
    }
    
    try:
        initialize_token_issuer(config)
        logger.info("Token issuer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize token issuer: {e}")
        raise


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "control-plane-security",
        "version": "1.0"
    }


# ============================================================================
# TOKEN ENDPOINTS
# ============================================================================

@app.post("/api/security/v1/token")
async def issue_token(
    agent_name: str,
    capabilities: list,
    agent_instance_id: Optional[str] = None,
    spire_svid: Optional[str] = None
):
    """
    Issue JWT token for agent.
    
    Args:
        agent_name: Name of agent
        capabilities: List of capabilities to grant
        agent_instance_id: Optional instance ID (auto-generated if not provided)
        spire_svid: Optional SPIRE SVID for identity validation
        
    Returns:
        JWT token
    """
    try:
        if not agent_instance_id:
            agent_instance_id = f"{agent_name}-{uuid.uuid4()}"
        
        issuer = get_token_issuer()
        token = issuer.issue_token(
            agent_name=agent_name,
            agent_instance_id=agent_instance_id,
            capabilities=capabilities,
            spire_svid=spire_svid
        )
        
        logger.info(f"Token issued for {agent_name}")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "agent_instance_id": agent_instance_id,
            "expires_in": issuer.expiration_hours * 3600
        }
    
    except Exception as e:
        logger.error(f"Failed to issue token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/security/v1/validate")
async def validate_token(token: str):
    """
    Validate JWT token.
    
    Args:
        token: JWT token to validate
        
    Returns:
        Token payload if valid
    """
    try:
        issuer = get_token_issuer()
        payload = issuer.validate_token(token)
        
        return {
            "valid": True,
            "agent_name": payload.get('agent_name'),
            "agent_instance_id": payload.get('agent_instance_id'),
            "capabilities": payload.get('activated_capabilities', []),
            "expires_at": payload.get('exp')
        }
    
    except Exception as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


@app.post("/api/security/v1/revoke")
async def revoke_token(token: str, reason: str = "revoked"):
    """
    Revoke a token.
    
    Args:
        token: JWT token to revoke
        reason: Reason for revocation
        
    Returns:
        Success response
    """
    try:
        import jwt as pyjwt
        
        # Decode without verification to get JTI
        payload = pyjwt.decode(token, options={"verify_signature": False})
        jti = payload.get('jti')
        
        if not jti:
            raise ValueError("Token missing JTI")
        
        issuer = get_token_issuer()
        issuer.revoke_token(jti, reason)
        
        logger.info(f"Token revoked: {jti}")
        
        return {
            "status": "revoked",
            "jti": jti,
            "reason": reason
        }
    
    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# MIDDLEWARE - Request Logging
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"  -> {response.status_code}")
    return response


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# ============================================================================
# Root
# ============================================================================

@app.get("/")
async def root():
    """API root."""
    return {
        "service": "Control Plane Security Service",
        "version": "1.0",
        "endpoints": {
            "health": "GET /health",
            "token": "POST /api/security/v1/token",
            "validate": "POST /api/security/v1/validate",
            "revoke": "POST /api/security/v1/revoke"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
