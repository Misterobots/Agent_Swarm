import json
import os
import logging

# Define context file within the agents directory
CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "swarm_context.json")
logger = logging.getLogger("ContextManager")

def save_pending_context(data: dict):
    """Saves generic context dictionary."""
    try:
        data["timestamp"] = os.path.getmtime(CONTEXT_FILE) if os.path.exists(CONTEXT_FILE) else 0
        with open(CONTEXT_FILE, 'w') as f:
            json.dump(data, f)
        logger.info(f"Saved pending context: {data}")
    except Exception as e:
        logger.error(f"Failed to save context: {e}")

def save_pending_image_clarification(original_prompt: str):
    """Saves the original prompt when Art Director asks for clarification."""
    save_pending_context({
        "type": "image_clarification",
        "prompt": original_prompt
    })

def get_pending_context():
    """Retrieves pending context if it exists."""
    if not os.path.exists(CONTEXT_FILE):
        return None
        
    try:
        with open(CONTEXT_FILE, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load context: {e}")
        return None

def clear_context():
    """Clears the context file after successful execution."""
    if os.path.exists(CONTEXT_FILE):
        try:
            os.remove(CONTEXT_FILE)
            logger.info("Context cleared.")
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")
