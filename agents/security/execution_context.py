"""
Execution Context — Thread-Local JWT Token Storage
=====================================================

Allows the router to set the current JWT token before agent execution,
and tools to read it for capability validation without requiring
explicit token passing through every function call.

Also supports *active scope* — the per-intent subset of capabilities that
are currently allowed.  The card carries the broad identity; the scope
narrows what is actually permitted for a given routing decision.

Usage:
    # In router (before agent execution):
    set_current_token(jwt_token)
    set_active_scope(["file_read", "model_generate"])

    # In tool functions:
    token = get_current_token()
    scope = get_active_scope()
    if token:
        validator = CapabilityValidator()
        if not validator.check_capability(token, "file_write"):
            raise PermissionError("Missing file_write capability")
        if scope and "file_write" not in scope:
            raise PermissionError("file_write not in active scope")

    # In router (after agent execution):
    clear_active_scope()
    clear_current_token()
"""

import threading
from typing import Optional, List

_context = threading.local()


# ---- Token ----

def set_current_token(token: str) -> None:
    """Set the JWT token for the current thread's execution context."""
    _context.token = token


def get_current_token() -> Optional[str]:
    """Get the JWT token from the current thread's execution context."""
    return getattr(_context, "token", None)


def clear_current_token() -> None:
    """Clear the JWT token from the current thread's execution context."""
    _context.token = None


# ---- Active scope ----

def set_active_scope(capabilities: List[str]) -> None:
    """Set the per-intent capability scope for the current thread."""
    _context.active_scope = list(capabilities)


def get_active_scope() -> Optional[List[str]]:
    """Get the active capability scope (None means no scope restriction)."""
    return getattr(_context, "active_scope", None)


def clear_active_scope() -> None:
    """Clear the active scope for the current thread."""
    _context.active_scope = None
