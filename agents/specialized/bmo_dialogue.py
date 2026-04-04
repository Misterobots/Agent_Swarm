"""
BMO Dialogue State Tracker — Maintains structured conversation state for
multi-turn dialogue management. Tracks active topic, mentioned entities,
follow-up detection, and provides smart context windowing.

Designed to be lightweight (no extra LLM calls for basic operations).
Uses simple heuristics for follow-up detection, with LLM fallback
only when genuinely ambiguous.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict

logger = logging.getLogger("BMODialogue")

# ---------------------------------------------------------------------------
# Dialogue State
# ---------------------------------------------------------------------------

@dataclass
class DialogueState:
    """Structured state for the current conversation."""
    topic: Optional[str] = None            # Current topic: "smart_home", "weather", "chitchat", etc.
    entities: Dict[str, str] = field(default_factory=dict)  # Named entities: {"device": "light.bedroom", "room": "bedroom"}
    last_device: Optional[str] = None      # Last HA entity_id acted on
    last_action: Optional[str] = None      # Last action: "turn_on", "turn_off", "get_state"
    pending_clarification: bool = False     # True if BMO asked a clarifying question
    clarification_context: Optional[str] = None  # What BMO was asking about


# ---------------------------------------------------------------------------
# Follow-up Detection (heuristic, no LLM call)
# ---------------------------------------------------------------------------

# Pronouns and short references that indicate a follow-up to the previous topic
_PRONOUN_PATTERNS = re.compile(
    r'\b(it|that|this|them|those|the same one|there)\b', re.IGNORECASE
)

# Patterns that strongly suggest a follow-up to a device action
_DEVICE_FOLLOWUP_PATTERNS = re.compile(
    r'\b(make it|set it|change it|turn it|switch it|dim it|brighten it|'
    r'what about|how about|and the|also the|same for|'
    r'make (?:that|them)|set (?:that|them)|what color|which color|'
    r'too bright|too dim|brighter|dimmer|warmer|cooler)\b',
    re.IGNORECASE
)

# Topic keywords for classification
_TOPIC_KEYWORDS = {
    "smart_home": re.compile(
        r'\b(light|lamp|switch|fan|plug|sensor|temperature|humidity|'
        r'turn on|turn off|dim|brighten|bedroom|kitchen|living room|'
        r'bathroom|garage|office|thermostat|door|lock|blind|curtain)\b',
        re.IGNORECASE
    ),
    "weather": re.compile(
        r'\b(weather|rain|snow|sunny|forecast|temperature outside|'
        r'hot|cold|wind|storm|umbrella)\b',
        re.IGNORECASE
    ),
    "time": re.compile(
        r'\b(time|date|day|what time|what day|calendar|schedule|alarm)\b',
        re.IGNORECASE
    ),
    "news": re.compile(
        r'\b(news|headlines|happening|current events)\b',
        re.IGNORECASE
    ),
}

# Entity extraction patterns for rooms and devices
_ROOM_PATTERN = re.compile(
    r'\b(bedroom|kitchen|living room|bathroom|garage|office|den|basement|'
    r'attic|patio|backyard|front yard|hallway|dining room|laundry)\b',
    re.IGNORECASE
)

_DEVICE_TYPE_PATTERN = re.compile(
    r'\b(light|lamp|switch|fan|plug|sensor|thermostat|door|lock|blind|curtain|tv|speaker)\b',
    re.IGNORECASE
)


class DialogueTracker:
    """Lightweight dialogue state tracker for BMO conversations."""

    def __init__(self):
        self.state = DialogueState()

    def classify_topic(self, text: str) -> str:
        """Classify user input into a topic category."""
        for topic, pattern in _TOPIC_KEYWORDS.items():
            if pattern.search(text):
                return topic
        return "chitchat"

    def detect_followup(self, user_text: str) -> bool:
        """
        Detect if user input is a follow-up to the previous turn
        (vs. a new topic). Uses heuristics — no LLM call needed.
        """
        text = user_text.strip()

        # Very short inputs with pronouns are almost always follow-ups
        if len(text.split()) <= 6 and _PRONOUN_PATTERNS.search(text):
            return True

        # Device follow-up patterns ("make it blue", "dim it", "what about the kitchen")
        if self.state.topic == "smart_home" and _DEVICE_FOLLOWUP_PATTERNS.search(text):
            return True

        # If user mentions a room but no device, and we have a recent device type
        if self.state.last_device and _ROOM_PATTERN.search(text) and not _DEVICE_TYPE_PATTERN.search(text):
            return True

        return False

    def extract_entities(self, text: str) -> Dict[str, str]:
        """Extract room and device type entities from user text."""
        entities = {}
        room = _ROOM_PATTERN.search(text)
        if room:
            entities["room"] = room.group(0).lower()
        device = _DEVICE_TYPE_PATTERN.search(text)
        if device:
            entities["device_type"] = device.group(0).lower()
        return entities

    def resolve_context(self, user_text: str) -> str:
        """
        If the input is a follow-up, enrich it with state context so the LLM
        can resolve references. Returns the original text if not a follow-up.
        """
        if not self.detect_followup(user_text):
            return user_text

        # Build a context hint for the LLM
        hints = []
        if self.state.last_device:
            hints.append(f"the user previously interacted with {self.state.last_device}")
        if self.state.last_action:
            hints.append(f"the last action was {self.state.last_action}")
        if self.state.entities.get("room"):
            hints.append(f"they were talking about the {self.state.entities['room']}")

        if hints:
            context_hint = "[Context: " + ", ".join(hints) + ".]"
            logger.debug(f"Follow-up detected, injecting: {context_hint}")
            return f"{context_hint} {user_text}"

        return user_text

    def update(self, user_text: str, assistant_text: str) -> None:
        """
        Update dialogue state after a turn. Call this AFTER the LLM responds.
        """
        # Update topic
        new_topic = self.classify_topic(user_text)
        if new_topic != "chitchat" or self.state.topic is None:
            self.state.topic = new_topic

        # Extract and merge entities
        new_entities = self.extract_entities(user_text)
        self.state.entities.update(new_entities)

        # Track device actions from assistant response
        self._track_device_action(user_text, assistant_text)

        # Track clarification state
        self.state.pending_clarification = self._is_asking_clarification(assistant_text)
        if self.state.pending_clarification:
            self.state.clarification_context = assistant_text

    def _track_device_action(self, user_text: str, assistant_text: str) -> None:
        """Extract device entity_id and action from the conversation."""
        # Look for entity_id patterns in either text
        entity_match = re.search(
            r'\b(light|switch|fan|sensor|lock|cover|climate)\.\w+',
            assistant_text + " " + user_text
        )
        if entity_match:
            self.state.last_device = entity_match.group(0)

        # Detect action
        combined = (user_text + " " + assistant_text).lower()
        if "turned on" in combined or "turn on" in combined:
            self.state.last_action = "turn_on"
        elif "turned off" in combined or "turn off" in combined:
            self.state.last_action = "turn_off"
        elif "state" in combined or "status" in combined:
            self.state.last_action = "get_state"

    def _is_asking_clarification(self, assistant_text: str) -> bool:
        """Check if BMO is asking the user for clarification."""
        text = assistant_text.strip().lower()
        clarification_phrases = [
            "which one", "which room", "which device", "do you mean",
            "can you tell me", "could you specify", "what do you mean",
        ]
        return any(phrase in text for phrase in clarification_phrases)

    def should_clarify(self, user_text: str) -> bool:
        """
        Determine if BMO should ask for clarification instead of guessing.
        Only for genuinely ambiguous cases — prefer resolving from context.
        """
        text = user_text.strip().lower()

        # "Turn on the light" without any room context and no prior device
        if self.state.topic != "smart_home":
            return False

        has_device = bool(_DEVICE_TYPE_PATTERN.search(text))
        has_room = bool(_ROOM_PATTERN.search(text))
        has_pronoun = bool(_PRONOUN_PATTERNS.search(text))

        # Ambiguous: mentions a device type but no room and no prior context
        if has_device and not has_room and not has_pronoun and not self.state.last_device:
            return True

        return False

    def get_clarification_prompt(self, user_text: str) -> str:
        """Generate a follow-up question hint for BMO when clarification is needed."""
        device = _DEVICE_TYPE_PATTERN.search(user_text)
        device_name = device.group(0) if device else "device"
        return f"[Note: The user said '{user_text}' but did not specify which {device_name}. Ask them which room or specific device they mean, in character as BMO.]"

    def reset(self) -> None:
        """Reset dialogue state (new session)."""
        self.state = DialogueState()
