# SPIFFE/SPIRE Security Module
"""
Zero-trust security for agent-to-agent communication.
"""

from .spiffe_auth import (
    SpiffeAuth,
    get_spiffe_auth,
    get_auth_headers,
    verify_request_identity,
    SPIFFE_AVAILABLE,
)

try:
    from .middleware import (
        SpiffeJWTBearer,
        SpiffeAuthMiddleware,
        require_spiffe_id,
    )
except ImportError:
    SpiffeJWTBearer = None
    SpiffeAuthMiddleware = None
    require_spiffe_id = None

__all__ = [
    # Auth functions
    "SpiffeAuth",
    "get_spiffe_auth", 
    "get_auth_headers",
    "verify_request_identity",
    "SPIFFE_AVAILABLE",
    # Middleware
    "SpiffeJWTBearer",
    "SpiffeAuthMiddleware",
    "require_spiffe_id",
]

