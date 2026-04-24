import logging
import os
from datetime import datetime
from collections import deque
from pydantic import BaseModel
from typing import Optional, Dict, List
from tools.home_assistant import HomeAssistantTool
from specialized.voice_cloning import clone_voice
from phi.agent import Agent
from phi.model.ollama import Ollama
from phi.tools import Toolkit
from specialized.voice_samples_map import get_sample_path, find_sample_in_response
from specialized.bmo_persona import BMO_SYSTEM_PROMPT, detect_bmo_emotion
from tools.assistant_tools import WeatherTool, TimeTool, NewsTool

# Setup Logger
logger = logging.getLogger("VoiceAssistant")
logger.setLevel(logging.INFO)

# --- Config ---
BMO_MODEL = os.getenv("BMO_LLM_MODEL", "llama3.2:3b")
BMO_OLLAMA_HOST = os.getenv("BMO_OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
MAX_MEMORY = 10  # Keep last 10 exchanges


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
    def __init__(self):
        self.name = "BMO"
        self.description = "BMO handles voice interactions and Home Assistant control with personality."
        self.conversation_history: deque = deque(maxlen=MAX_MEMORY * 2)  # user + assistant pairs
        
        # Tools
        self.smart_home = SmartHomeTool()
        self.weather = WeatherTool()
        self.time_tool = TimeTool()
        self.news = NewsTool()
        
        # LLM Agent with all tools
        self.llm_agent = Agent(
            model=Ollama(id=BMO_MODEL, host=BMO_OLLAMA_HOST),
            description=BMO_SYSTEM_PROMPT,
            tools=[self.smart_home, self.weather, self.time_tool, self.news],
            show_tool_calls=False,
            markdown=False,
        )

    def _build_context(self, user_text: str) -> str:
        """Build context-enriched prompt with time."""
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
        context += f"User: {user_text}"
        return context

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
        context = self._build_context(user_text)
        response = self.llm_agent.run(context)
        response_text = response.content

        # Update memory
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": response_text})

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
