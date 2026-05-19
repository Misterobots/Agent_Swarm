# context_manager.py — backward-compatibility shim
# This module was renamed to brooks.py as part of the Pioneer naming scheme.
# This shim re-exports everything so any remaining references (cached .pyc,
# container volumes, or external imports) continue to work.
from brooks import (
    CONTEXT_DIR,
    save_pending_context,
    save_pending_image_clarification,
    get_pending_context,
    clear_context,
)

__all__ = [
    "CONTEXT_DIR",
    "save_pending_context",
    "save_pending_image_clarification",
    "get_pending_context",
    "clear_context",
]
