import json
import os
import logging

# Define context directory within the agents directory
CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "context_sessions")
logger = logging.getLogger("ContextManager")


def _context_file(session_id: str = "default") -> str:
    """Return the context file path for a given session."""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    # Sanitize session_id for filesystem safety
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64]
    return os.path.join(CONTEXT_DIR, f"{safe_id}.json")


def save_pending_context(data: dict, session_id: str = "default"):
    """Saves generic context dictionary scoped to a session."""
    try:
        path = _context_file(session_id)
        with open(path, 'w') as f:
            json.dump(data, f)
        logger.info(f"Saved pending context for session {session_id}: {data}")
    except Exception as e:
        logger.error(f"Failed to save context: {e}")

def save_pending_image_clarification(original_prompt: str, session_id: str = "default"):
    """Saves the original prompt when Art Director asks for clarification."""
    save_pending_context({
        "type": "image_clarification",
        "prompt": original_prompt
    }, session_id=session_id)

def get_pending_context(session_id: str = "default"):
    """Retrieves pending context for a specific session."""
    path = _context_file(session_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load context: {e}")
        return None

def clear_context(session_id: str = "default"):
    """Clears the context file for a specific session."""
    path = _context_file(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Context cleared for session {session_id}.")
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
