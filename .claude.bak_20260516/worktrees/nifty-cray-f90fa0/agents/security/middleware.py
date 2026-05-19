"""
FastAPI Security Middleware for SPIFFE JWT Verification

This middleware intercepts incoming requests and verifies the
SPIFFE JWT-SVID in the Authorization header.
"""

import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .spiffe_auth import get_spiffe_auth, SPIFFE_AVAILABLE

logger = logging.getLogger(__name__)


class SpiffeJWTBearer(HTTPBearer):
    """
    FastAPI security scheme for SPIFFE JWT-SVID authentication.
    
    Usage:
        from security.middleware import SpiffeJWTBearer
        
        spiffe_auth = SpiffeJWTBearer()
        
        @app.get("/protected")
        async def protected_endpoint(credentials: dict = Depends(spiffe_auth)):
            caller_id = credentials["spiffe_id"]
            return {"message": f"Hello {caller_id}"}
    """
    
    def __init__(
        self,
        auto_error: bool = True,
        required_spiffe_ids: Optional[list[str]] = None
    ):
        """
        Initialize SPIFFE JWT authentication.
        
        Args:
            auto_error: If True, raise HTTPException on auth failure
            required_spiffe_ids: Optional list of allowed SPIFFE IDs
        """
        super().__init__(auto_error=auto_error)
        self.required_spiffe_ids = required_spiffe_ids
    
    async def __call__(self, request: Request) -> Optional[dict]:
        """Verify JWT and return claims."""
        if not SPIFFE_AVAILABLE:
            logger.warning("SPIFFE not available, skipping auth")
            return {"spiffe_id": "unknown", "authenticated": False}
        
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            if self.auto_error:
                raise HTTPException(status_code=401, detail="Not authenticated")
            return None
        
        if credentials.scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            return None
        
        # Verify the JWT
        auth = get_spiffe_auth()
        our_id = auth.get_spiffe_id()
        
        if not our_id:
            logger.error("Cannot verify JWT: own SPIFFE ID not available")
            if self.auto_error:
                raise HTTPException(status_code=500, detail="Identity service unavailable")
            return None
        
        claims = auth.verify_jwt_token(credentials.credentials, our_id)
        
        if not claims:
            if self.auto_error:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return None
        
        # Check allowed SPIFFE IDs
        caller_id = claims.get("spiffe_id")
        if self.required_spiffe_ids and caller_id not in self.required_spiffe_ids:
            logger.warning(f"Unauthorized caller: {caller_id}")
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Caller not authorized")
            return None
        
        claims["authenticated"] = True
        return claims


class SpiffeAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds SPIFFE identity info to request state.
    
    Does not block requests, just enriches them with identity info.
    Use SpiffeJWTBearer for strict authentication.
    
    Usage:
        app.add_middleware(SpiffeAuthMiddleware)
        
        @app.get("/info")
        async def get_info(request: Request):
            caller = request.state.spiffe_caller  # May be None
            return {"caller": caller}
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Initialize with no caller
        request.state.spiffe_caller = None
        request.state.spiffe_authenticated = False
        
        if not SPIFFE_AVAILABLE:
            return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)
        
        token = auth_header.split(" ", 1)[1]
        
        # Try to verify
        auth = get_spiffe_auth()
        our_id = auth.get_spiffe_id()
        
        if our_id:
            claims = auth.verify_jwt_token(token, our_id)
            if claims:
                request.state.spiffe_caller = claims.get("spiffe_id")
                request.state.spiffe_authenticated = True
                logger.debug(f"Authenticated caller: {request.state.spiffe_caller}")
        
        return await call_next(request)


def require_spiffe_id(*allowed_ids: str):
    """
    Dependency that requires specific SPIFFE IDs.
    
    Usage:
        @app.post("/internal")
        async def internal_only(
            _: None = Depends(require_spiffe_id(
                "spiffe://home-ai-lab/agent/runtime",
                "spiffe://home-ai-lab/agent/router"
            ))
        ):
            return {"status": "ok"}
    """
    bearer = SpiffeJWTBearer(required_spiffe_ids=list(allowed_ids))
    return bearer
