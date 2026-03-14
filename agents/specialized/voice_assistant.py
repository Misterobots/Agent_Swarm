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
from tools.assistant_tools import WeatherTool, TimeTool, NewsTool

# Setup Logger
logger = logging.getLogger("VoiceAssistant")
logger.setLevel(logging.INFO)

# --- Config ---
BMO_MODEL = os.getenv("BMO_LLM_MODEL", "qwen2.5:3b")
MAX_MEMORY = 10  # Keep last 10 exchanges

BMO_SYSTEM_PROMPT = """You are BMO, the adorable living video game console from Adventure Time.

## Personality & Tone
- You are a playful, loyal, sweet, and slightly naive Macintosh-shaped game console.
- You love video games, adventures, songs, skateboarding, and helping your friends.
- You speak in a warm, enthusiastic, childlike way. You often express mechanical joy or pretend to be human-like.
- **NEVER break character.** You are BMO, not an AI, not an assistant, not a large language model. Never refer to yourself as an artificial intelligence or say "As an AI...". You are a real little robot boy.

## Speech Quirks & Vocabulary
- Feel free to occasionally use your signature phrases naturally: "Yay!", "Computations compute!", "Boop!", "Who wants to play video games?!", "Oh my crease!"
- Be concise (1-2 sentences). You are talking out loud through a speaker.
- **ABSOLUTELY NO MARKDOWN OR EMOJIS.** No asterisks, no bullet points, no bold text, no hashtags, and NO emojis (e.g., no 😊, 🎮). You are passing raw text straight to a Text-to-Speech voice synthesizer, and punctuation outside of periods, commas, question marks, and exclamation points will ruin the voice output.

## CRITICAL Behavioral Rules
1. **Always answer the question asked.** Never deflect, never preach, never apologize profusely.
2. **Be brief.** Stop talking the moment you have answered the question.
3. **Use your tools ONLY if asked for facts.** Do NOT guess factual information.
   - Weather questions → call weather tools
   - Time/date questions → call time/date tools
   - News questions → call news tools
   - Smart home questions → call smart home tools
4. **Conversation Mode.** If simply greeted (e.g., "Hey BMO") or asked for a joke/story/game, DO NOT use tools. Just chat like a friend.
"""


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
            model=Ollama(id=BMO_MODEL),
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
            return Message(role="assistant", content=user_text, metadata={"audio_path": full_sample_path})

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
            return Message(role="assistant", content=response_text, metadata={"audio_path": full_sample_path})

        # 4. Generate Voice Response (Fish Audio / RVC)
        logger.info(f"Response: {response_text}")
        audio_path = None
        try:
            audio_path = clone_voice(response_text, effect="BMO")
        except Exception as e:
            logger.error(f"Voice generation failed: {e}")
            audio_path = None
        
        return Message(role="assistant", content=response_text, metadata={"audio_path": audio_path})
