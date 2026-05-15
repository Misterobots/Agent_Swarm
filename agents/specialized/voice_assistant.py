import logging
import os
import random
import re
import threading
from datetime import datetime
from collections import deque
from pydantic import BaseModel
from typing import Optional, Dict, List
from tools.home_assistant import HomeAssistantTool
from specialized.voice_cloning import clone_voice
from phi.agent import Agent
from phi.model.ollama import Ollama
from config import get_ollama_options
from phi.tools import Toolkit
from specialized.voice_samples_map import get_sample_path, find_sample_in_response
from specialized.bmo_persona import BMO_SYSTEM_PROMPT, detect_bmo_emotion
from tools.assistant_tools import WeatherTool, TimeTool, NewsTool

# Setup Logger
logger = logging.getLogger("VoiceAssistant")
logger.setLevel(logging.INFO)

# --- Config ---
BMO_MODEL = os.getenv("BMO_LLM_MODEL", "qwen3:14b")
BMO_OLLAMA_HOST = os.getenv("BMO_OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
MAX_MEMORY = 10  # Keep last 10 exchanges
MEMPALACE_API_URL = os.getenv("MEMPALACE_API_URL", "http://mempalace:8200")

# Pre-baked acknowledgement phrases — spoken immediately while LLM processes
_ACK_PHRASES = [
    "Beemo is on it.",
    "Checking now.",
    "Give Beemo a moment.",
    "Computations starting.",
    "Beemo is thinking.",
]

# Status update phrases — spoken if LLM takes more than ~10 seconds
_STATUS_PHRASES = [
    "Beemo is still working on that.",
    "Almost there, maybe.",
    "Beemo is still computing.",
    "Still on it. Give Beemo a second.",
]


def _clean_response(text: str) -> str:
    """Remove LLM artifacts before TTS: think tags, markdown, AI disclaimers."""
    # Strip qwen3 thinking blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown formatting
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)   # code blocks
    text = re.sub(r"`([^`]+)`", r"\1", text)                  # inline code
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)              # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)                  # italic
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
    text = re.sub(r"^[-*•]\s+", "", text, flags=re.MULTILINE)   # bullets
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)   # numbered lists
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)    # markdown links
    # Collapse newlines/extra whitespace to single space
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    # Log and strip AI-disclaimer phrases (character break detection)
    if re.search(r"(?i)(as an ai|i'm an ai|i am an ai|as a language model|as an ai assistant)", text):
        logger.warning("⚠️ BMO character break detected — AI disclaimer in response. Stripping.")
        text = re.sub(r"(?i)(as an ai|i'm an ai|i am an ai|as a language model|as an ai assistant)[^.!?]*[.!?]?", "", text)
    return text.strip()


