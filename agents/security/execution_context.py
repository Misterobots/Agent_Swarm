"""
Execution Context — Thread-Local JWT Token Storage
=====================================================

Allows the router to set the current JWT token before agent execution,
and tools to read it for capability validation without requiring
explicit token passing through every function call.

Usage:
    # In router (before agent execution):
    set_current_token(jwt_token)

    # In tool functions:
    token = get_current_token()
    if token:
        validator = CapabilityValidator()
        if not validator.check_capability(token, "file_write"):
            raise PermissionError("Missing file_write capability")

    # In router (after agent execution):
    clear_current_token()
"""

import threading
from typing import Optional

_context = threading.local()


def set_current_token(token: str) -> None:
    """Set the JWT token for the current thread's execution context."""
    _context.token = token


def get_current_token() -> Optional[str]:
    """Get the JWT token from the current thread's execution context."""
    return getattr(_context, "token", None)


def clear_current_token() -> None:
    """Clear the JWT token from the current thread's execution context."""
    _context.token = None
