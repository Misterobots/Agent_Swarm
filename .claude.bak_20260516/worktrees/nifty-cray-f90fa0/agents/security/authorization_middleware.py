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
import os
from typing import Optional, Any
from datetime import datetime, timezone
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

    ENDPOINT_CLASS_PUBLIC = "public"
    ENDPOINT_CLASS_USER = "user"
    ENDPOINT_CLASS_ADMIN = "admin"
    ENDPOINT_CLASS_INTERNAL = "internal"
    ENDPOINT_CLASS_API_KEY = "api_key"

    TOKEN_PROFILE_UNKNOWN = "unknown"
    TOKEN_PROFILE_USER = "user"
    TOKEN_PROFILE_WORKLOAD = "workload"
    
    def __init__(self, app, enforcement_mode: Optional[str] = None):
        super().__init__(app)
        self.validator = None
        self._request_counter = 0
        mode = (enforcement_mode or os.getenv("AUTH_ENFORCEMENT_MODE", "parse")).strip().lower()
        self.enforcement_mode = mode if mode in {"parse", "soft", "hard"} else "parse"
        logger.info("AuthorizationMiddleware initialized in %s mode", self.enforcement_mode)
    
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
        
        endpoint_class = self._classify_endpoint(request.url.path, request.method)
        request.state.endpoint_class = endpoint_class
        request.state.request_id = request_id

        # Check if route requires bearer authentication
        if not self._requires_bearer_auth(endpoint_class):
            logger.debug(
                f"[{request_id}] Endpoint class {endpoint_class}, skipping bearer auth: {request.url.path}"
            )
            response = await call_next(request)
            self._log_request(request, response.status_code, start_time, None, request_id, endpoint_class)
            return response

        token = self._extract_token(request)

        # Parse-only mode logs missing tokens but does not block.
        if self.enforcement_mode == "parse" and not token:
            logger.warning(
                f"[{request_id}] Parse-only auth bypass: missing bearer token for "
                f"endpoint_class={endpoint_class}, path={request.url.path}"
            )
            response = await call_next(request)
            self._log_request(request, response.status_code, start_time, None, request_id, endpoint_class)
            return response

        token_profile = self._classify_token_profile(token) if token else self.TOKEN_PROFILE_UNKNOWN
        request.state.token_profile = token_profile

        if token and self._is_profile_mismatch(endpoint_class, token_profile):
            detail = "Token profile not allowed for endpoint class"
            if self.enforcement_mode == "parse":
                logger.warning(
                    f"[{request_id}] Parse-only token profile mismatch: "
                    f"endpoint_class={endpoint_class}, token_profile={token_profile}, path={request.url.path}"
                )
            else:
                logger.warning(
                    f"[{request_id}] Policy deny: endpoint_class={endpoint_class}, "
                    f"token_profile={token_profile}, path={request.url.path}"
                )
                self._log_request(
                    request,
                    status.HTTP_401_UNAUTHORIZED,
                    start_time,
                    None,
                    request_id,
                    endpoint_class,
                    error=detail,
                )
                return Response(
                    content=(
                        f'{{"detail": "{detail}", '
                        f'"request_id": "{request_id}"}}'
                    ),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json"
                )
        
        # Validate token for protected routes
        try:
            agent_card = await self._validate_request(request, request_id, endpoint_class)

            # Enforce endpoint-class policy in soft/hard mode.
            if self.enforcement_mode in {"soft", "hard"}:
                self._enforce_endpoint_policy(endpoint_class, agent_card, request_id, request.url.path)
            
            # Attach to request state for use in handlers
            request.state.agent_card = agent_card
            request.state.agent_name = agent_card.agent_name
            request.state.agent_id = agent_card.agent_instance_id
            request.state.owner_id = self._resolve_owner_id(agent_card, token_profile)
            request.state.request_id = request_id
            
            logger.info(
                f"[{request_id}] Auth SUCCESS: Agent={agent_card.agent_name}, "
                f"Path={request.url.path}, Method={request.method}, Class={endpoint_class}, "
                f"Owner={getattr(request.state, 'owner_id', None)}"
            )
            
            # Continue to handler
            response = await call_next(request)
            
            # Log successful request
            self._log_request(
                request,
                response.status_code,
                start_time,
                agent_card,
                request_id,
                endpoint_class
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
                endpoint_class,
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
                endpoint_class,
                error=str(e)
            )
            
            return Response(
                content=f'{{"detail": "Internal server error", "request_id": "{request_id}"}}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                media_type="application/json"
            )
    
    async def _validate_request(self, request: Request, request_id: str, endpoint_class: str) -> Any:
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
            try:
                from agents.security.token_issuer import get_token_validator
            except ImportError:
                from security.token_issuer import get_token_validator
            self.validator = get_token_validator()
        
        # Extract token
        token = self._extract_token(request)
        if not token:
            logger.warning(f"[{request_id}] Missing authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing or invalid authorization header "
                    f"(endpoint_class={endpoint_class})"
                ),
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate token
        try:
            if endpoint_class in {self.ENDPOINT_CLASS_USER, self.ENDPOINT_CLASS_ADMIN}:
                agent_card = self.validator.validate_user_token(token)
            elif endpoint_class == self.ENDPOINT_CLASS_INTERNAL:
                agent_card = self.validator.validate_workload_token(token)
            else:
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
                detail=f"Invalid or malformed token (endpoint_class={endpoint_class})"
            )
        
        except Exception as e:
            logger.error(f"[{request_id}] Token validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error validating authorization (endpoint_class={endpoint_class})"
            )
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        return auth_header[7:]  # Remove "Bearer " prefix

    def _classify_token_profile(self, token: str) -> str:
        """Classify a bearer token by unverified header/claims for route-policy enforcement."""
        try:
            header = jwt.get_unverified_header(token)
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
                algorithms=["HS256", "RS256", "ES256", "ES384", "ES512"],
            )
        except Exception as exc:
            logger.warning("Unable to classify token profile from unverified claims: %s", exc)
            return self.TOKEN_PROFILE_UNKNOWN

        issuer = str(claims.get("iss", ""))
        subject = str(claims.get("sub", ""))
        spiffe_id = str(claims.get("spiffe_id", ""))
        algorithm = str(header.get("alg", "")).upper()

        if issuer == "home-ai-lab-token-issuer":
            return self.TOKEN_PROFILE_USER

        if subject.startswith("spiffe://") or spiffe_id.startswith("spiffe://"):
            return self.TOKEN_PROFILE_WORKLOAD

        if issuer.startswith("spiffe://") or "spire" in issuer.lower() or "spiffe" in issuer.lower():
            return self.TOKEN_PROFILE_WORKLOAD

        if algorithm in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}:
            return self.TOKEN_PROFILE_WORKLOAD

        if algorithm == "HS256":
            return self.TOKEN_PROFILE_USER

        return self.TOKEN_PROFILE_UNKNOWN

    def _is_profile_mismatch(self, endpoint_class: str, token_profile: str) -> bool:
        """Determine whether a token profile is explicitly incompatible with an endpoint class."""
        if token_profile == self.TOKEN_PROFILE_UNKNOWN:
            return False

        if endpoint_class in {self.ENDPOINT_CLASS_USER, self.ENDPOINT_CLASS_ADMIN}:
            return token_profile != self.TOKEN_PROFILE_USER

        if endpoint_class == self.ENDPOINT_CLASS_INTERNAL:
            return token_profile != self.TOKEN_PROFILE_WORKLOAD

        return False
    
    def _classify_endpoint(self, path: str, method: str) -> str:
        """Classify endpoint into policy class for token/profile enforcement."""
        if path in self.PUBLIC_ROUTES:
            return self.ENDPOINT_CLASS_PUBLIC

        if path == "/" or path == "/v1/models" or path == "/log":
            return self.ENDPOINT_CLASS_PUBLIC

        if path.startswith("/voice_samples/"):
            return self.ENDPOINT_CLASS_PUBLIC

        if method.upper() == "POST" and path == "/api/v1/request":
            return self.ENDPOINT_CLASS_API_KEY

        if method.upper() == "POST" and path.startswith("/api/v1/request/") and path.endswith("/status"):
            return self.ENDPOINT_CLASS_ADMIN

        # Identity endpoint is a "who am I?" self-inspection endpoint; public so the
        # UI can call it without a bearer token (returns "anonymous" in that case).
        if path == "/api/v1/identity":
            return self.ENDPOINT_CLASS_PUBLIC

        # MCP bridge is user-facing (CLI clients) and should accept user JWT tokens.
        if path.startswith("/api/v1/mcp/"):
            return self.ENDPOINT_CLASS_USER

        if path.startswith("/api/v1/"):
            return self.ENDPOINT_CLASS_INTERNAL

        if path.startswith("/v1/"):
            return self.ENDPOINT_CLASS_USER

        # Fallback: treat unknown endpoints as public until they are explicitly classified.
        return self.ENDPOINT_CLASS_PUBLIC

    def _requires_bearer_auth(self, endpoint_class: str) -> bool:
        """Return True when endpoint class requires bearer-token authorization."""
        return endpoint_class in {
            self.ENDPOINT_CLASS_USER,
            self.ENDPOINT_CLASS_ADMIN,
            self.ENDPOINT_CLASS_INTERNAL,
        }

    def _enforce_endpoint_policy(self, endpoint_class: str, agent_card: Any, request_id: str, path: str) -> None:
        """Enforce endpoint-class policy after token validation."""
        capabilities = set(getattr(agent_card, "activated_capabilities", []) or [])
        security_level = getattr(agent_card, "security_level", "")

        if endpoint_class == self.ENDPOINT_CLASS_ADMIN:
            if "admin" not in capabilities and "system_admin" not in capabilities:
                logger.warning(
                    f"[{request_id}] Policy deny: missing admin capability for {path}. "
                    f"Capabilities={sorted(capabilities)}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role/scope for admin endpoint"
                )

        if endpoint_class == self.ENDPOINT_CLASS_INTERNAL and self.enforcement_mode == "hard":
            if security_level not in {"L3_ADMIN", "L4_SYSTEM"}:
                logger.warning(
                    f"[{request_id}] Policy deny: insufficient security_level for internal endpoint {path}. "
                    f"security_level={security_level}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient security level for internal endpoint"
                )

    def _resolve_owner_id(self, agent_card: Any, token_profile: str) -> Optional[str]:
        """Resolve owner identity from validated agent card in priority order."""
        explicit_owner = getattr(agent_card, "user_id", None)
        if explicit_owner:
            return explicit_owner

        metadata = getattr(agent_card, "metadata", {}) or {}
        metadata_owner = metadata.get("user_id") or metadata.get("owner_id")
        if metadata_owner:
            return metadata_owner

        if token_profile == self.TOKEN_PROFILE_USER:
            fallback_session = getattr(agent_card, "session_id", None)
            if fallback_session:
                return f"session:{fallback_session}"

        return None
    
    def _get_request_id(self, request: Request) -> str:
        """Get request ID from headers or generate new one."""
        # Check if client provided request ID
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            return request_id
        
        # Generate new one
        self._request_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"req-{timestamp}-{self._request_counter:06d}"
    
    def _log_request(
        self,
        request: Request,
        status_code: int,
        start_time: float,
        agent_card: Optional[Any],
        request_id: str,
        endpoint_class: str,
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
            f"Class={endpoint_class} Agent={agent_name} AgentID={agent_id}"
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
