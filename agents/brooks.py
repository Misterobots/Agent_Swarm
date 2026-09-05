import json
import os
import time
import logging

_CONTEXT_TTL_SECONDS = 1800  # 30 minutes — stale contexts corrupt fresh sessions

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
        payload = {**data, "_saved_at": time.time()}
        with open(path, 'w') as f:
            json.dump(payload, f)
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
    """Retrieve pending context for a specific session and optional owner.

    Returns None (and removes the file) if the context is older than _CONTEXT_TTL_SECONDS.
    """
    path = _context_file(session_id, owner_id=owner_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        saved_at = data.pop("_saved_at", None)
        if saved_at is None or (time.time() - saved_at) > _CONTEXT_TTL_SECONDS:
            logger.warning(
                "Pending context for session %s expired (%.0fs old) — discarding.",
                session_id,
                time.time() - saved_at,
            )
            try:
                os.remove(path)
            except OSError:
                pass
            return None

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


# ---------------------------------------------------------------------------
# Session-scoped workshop state
# Persists Phase 1 output by owner and session.  A different tab must not be
# interpreted as a Workshop continuation merely because it shares an owner.
# TTL is 24 h — long enough for an async workshop, shorter than session context.
# ---------------------------------------------------------------------------

_WORKSHOP_TTL_SECONDS = 86_400  # 24 hours


def _workshop_file(owner_id: str, session_id: str | None = None) -> str:
    safe_owner = _safe_component(owner_id, "anonymous")
    owner_dir = os.path.join(CONTEXT_DIR, safe_owner)
    os.makedirs(owner_dir, exist_ok=True)
    safe_session = _safe_component(session_id or "legacy", "legacy")
    return os.path.join(owner_dir, f"workshop_pending_{safe_session}.json")


def save_workshop_state(phase1_output: str, original_idea: str, owner_id: str, session_id: str | None = None) -> None:
    """Persist Phase 1 workshop output for its owning conversation."""
    try:
        path = _workshop_file(owner_id, session_id)
        with open(path, "w") as fh:
            json.dump(
                {
                    "type": "workshop_phase1",
                    "output": phase1_output,
                    "idea": original_idea,
                    "_saved_at": time.time(),
                },
                fh,
            )
        logger.info("[Brooks] Workshop Phase 1 saved for owner=%s session=%s", owner_id, session_id)
    except Exception as exc:
        logger.error("[Brooks] Failed to save workshop state: %s", exc)


def get_workshop_state(owner_id: str, session_id: str | None = None) -> dict | None:
    """Retrieve a pending workshop only for its owning conversation."""
    try:
        path = _workshop_file(owner_id, session_id)
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            data = json.load(fh)
        saved_at = data.pop("_saved_at", None)
        if saved_at is None or (time.time() - saved_at) > _WORKSHOP_TTL_SECONDS:
            logger.info("[Brooks] Workshop state for owner=%s expired — discarding", owner_id)
            os.remove(path)
            return None
        return data
    except Exception as exc:
        logger.error("[Brooks] Failed to load workshop state: %s", exc)
        return None


def clear_workshop_state(owner_id: str, session_id: str | None = None) -> None:
    """Delete this session's pending workshop state after Phase 2 completes."""
    try:
        path = _workshop_file(owner_id, session_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info("[Brooks] Workshop state cleared for owner=%s", owner_id)
    except Exception as exc:
        logger.error("[Brooks] Failed to clear workshop state: %s", exc)


# --- Migration: clean up old shared context file ---
_OLD_CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "swarm_context.json")
if os.path.exists(_OLD_CONTEXT_FILE):
    try:
        os.remove(_OLD_CONTEXT_FILE)
        logger.info("Removed stale shared swarm_context.json")
    except Exception:
        pass
