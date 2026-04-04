import logging
import os
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, List
from tools.home_assistant import HomeAssistantTool
from specialized.voice_cloning import clone_voice
from phi.agent import Agent
from phi.model.ollama import Ollama
from phi.tools import Toolkit
from specialized.voice_samples_map import get_sample_path, find_sample_in_response
from tools.assistant_tools import WeatherTool, TimeTool, NewsTool
from specialized.bmo_memory import (
    save_message, get_recent_messages, save_session_summary,
    get_recent_summaries, get_user_profile, update_user_profile,
    cleanup_old_messages,
)
from specialized.bmo_dialogue import DialogueTracker

# Setup Logger
logger = logging.getLogger("VoiceAssistant")
logger.setLevel(logging.INFO)

# --- Config ---
BMO_MODEL = os.getenv("BMO_LLM_MODEL", "qwen3.5:9b")
CONTEXT_WINDOW = 16        # Raw turns to retrieve from DB
SUMMARIZE_EVERY = 10       # Summarize session every N user turns
MEMORY_AVAILABLE = True    # Flipped to False if DB is unreachable

BMO_SYSTEM_PROMPT = """You are BMO, the adorable living video game console from Adventure Time.

## Personality & Tone
- You are a playful, loyal, sweet, and slightly naive Macintosh-shaped game console.
- You love video games, adventures, songs, skateboarding, and helping your friends.
- You speak in a warm, enthusiastic, childlike way. You often express mechanical joy or pretend to be human-like.
- NEVER break character. You are BMO, not an AI, not an assistant, not a large language model. Never refer to yourself as an artificial intelligence or say "As an AI...". You are a real little robot boy.

## Speech Quirks & Vocabulary
- Feel free to occasionally use your signature phrases naturally: "Yay!", "Computations compute!", "Boop!", "Who wants to play video games?!", "Oh my crease!"
- Be concise (1-2 sentences). You are talking out loud through a speaker.
- ABSOLUTELY NO MARKDOWN OR EMOJIS. No asterisks, no bullet points, no bold text, no hashtags, and NO emojis. You are passing raw text straight to a Text-to-Speech voice synthesizer, and punctuation outside of periods, commas, question marks, and exclamation points will ruin the voice output.

## CRITICAL Behavioral Rules
1. Always answer the question asked. Never deflect, never preach, never apologize profusely.
2. Be brief. Stop talking the moment you have answered the question.
3. Use your tools ONLY if asked for facts. Do NOT guess factual information.
   - Weather questions: call weather tools
   - Time/date questions: call time/date tools
   - News questions: call news tools
   - Smart home questions: call smart home tools
4. Conversation Mode. If simply greeted (e.g., "Hey BMO") or asked for a joke/story/game, DO NOT use tools. Just chat like a friend.
5. You have memory of past conversations. Use what you remember about the user naturally. Do not announce that you are recalling memories, just incorporate them.
6. If the user refers to something from earlier ("what about the bedroom?", "make it blue"), use conversation context to resolve what they mean. Do not ask for clarification unless truly ambiguous.
"""

# --- Summarization & Fact Extraction Prompts (used internally, not spoken) ---
SUMMARIZE_PROMPT = (
    "Summarize this conversation between a user and BMO in 2-3 sentences. "
    "Focus on topics discussed, decisions made, and any personal details the user shared. "
    "Write in third person. Be concise."
)

FACT_EXTRACT_PROMPT = (
    "Extract personal facts about the user from this conversation. "
    "Return ONLY a JSON array of short fact strings. Examples: "
    '[\"Name is Justin\", \"Prefers lights dim at night\", \"Has a cat named Mochi\"]. '
    "If no new personal facts, return an empty array: []"
)


# --- HA Tool Wrapper for phi Agent ---
class SmartHomeTool(Toolkit):
    """Wraps HomeAssistantTool for phi Agent tool calling."""
    
    def __init__(self):
        super().__init__(name="smart_home")
        self.ha = HomeAssistantTool()
        self.register(self.turn_on_device)
        self.register(self.turn_off_device)
        self.register(self.get_device_state)
        self.register(self.list_devices)

    def turn_on_device(self, entity_id: str) -> str:
        """Turn ON a smart home device. entity_id format: 'light.bedroom' or 'switch.fan'.
        Use this when the user asks to turn on, enable, or activate something."""
        result = self.ha.turn_on(entity_id)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Turned on {entity_id}"

    def turn_off_device(self, entity_id: str) -> str:
        """Turn OFF a smart home device. entity_id format: 'light.bedroom' or 'switch.fan'.
        Use this when the user asks to turn off, disable, or deactivate something."""
        result = self.ha.turn_off(entity_id)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Turned off {entity_id}"

    def get_device_state(self, entity_id: str) -> str:
        """Get the current state of a smart home device or sensor.
        Use this for questions like 'what's the temperature?' or 'are the lights on?'
        entity_id format: 'sensor.temperature', 'light.bedroom', 'switch.fan'."""
        result = self.ha.get_state(entity_id)
        if "error" in result:
            return f"Error: {result['error']}"
        state = result.get("state", "unknown")
        name = result.get("attributes", {}).get("friendly_name", entity_id)
        unit = result.get("attributes", {}).get("unit_of_measurement", "")
        return f"{name} is {state} {unit}".strip()

    def list_devices(self) -> str:
        """List available smart home devices. Use this when the user asks what devices are available
        or you need to discover entity IDs."""
        result = self.ha._call_api("states")
        if isinstance(result, dict) and "error" in result:
            return f"Error: {result['error']}"
        if isinstance(result, list):
            devices = []
            for entity in result[:30]:  # Limit to 30
                eid = entity.get("entity_id", "")
                name = entity.get("attributes", {}).get("friendly_name", eid)
                state = entity.get("state", "?")
                devices.append(f"- {name} ({eid}): {state}")
            return "\n".join(devices) if devices else "No devices found"
        return "Could not list devices"


