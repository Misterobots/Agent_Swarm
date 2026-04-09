import json
import os
import logging

# Define context directory within the agents directory
CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "context_sessions")
logger = logging.getLogger("ContextManager")


def _safe_component(value: str, fallback: str) -> str:
    """Return a filesystem-safe identifier."""
    safe_value = "".join(c for c in value if c.isalnum() or c in "-_")[:64]
    return safe_value or fallback


def _context_file(session_id: str = "default", owner_id: str | None = None) -> str:
    """Return the context file path for a given session and optional owner."""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    safe_id = _safe_component(session_id, "default")
    if owner_id:
        safe_owner = _safe_component(owner_id, "anonymous")
        owner_dir = os.path.join(CONTEXT_DIR, safe_owner)
        os.makedirs(owner_dir, exist_ok=True)
        return os.path.join(owner_dir, f"{safe_id}.json")
    return os.path.join(CONTEXT_DIR, f"{safe_id}.json")


def save_pending_context(data: dict, session_id: str = "default", owner_id: str | None = None):
    """Save generic context dictionary scoped to a session and optional owner."""
    try:
        path = _context_file(session_id, owner_id=owner_id)
        with open(path, 'w') as f:
            json.dump(data, f)
        logger.info(
            "Saved pending context for session %s owner=%s: %s",
            session_id,
            owner_id or "shared",
            data,
        )
    except Exception as e:
        logger.error(f"Failed to save context: {e}")

def save_pending_image_clarification(original_prompt: str, session_id: str = "default", owner_id: str | None = None):
    """Save the original prompt when Art Director asks for clarification."""
    save_pending_context({
        "type": "image_clarification",
        "prompt": original_prompt
    }, session_id=session_id, owner_id=owner_id)

def get_pending_context(session_id: str = "default", owner_id: str | None = None):
    """Retrieve pending context for a specific session and optional owner."""
    path = _context_file(session_id, owner_id=owner_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load context: {e}")
        return None

def clear_context(session_id: str = "default", owner_id: str | None = None):
    """Clear the context file for a specific session and optional owner."""
    path = _context_file(session_id, owner_id=owner_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.info("Context cleared for session %s owner=%s.", session_id, owner_id or "shared")
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")


# --- Migration: clean up old shared context file ---
_OLD_CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "swarm_context.json")
if os.path.exists(_OLD_CONTEXT_FILE):
    try:
        os.remove(_OLD_CONTEXT_FILE)
        logger.info("Removed stale shared swarm_context.json")
    except Exception:
        pass
