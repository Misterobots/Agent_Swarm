from phi.agent import Agent
from phi.model.ollama import Ollama
import os
import requests
from specialized.bmo_persona import BMO_SYSTEM_PROMPT
from config import get_ollama_options

def get_bmo_agent() -> Agent:
    """
    Returns the BMO Voice Agent.
    """
    MODEL_NAME = os.getenv("BMO_LLM_MODEL", "llama3.2:3b")
    OLLAMA_HOST = os.getenv("BMO_OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    # Qwen3-TTS voice engine (voice_engine_gpu on execution_net); the old bmo-voice-gpu
    # RVC container was retired.
    BMO_VOICE_URL = os.getenv("BMO_VOICE_URL", "http://voice_engine_gpu:8020/speak")

    def generate_bmo_speech(text: str) -> str:
        """
        Generates speech in BMO's voice from the given text.

        Args:
            text (str): The text to be spoken.

        Returns:
            str: Status message.
        """
        try:
            # For now, we just ping the endpoint to verify connectivity
            # In a real scenario, we would post the text and get back an audio file ID or URL
            response = requests.post(BMO_VOICE_URL, params={"text": text}, timeout=90)
            if response.status_code == 200:
                return f"Successfully sent to BMO Voice Engine: {text}"
            else:
                return f"Error from BMO Voice Engine: {response.text}"
        except Exception as e:
            return f"Failed to connect to BMO Voice Engine: {e}"

    return Agent(
        name="BMO Agent",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST, options=get_ollama_options(MODEL_NAME)),
        description=BMO_SYSTEM_PROMPT,
        instructions=[
            "When asked to generate speech, use the 'generate_bmo_speech' tool.",
        ],
        tools=[generate_bmo_speech],
        show_tool_calls=False,
        markdown=False,
    )
