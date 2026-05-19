"""
Capability guard decorator for tool-level access control.

Checks that the calling agent's AgentCard has the required capability
before allowing tool execution.  Falls back to allow-all when the
registry or execution context is unavailable (graceful degradation).

Usage:
    @require_capability("file_ops.write")
    def write_file(path, content):
        ...
"""

import functools
import logging
from typing import Optional

logger = logging.getLogger("CapabilityGuard")

# Thread-local execution context — set by the router before dispatching
_current_agent_name: Optional[str] = None
_enforcement_enabled: bool = True


def set_current_agent(agent_name: str):
    """Set the agent name for the current execution context."""
    global _current_agent_name
    _current_agent_name = agent_name


def clear_current_agent():
    global _current_agent_name
    _current_agent_name = None


def set_enforcement(enabled: bool):
    global _enforcement_enabled
    _enforcement_enabled = enabled


def require_capability(capability: str):
    """
    Decorator that checks the current agent's capabilities before
    allowing the wrapped function to execute.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _enforcement_enabled:
                return func(*args, **kwargs)

            if _current_agent_name is None:
                # No execution context — allow (CLI / direct call)
                return func(*args, **kwargs)

            try:
                import sys as _sys
                import os as _os
                # Ensure agents dir is importable
                _agents_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "agents")
                if _agents_dir not in _sys.path:
                    _sys.path.insert(0, _agents_dir)
                from registry import registry
                card = registry.get_card(_current_agent_name)
                if card is None:
                    logger.warning(
                        f"[CapabilityGuard] Unknown agent '{_current_agent_name}' "
                        f"attempted tool '{func.__name__}' — ALLOWING (unregistered)"
                    )
                    return func(*args, **kwargs)

                # Check capability match (supports prefix matching: "file_ops" matches "file_ops.write")
                has_cap = any(
                    capability == c or capability.startswith(c + ".")
                    for c in card.capabilities
                )

                if not has_cap:
                    msg = (
                        f"[CapabilityGuard] BLOCKED: Agent '{_current_agent_name}' "
                        f"lacks capability '{capability}' for tool '{func.__name__}'. "
                        f"Has: {card.capabilities}"
                    )
                    logger.warning(msg)
                    return f"⛔ Access denied: {_current_agent_name} lacks '{capability}' capability."

            except ImportError:
                # Registry not available — degrade gracefully
                pass
            except Exception as e:
                logger.error(f"[CapabilityGuard] Check failed: {e} — allowing")

            return func(*args, **kwargs)
        return wrapper
    return decorator