def _strip_think_tags(text: str) -> str:
    """Legacy alias — use _clean_response() for new code."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


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


class WebSearchTool(Toolkit):
    """Web search via DuckDuckGo Lite. No API key required."""

    def __init__(self):
        super().__init__(name="web_search")
        self.register(self.search)

    def search(self, query: str) -> str:
        """Search the web for real-time information: store hours, news, prices, facts, events.
        Use this whenever the user asks about something you don't know or that may have changed.
        Returns a short summary of the top results."""
        try:
            from tools.web_browser import web_search
            results = web_search(query, num_results=4)
            if not results:
                return "No results found."
            # Summarise into a compact string for the LLM
            lines = []
            for r in results:
                title = r.get("title", "").strip()
                snippet = r.get("snippet", r.get("body", "")).strip()
                if title or snippet:
                    lines.append(f"{title}: {snippet}" if title else snippet)
            return "\n".join(lines[:4]) if lines else "No useful results."
        except Exception as e:
            logger.warning(f"WebSearch failed: {e}")
            return f"Search unavailable: {e}"


class Message(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict] = {}


class VoiceAssistantAgent:
    def __init__(self):
        self.name = "BMO"
        self.description = "BMO handles voice interactions and Home Assistant control with personality."
        self.conversation_history: deque = deque(maxlen=MAX_MEMORY * 2)  # user + assistant pairs

        # Ack audio cache — pre-baked on startup so first ack is instant
        self._ack_cache: list = []       # list of (text, audio_path)
        self._status_cache: list = []    # list of (text, audio_path)
        self._ack_lock = threading.Lock()
        
        # Tools
        self.smart_home = SmartHomeTool()
        self.weather = WeatherTool()
        self.time_tool = TimeTool()
        self.news = NewsTool()
        self.web_search = WebSearchTool()
        
        # LLM Agent with all tools
        self.llm_agent = Agent(
            model=Ollama(id=BMO_MODEL, host=BMO_OLLAMA_HOST, options=get_ollama_options(BMO_MODEL)),
            description=BMO_SYSTEM_PROMPT,
            tools=[self.smart_home, self.weather, self.time_tool, self.news, self.web_search],
            show_tool_calls=False,
            markdown=False,
            add_history_to_messages=True,
            num_history_responses=8,  # keep last 8 exchanges in context window
        )

        # Pre-bake ack/status audio in the background — ready before first real request
        threading.Thread(target=self._prebake_audio, daemon=True).start()

    def _prebake_audio(self):
        """Generate ack and status audio files at startup and cache their paths."""
        for phrase in _ACK_PHRASES:
            try:
                path = clone_voice(phrase, effect="BMO")
                if path:
                    with self._ack_lock:
                        self._ack_cache.append((phrase, path))
                    logger.info(f"🔊 Prebaked ack: {phrase!r}")
            except Exception as e:
                logger.warning(f"Prebake failed for {phrase!r}: {e}")
        for phrase in _STATUS_PHRASES:
            try:
                path = clone_voice(phrase, effect="BMO")
                if path:
                    with self._ack_lock:
                        self._status_cache.append((phrase, path))
                    logger.info(f"🔊 Prebaked status: {phrase!r}")
            except Exception as e:
                logger.warning(f"Prebake failed for {phrase!r}: {e}")

    def get_ack(self) -> tuple:
        """Return (text, audio_path) for an immediate ack. Falls back to text-only if not ready."""
        with self._ack_lock:
            if self._ack_cache:
                return random.choice(self._ack_cache)
        return (random.choice(_ACK_PHRASES), None)

    def get_status_update(self) -> tuple:
        """Return (text, audio_path) for a 'still working' status update."""
        with self._ack_lock:
            if self._status_cache:
                return random.choice(self._status_cache)
        return (random.choice(_STATUS_PHRASES), None)

    def _recall_memories(self, user_text: str) -> str:
        """Query MemPalace for facts relevant to this turn. Non-fatal, 3s timeout."""
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(
                    f"{MEMPALACE_API_URL}/v1/memories/search",
                    json={"query": user_text, "agent_id": "bmo", "limit": 4},
                )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    return "\n".join(f"- {m['content']}" for m in results[:4])
        except Exception as e:
            logger.debug(f"MemPalace recall failed (non-fatal): {e}")
        return ""

    def _store_memory_async(self, user_text: str, response_text: str):
        """Fire-and-forget: send exchange to MemPalace /v1/extract (LLM-based, runs in background)."""
        def _run():
            try:
                import httpx
                with httpx.Client(timeout=60.0) as client:
                    client.post(
                        f"{MEMPALACE_API_URL}/v1/extract",
                        json={
                            "conversation": f"User: {user_text}\nBMO: {response_text}",
                            "agent_id": "bmo",
                        },
                    )
            except Exception as e:
                logger.debug(f"MemPalace store failed (non-fatal): {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _build_context(self, user_text: str, memories: str = "") -> str:
        """Build context-enriched prompt with time and persistent memories."""
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
        parts = [f"[System Context: Current time: {time_str}. {greeting_hint}]"]
        if memories:
            parts.append(f"\n[What BMO knows about you]\n{memories}")
        parts.append(f"\n{user_text}")
        return "\n".join(parts)

    def _build_sandbox_metadata(
        self,
        user_text: str,
        response_text: str,
        sample_match: str | None,
        response_sample: str | None,
        audio_path: str | None,
    ) -> Dict:
        emotion, pitch, speed = detect_bmo_emotion(response_text)
        metadata: Dict[str, object] = {
            "user_text": user_text,
            "emotion": emotion,
            "pitch": pitch,
            "speed": speed,
            "sample_match": sample_match,
            "response_sample": response_sample,
            "audio_path": audio_path,
            "audio_kind": "generated",
        }
        if sample_match:
            metadata["audio_kind"] = "sample_input"
        elif response_sample:
            metadata["audio_kind"] = "sample_response"

        sample_file = sample_match or response_sample
        if sample_file:
            metadata["sample_file"] = sample_file
            metadata["sample_url"] = f"/voice_samples/{sample_file}"

        return metadata

    def process(self, message: Message) -> Message:
        """Process user input: samples → LLM (with HA tools) → voice."""
        user_text = message.content.strip()
        logger.info(f"Processing: {user_text}")

        # 1. Fast Path: Check for exact sample matches for the INPUT
        sample_path = get_sample_path(user_text)
        if sample_path:
            full_sample_path = f"/app/agents/bmo_voice/voice_samples/{sample_path}"
            logger.info(f"🎯 Sample Fast-Path: {sample_path}")
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": user_text})
            sandbox = self._build_sandbox_metadata(user_text, user_text, sample_path, None, full_sample_path)
            return Message(role="assistant", content=user_text, metadata=sandbox)

        # 2. LLM with Tool Calling (handles HA + general conversation)
        memories = self._recall_memories(user_text)
        context = self._build_context(user_text, memories)
        response = self.llm_agent.run(context)
        response_text = _clean_response(response.content)

        # Update in-session memory and kick off persistent MemPalace store
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": response_text})
        self._store_memory_async(user_text, response_text)

        # 3. Scan LLM response for embedded sample phrases
        response_sample = find_sample_in_response(response_text)
        if response_sample:
            full_sample_path = f"/app/agents/bmo_voice/voice_samples/{response_sample}"
            logger.info(f"🎯 Response Sample Match: {response_sample}")
            sandbox = self._build_sandbox_metadata(user_text, response_text, None, response_sample, full_sample_path)
            return Message(role="assistant", content=response_text, metadata=sandbox)

        # 4. Generate Voice Response (Fish Audio / RVC)
        logger.info(f"Response: {response_text}")
        audio_path = None
        try:
            audio_path = clone_voice(response_text, effect="BMO")
        except Exception as e:
            logger.error(f"Voice generation failed: {e}")
            audio_path = None

        sandbox = self._build_sandbox_metadata(user_text, response_text, None, None, audio_path)
        return Message(role="assistant", content=response_text, metadata=sandbox)
