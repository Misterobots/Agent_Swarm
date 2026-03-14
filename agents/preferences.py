"""
User Preferences Module
=======================
Handles structured preference storage and Human-in-the-Loop confirmation.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from config import AGNO_DB_URL

# =============================================================================
# PREFERENCE STORAGE
# =============================================================================

@dataclass
class UserPreference:
    """A single user preference."""
    key: str
    value: Any
    task_type: str  # e.g., "image_generation", "code_generation"
    confidence: float = 1.0  # How confident we are (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0


class UserPreferences:
    """
    Stored in Agno PostgreSQL alongside conversation history.
    """
    
    # DB URL sourced from network.env via config.py
    DEFAULT_DB_URL = AGNO_DB_URL
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._preferences: Dict[str, UserPreference] = {}
    
    def set(self, key: str, value: Any, task_type: str = "general", confidence: float = 1.0):
        """Set a preference."""
        self._preferences[key] = UserPreference(
            key=key,
            value=value,
            task_type=task_type,
            confidence=confidence
        )
    
    def get(self, key: str, default=None) -> Any:
        """Get a preference value."""
        pref = self._preferences.get(key)
        if pref:
            pref.last_used = datetime.now()
            pref.use_count += 1
            return pref.value
        return default
    
    def get_for_task(self, task_type: str) -> Dict[str, Any]:
        """Get all preferences relevant to a task type."""
        return {
            k: v.value 
            for k, v in self._preferences.items() 
            if v.task_type == task_type or v.task_type == "general"
        }
    
    def to_dict(self) -> dict:
        """Serialize for storage in agent memory."""
        return {
            "user_id": self.user_id,
            "preferences": {
                k: {
                    "value": v.value,
                    "task_type": v.task_type,
                    "confidence": v.confidence,
                    "use_count": v.use_count
                }
                for k, v in self._preferences.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserPreferences":
        """Deserialize from agent memory."""
        prefs = cls(data.get("user_id", "unknown"))
        for k, v in data.get("preferences", {}).items():
            prefs._preferences[k] = UserPreference(
                key=k,
                value=v["value"],
                task_type=v.get("task_type", "general"),
                confidence=v.get("confidence", 1.0),
                use_count=v.get("use_count", 0)
            )
        return prefs


# =============================================================================
# CONFIRMATION STATE (Human-in-the-Loop)
# =============================================================================

@dataclass
class PendingAction:
    """An action awaiting user confirmation."""
    action_type: str  # e.g., "generate_image", "execute_code"
    original_request: str  # User's original message
    inferred_params: Dict[str, Any]  # Params inferred from preferences
    suggested_prompt: str  # What we'll actually execute
    created_at: datetime = field(default_factory=datetime.now)


class ConfirmationState:
    """
    Tracks pending actions that need user confirmation.
    
    Flow:
    1. User: "Generate a sunset"
    2. Agent: queue_action("generate_image", style="cyberpunk")
    3. Agent: "I'll make it cyberpunk. OK?"
    4. User: "Yes"
    5. Agent: confirm() -> executes with cyberpunk style
    """
    
    def __init__(self):
        self._pending: Optional[PendingAction] = None
    
    @property
    def has_pending(self) -> bool:
        return self._pending is not None
    
    def queue(self, action_type: str, original_request: str, 
              inferred_params: Dict[str, Any], suggested_prompt: str):
        """Queue an action for confirmation."""
        self._pending = PendingAction(
            action_type=action_type,
            original_request=original_request,
            inferred_params=inferred_params,
            suggested_prompt=suggested_prompt
        )
    
    def modify(self, **new_params):
        """Modify the pending action's parameters."""
        if self._pending:
            self._pending.inferred_params.update(new_params)
    
    def confirm(self) -> Optional[PendingAction]:
        """Confirm and return the pending action."""
        if not self._pending:
            return None
        result = self._pending
        self._pending = None
        return result
    
    def reject(self):
        """Reject the pending action."""
        self._pending = None
    
    def get_pending(self) -> Optional[PendingAction]:
        """Get the pending action without confirming."""
        return self._pending


# =============================================================================
# CONFIRMATION INSTRUCTIONS (For Agent)
# =============================================================================

CONFIRMATION_INSTRUCTIONS = """
=== PREFERENCE CONFIRMATION PROTOCOL ===
When a user makes a creative request (image, 3D, art, code, etc.):

1. CHECK MEMORY: Look at conversation history for stated preferences.

2. IF preferences exist AND are relevant:
   - ASK for confirmation before applying them.
   - Format: "I remember you prefer [X]. Would you like that, or something different?"
   
3. IF no relevant preferences:
   - Ask what style/approach they'd like.
   - Remember their answer for future use.

4. ONLY execute the task AFTER user confirms or specifies.

=== PREFERENCE LEARNING ===
When a user expresses a preference, acknowledge and remember it:
  "Got it! I'll remember you prefer [X] for future suggestions."

=== EXAMPLE DIALOGS ===

Example 1 (Confirmation):
  User: Generate an image of a sunset
  You: I remember you said you like cyberpunk aesthetics. Would you like a cyberpunk-style sunset, or something different?
  User: Yes, cyberpunk please
  You: [Generate cyberpunk sunset]

Example 2 (Override):
  User: Generate an image of a cat
  You: I remember you prefer cyberpunk style. Would you like that for the cat?
  User: No, make it watercolor instead
  You: Got it! [Generate watercolor cat]

Example 3 (New Preference):
  User: I really like art deco style
  You: Noted! I'll remember you prefer art deco for future suggestions.
"""


def get_confirmation_instructions() -> str:
    """Returns the confirmation protocol instructions for agents."""
    return CONFIRMATION_INSTRUCTIONS
