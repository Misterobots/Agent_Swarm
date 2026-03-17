"""
Authorization Middleware
=========================

FastAPI middleware for enforcing authorization across all routes.
Validates JWT tokens, extracts agent identity, and enriches requests with
authorization context for downstream handlers.

Request Flow:
    1. Extract token from Authorization header
    2. Validate token signature and expiration
    3. Check agent exists and is authorized
    4. Attach agent card to request.state for use in handlers
    5. Log request with agent identity for audit trail
"""

import logging
import time
from typing import Optional, Any
from datetime import datetime
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import jwt

logger = logging.getLogger(__name__)


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for authorization enforcement.
    
    Validates all authenticated requests with JWT tokens and attaches
    agent card to request state for use in route handlers.
    """
    
    # Routes that bypass token validation
    PUBLIC_ROUTES = {
        '/docs',
        '/openapi.json',
        '/redoc',
        '/health',
        '/ready',
        '/metrics',
        '/api/v1/health',
    }
    
    # Routes that require authentication
    PROTECTED_ROUTES_PATTERN = '/api/'
    
    def __init__(self, app):
        super().__init__(app)
        self.validator = None
        self._request_counter = 0
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request through authorization pipeline.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler
            
        Returns:
            Response from handler or error response
        """
        start_time = time.time()
        request_id = self._get_request_id(request)
        
        # Check if route requires authentication
        if not self._should_authenticate(request.url.path):
            logger.debug(f"[{request_id}] Public route, skipping auth: {request.url.path}")
            response = await call_next(request)
            self._log_request(request, response.status_code, start_time, None, request_id)
            return response
        
        # Validate token for protected routes
        try:
            agent_card = await self._validate_request(request, request_id)
            
            # Attach to request state for use in handlers
            request.state.agent_card = agent_card
            request.state.agent_name = agent_card.agent_name
            request.state.agent_id = agent_card.agent_instance_id
            request.state.request_id = request_id
            
            logger.info(
                f"[{request_id}] Auth SUCCESS: Agent={agent_card.agent_name}, "
                f"Path={request.url.path}, Method={request.method}"
            )
            
            # Continue to handler
            response = await call_next(request)
            
            # Log successful request
            self._log_request(
                request,
                response.status_code,
                start_time,
                agent_card,
                request_id
            )
            
            return response
        
        except HTTPException as e:
            logger.warning(
                f"[{request_id}] Auth FAILED: {e.detail}, "
                f"Path={request.url.path}"
            )
            
            # Return error response
            self._log_request(
                request,
                e.status_code,
                start_time,
                None,
                request_id,
                error=e.detail
            )
            
            return Response(
                content=f'{{"detail": "{e.detail}", "request_id": "{request_id}"}}',
                status_code=e.status_code,
                media_type="application/json"
            )
        
        except Exception as e:
            logger.error(
                f"[{request_id}] Auth ERROR: {type(e).__name__}: {e}",
                exc_info=True
            )
            
            # Return 500 error
            self._log_request(
                request,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                start_time,
                None,
                request_id,
                error=str(e)
            )
            
            return Response(
                content=f'{{"detail": "Internal server error", "request_id": "{request_id}"}}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                media_type="application/json"
            )
    
    async def _validate_request(self, request: Request, request_id: str) -> Any:
        """
        Validate authorization header and token.
        
        Args:
            request: HTTP request
            request_id: Unique request identifier
            
        Returns:
            EphemeralAgentCard if valid
            
        Raises:
            HTTPException if validation fails
        """
        # Get validator (lazy initialize)
        if self.validator is None:
            from agents.security.token_issuer import get_token_validator
            self.validator = get_token_validator()
        
        # Extract token
        token = self._extract_token(request)
        if not token:
            logger.warning(f"[{request_id}] Missing authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate token
        try:
            agent_card = self.validator.validate_token(token)
            return agent_card
        
        except jwt.ExpiredSignatureError:
            logger.warning(f"[{request_id}] Token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"[{request_id}] Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed token"
            )
        
        except Exception as e:
            logger.error(f"[{request_id}] Token validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating authorization"
            )
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        return auth_header[7:]  # Remove "Bearer " prefix
    
    def _should_authenticate(self, path: str) -> bool:
        """Determine if route requires authentication."""
        # Public routes bypass authentication
        if path in self.PUBLIC_ROUTES:
            return False
        
        # Routes starting with /api/ require authentication
        if path.startswith(self.PROTECTED_ROUTES_PATTERN):
            return True
        
        # Everything else is protected
        return False
    
    def _get_request_id(self) -> str:
        """Generate unique request identifier."""
        self._request_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"req-{timestamp}-{self._request_counter:06d}"
    
    def _get_request_id(self, request: Request) -> str:
        """Get request ID from headers or generate new one."""
        # Check if client provided request ID
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            return request_id
        
        # Generate new one
        self._request_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"req-{timestamp}-{self._request_counter:06d}"
    
    def _log_request(
        self,
        request: Request,
        status_code: int,
        start_time: float,
        agent_card: Optional[Any],
        request_id: str,
        error: Optional[str] = None
    ):
        """Log HTTP request with authorization context."""
        duration_ms = (time.time() - start_time) * 1000
        
        agent_name = agent_card.agent_name if agent_card else "anonymous"
        agent_id = agent_card.agent_instance_id if agent_card else "unknown"
        
        log_level = "ERROR" if status_code >= 500 else "INFO"
        
        log_message = (
            f"[{request_id}] {request.method} {request.url.path} "
            f"Status={status_code} Duration={duration_ms:.1f}ms "
            f"Agent={agent_name} AgentID={agent_id}"
        )
        
        if error:
            log_message += f" Error={error}"
        
        if log_level == "ERROR":
            logger.error(log_message)
        else:
            logger.info(log_message)


# ============================================================================
# CONTEXT HELPERS
# ============================================================================

class AuthContext:
    """Helper class to access authorization context from request."""
    
    def __init__(self, request: Request):
        self.request = request
    
    @property
    def agent_card(self) -> Optional[Any]:
        """Get agent card from request state."""
        return getattr(self.request.state, 'agent_card', None)
    
    @property
    def agent_name(self) -> str:
        """Get agent name."""
        return getattr(self.request.state, 'agent_name', 'unknown')
    
    @property
    def agent_id(self) -> str:
        """Get agent instance ID."""
        return getattr(self.request.state, 'agent_id', 'unknown')
    
    @property
    def request_id(self) -> str:
        """Get request ID."""
        return getattr(self.request.state, 'request_id', 'unknown')
    
    def has_capability(self, capability: str) -> bool:
        """Check if agent has requested capability."""
        if not self.agent_card:
            return False
        
        capabilities = getattr(self.agent_card, 'activated_capabilities', [])
        return capability in (capabilities or [])
    
    def get_capability_level(self) -> str:
        """Get agent's capability level (admin, operator, observer)."""
        if not self.agent_card:
            return 'none'
        
        capabilities = getattr(self.agent_card, 'activated_capabilities', [])
        if not capabilities:
            return 'none'
        
        # Determine level based on capabilities
        if 'admin' in capabilities or 'system_admin' in capabilities:
            return 'admin'
        elif 'operator' in capabilities or len(capabilities) > 5:
            return 'operator'
        else:
            return 'observer'


def get_auth_context(request: Request) -> AuthContext:
    """
    Get auth context from request.
    
    Usage in route handler:
        @app.get("/api/v1/status")
        async def status(request: Request):
            auth = get_auth_context(request)
            return {"agent": auth.agent_name, "id": auth.agent_id}
    """
    return AuthContext(request)
