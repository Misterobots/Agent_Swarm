"""
interceptors.py — Auth + logging interceptors for OpenClaude gRPC server.

Validates Authentik OAuth2 tokens passed in gRPC metadata.
Pure Python logic — gRPC interceptor wiring is optional.

Auth flow:
    1. Client sends OAuth2 bearer token in 'authorization' metadata
    2. Interceptor extracts token and calls Authentik userinfo endpoint
    3. On success, request proceeds; on failure, UNAUTHENTICATED error returned
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests as _requests  # Module-level import for mockability

logger = logging.getLogger(__name__)

# Authentik configuration
AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://192.168.2.103:9000")
AUTHENTIK_USERINFO = os.getenv("AUTHENTIK_USERINFO_URL", f"{AUTHENTIK_URL}/application/o/userinfo/")
AUTH_ENABLED = os.getenv("GRPC_AUTH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
AUTH_CACHE_TTL = int(os.getenv("GRPC_AUTH_CACHE_TTL", "300"))  # 5 minutes

# Paths that skip auth (health checks, model listing)
AUTH_EXEMPT_METHODS = frozenset({
    "/openclaude.v1.InferenceService/HealthCheck",
    "/openclaude.v1.InferenceService/ListModels",
})


@dataclass
class AuthResult:
    """Result of token validation."""
    authenticated: bool
    user_id: str = ""
    username: str = ""
    email: str = ""
    groups: list = None
    error: str = ""

    def __post_init__(self):
        if self.groups is None:
            self.groups = []

    def to_dict(self) -> dict:
        return {
            "authenticated": self.authenticated,
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "groups": self.groups,
            "error": self.error,
        }


class TokenValidator:
    """
    Validates OAuth2 bearer tokens against Authentik's userinfo endpoint.
    Caches successful validations with TTL.
    """

    def __init__(
        self,
        userinfo_url: str = AUTHENTIK_USERINFO,
        cache_ttl: int = AUTH_CACHE_TTL,
        enabled: bool = AUTH_ENABLED,
    ):
        self._userinfo_url = userinfo_url
        self._cache_ttl = cache_ttl
        self._enabled = enabled
        self._cache: dict = {}  # token_hash -> (AuthResult, timestamp)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def validate(self, token: str) -> AuthResult:
        """Validate an OAuth2 bearer token."""
        if not self._enabled:
            return AuthResult(authenticated=True, user_id="auth-disabled", username="anonymous")

        if not token:
            return AuthResult(authenticated=False, error="No token provided")

        # Check cache
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        cached = self._cache.get(token_hash)
        if cached:
            result, ts = cached
            if time.time() - ts < self._cache_ttl:
                return result

        # Call Authentik userinfo
        try:
            resp = _requests.get(
                self._userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = AuthResult(
                    authenticated=True,
                    user_id=data.get("sub", ""),
                    username=data.get("preferred_username", data.get("name", "")),
                    email=data.get("email", ""),
                    groups=data.get("groups", []),
                )
                self._cache[token_hash] = (result, time.time())
                return result
            else:
                return AuthResult(authenticated=False, error=f"Authentik returned {resp.status_code}")
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return AuthResult(authenticated=False, error=str(e))

    def invalidate(self, token: str):
        """Remove a token from cache."""
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        self._cache.pop(token_hash, None)

    def clear_cache(self):
        """Clear all cached validations."""
        self._cache.clear()


class RequestLogger:
    """Logs gRPC request metadata for audit trail."""

    def __init__(self):
        self._audit_logger = logging.getLogger("grpc.audit")

    def log_request(self, method: str, auth_result: Optional[AuthResult] = None,
                    duration_ms: float = 0.0, error: str = ""):
        """Log a gRPC request."""
        user = auth_result.username if auth_result and auth_result.authenticated else "anonymous"
        status = "OK" if not error else "ERROR"
        self._audit_logger.info(
            f"gRPC {method} | user={user} | status={status} | "
            f"duration={duration_ms:.1f}ms | error={error}"
        )


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
_validator_instance: Optional[TokenValidator] = None
_logger_instance: Optional[RequestLogger] = None


def get_token_validator() -> TokenValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = TokenValidator()
    return _validator_instance


def get_request_logger() -> RequestLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = RequestLogger()
    return _logger_instance


def get_auth_interceptor():
    """
    Returns a gRPC server interceptor for auth validation.
    Returns None if grpc is not available.
    """
    try:
        import grpc

        class AuthInterceptor(grpc.ServerInterceptor):
            """gRPC server interceptor that validates OAuth2 tokens."""

            def __init__(self):
                self._validator = get_token_validator()
                self._req_logger = get_request_logger()

            def intercept_service(self, continuation, handler_call_details):
                method = handler_call_details.method
                # Skip auth for exempt methods
                if method in AUTH_EXEMPT_METHODS:
                    return continuation(handler_call_details)

                if not self._validator.enabled:
                    return continuation(handler_call_details)

                # Extract token from metadata
                metadata = dict(handler_call_details.invocation_metadata or [])
                auth_header = metadata.get("authorization", "")

                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                else:
                    token = auth_header

                result = self._validator.validate(token)
                if not result.authenticated:
                    self._req_logger.log_request(method, result, error=result.error)
                    # Return None to reject the request
                    return None

                self._req_logger.log_request(method, result)
                return continuation(handler_call_details)

        return AuthInterceptor()
    except ImportError:
        return None
