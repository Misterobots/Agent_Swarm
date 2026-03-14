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

from .middleware import (
    SpiffeJWTBearer,
    SpiffeAuthMiddleware,
    require_spiffe_id,
)

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