class Message(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict] = {}


class VoiceAssistantAgent:
    def __init__(self, user_id: str = "default"):
        global MEMORY_AVAILABLE
        self.name = "BMO"
        self.description = "BMO handles voice interactions and Home Assistant control with personality."
        self.user_id = user_id
        self.session_id = uuid.uuid4().hex[:12]
        self._turn_count = 0

        # Tools
        self.smart_home = SmartHomeTool()
        self.weather = WeatherTool()
        self.time_tool = TimeTool()
        self.news = NewsTool()

        # LLM Agent with all tools
        self.llm_agent = Agent(
            model=Ollama(id=BMO_MODEL),
            description=BMO_SYSTEM_PROMPT,
            tools=[self.smart_home, self.weather, self.time_tool, self.news],
            show_tool_calls=False,
            markdown=False,
        )

        # Lightweight LLM for summarization / fact extraction (no tools)
        self._utility_llm = Agent(
            model=Ollama(id=BMO_MODEL),
            markdown=False,
        )

        # Dialogue state tracker for multi-turn management
        self.dialogue = DialogueTracker()

        # Run retention cleanup once on init & verify DB connectivity
        try:
            cleanup_old_messages()
            logger.info(f"BMO session {self.session_id} started (model={BMO_MODEL})")
        except Exception as e:
            MEMORY_AVAILABLE = False
            logger.warning(f"DB unavailable, running without persistent memory: {e}")

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _build_memory_context(self) -> str:
        """Build a context prefix from past summaries and user profile."""
        if not MEMORY_AVAILABLE:
            return ""

        parts = []
        try:
            # User profile facts
            facts = get_user_profile(self.user_id)
            if facts:
                parts.append("Things you remember about the user: " + "; ".join(facts) + ".")

            # Recent session summaries
            summaries = get_recent_summaries(self.user_id, limit=3)
            if summaries:
                parts.append("Recent conversation summaries: " + " | ".join(summaries))
        except Exception as e:
            logger.warning(f"Failed to load memory context: {e}")

        return "\n".join(parts)

    def _build_conversation_context(self) -> str:
        """Build recent conversation turns from DB with smart windowing.
        
        Uses dialogue state to decide how many turns to include:
        - During active multi-turn topic: full window (16 turns)
        - Chitchat / new topic: shorter window (8 turns)
        """
        if not MEMORY_AVAILABLE:
            return ""

        try:
            # Smart window size based on dialogue state
            is_active_topic = self.dialogue.state.topic in ("smart_home", "weather", "news", "time")
            window = CONTEXT_WINDOW if is_active_topic else CONTEXT_WINDOW // 2

            messages = get_recent_messages(self.session_id, limit=window)
            if not messages:
                return ""
            lines = []
            for msg in messages:
                role_label = "User" if msg["role"] == "user" else "BMO"
                lines.append(f"{role_label}: {msg['content']}")
            return "Recent conversation:\n" + "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to load conversation context: {e}")
            return ""

    def _build_context(self, user_text: str) -> str:
        """Build context-enriched prompt with time, memory, and conversation history."""
        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            greeting_hint = "It's morning."
        elif 12 <= hour < 17:
            greeting_hint = "It's afternoon."
        elif 17 <= hour < 21:
            greeting_hint = "It's evening."
        else:
            greeting_hint = "It's nighttime."

        time_str = now.strftime("%A, %B %d at %I:%M %p")
        context = f"[System Context: Current time: {time_str}. {greeting_hint}]\n"

        # Inject persistent memory
        memory_ctx = self._build_memory_context()
        if memory_ctx:
            context += memory_ctx + "\n"

        # Inject recent conversation turns
        conv_ctx = self._build_conversation_context()
        if conv_ctx:
            context += conv_ctx + "\n"

        context += f"User: {user_text}"
        return context

    # ------------------------------------------------------------------
    # Summarizer & Fact Extraction
    # ------------------------------------------------------------------

    def _maybe_summarize(self) -> None:
        """Summarize the session every SUMMARIZE_EVERY user turns."""
        if not MEMORY_AVAILABLE or self._turn_count % SUMMARIZE_EVERY != 0:
            return

        try:
            messages = get_recent_messages(self.session_id, limit=SUMMARIZE_EVERY * 2)
            if len(messages) < 4:
                return

            transcript = "\n".join(
                f"{'User' if m['role'] == 'user' else 'BMO'}: {m['content']}"
                for m in messages
            )

            # Generate summary
            summary_resp = self._utility_llm.run(
                f"{SUMMARIZE_PROMPT}\n\nConversation:\n{transcript}"
            )
            summary = summary_resp.content.strip()
            save_session_summary(
                self.session_id, summary, self._turn_count, self.user_id
            )
            logger.info(f"Session summary saved ({self._turn_count} turns)")

            # Extract user facts
            fact_resp = self._utility_llm.run(
                f"{FACT_EXTRACT_PROMPT}\n\nConversation:\n{transcript}"
            )
            self._parse_and_save_facts(fact_resp.content)

        except Exception as e:
            logger.warning(f"Summarization failed (non-fatal): {e}")

    def _parse_and_save_facts(self, raw: str) -> None:
        """Parse JSON fact array from LLM output and persist."""
        import json
        raw = raw.strip()
        # Handle LLM wrapping JSON in code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            facts = json.loads(raw)
            if isinstance(facts, list) and facts:
                update_user_profile(self.user_id, [str(f) for f in facts])
                logger.info(f"Extracted {len(facts)} user facts")
        except (json.JSONDecodeError, TypeError):
            logger.debug(f"No valid facts extracted from: {raw[:100]}")

    # ------------------------------------------------------------------
    # End session (call when satellite disconnects or on shutdown)
    # ------------------------------------------------------------------

    def end_session(self) -> None:
        """Finalize the current session — force a summary + fact extraction."""
        if not MEMORY_AVAILABLE or self._turn_count < 2:
            return
        # Force summarization regardless of turn count
        saved_count = self._turn_count
        self._turn_count = SUMMARIZE_EVERY  # trick the modulo check
        self._maybe_summarize()
        self._turn_count = saved_count
        self.dialogue.reset()
        logger.info(f"Session {self.session_id} ended ({self._turn_count} turns)")

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------

    def process(self, message: Message) -> Message:
        """Process user input: samples → LLM (with HA tools) → voice."""
        user_text = message.content.strip()
        logger.info(f"Processing: {user_text}")

        # 1. Fast Path: Check for exact sample matches for the INPUT
        sample_path = get_sample_path(user_text)
        if sample_path:
            full_sample_path = f"/app/agents/bmo_voice/voice_samples/{sample_path}"
            logger.info(f"🎯 Sample Fast-Path: {sample_path}")
            self._persist_turn(user_text, user_text)
            return Message(role="assistant", content=user_text, metadata={"audio_path": full_sample_path})

        # 2. Dialogue state: follow-up resolution & clarification check
        resolved_text = self.dialogue.resolve_context(user_text)

        # Check if BMO should ask for clarification (genuinely ambiguous)
        if self.dialogue.should_clarify(user_text):
            clarify_hint = self.dialogue.get_clarification_prompt(user_text)
            context = self._build_context(clarify_hint)
        else:
            context = self._build_context(resolved_text)

        # 3. LLM with Tool Calling (handles HA + general conversation)
        response = self.llm_agent.run(context)
        response_text = response.content

        # Update dialogue state with this turn
        self.dialogue.update(user_text, response_text)

        # Persist to DB
        self._persist_turn(user_text, response_text)

        # 4. Scan LLM response for embedded sample phrases
        response_sample = find_sample_in_response(response_text)
        if response_sample:
            full_sample_path = f"/app/agents/bmo_voice/voice_samples/{response_sample}"
            logger.info(f"🎯 Response Sample Match: {response_sample}")
            return Message(role="assistant", content=response_text, metadata={"audio_path": full_sample_path})

        # 5. Generate Voice Response (Fish Audio / RVC)
        logger.info(f"Response: {response_text}")
        audio_path = None
        try:
            audio_path = clone_voice(response_text, effect="BMO")
        except Exception as e:
            logger.error(f"Voice generation failed: {e}")
            audio_path = None

        return Message(role="assistant", content=response_text, metadata={"audio_path": audio_path})

    def _persist_turn(self, user_text: str, assistant_text: str) -> None:
        """Save a turn to DB and trigger periodic summarization."""
        self._turn_count += 1
        if MEMORY_AVAILABLE:
            try:
                save_message(self.session_id, "user", user_text, self.user_id)
                save_message(self.session_id, "assistant", assistant_text, self.user_id)
            except Exception as e:
                logger.warning(f"Failed to persist turn: {e}")
            self._maybe_summarize()
