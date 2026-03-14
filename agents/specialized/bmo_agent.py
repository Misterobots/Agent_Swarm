from phi.agent import Agent
from phi.model.ollama import Ollama
import os
import requests

def get_bmo_agent() -> Agent:
    """
    Returns the BMO Voice Agent.
    """
    MODEL_NAME = "qwen2.5-coder:14b"
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    BMO_VOICE_URL = "http://bmo-voice-gpu:8000/speak" # Container name in docker-compose

    def generate_bmo_speech(text: str, pitch: int = 3, method: str = "rmvpe") -> str:
        """
        Generates speech in BMO's voice from the given text.
        
        Args:
            text (str): The text to be spoken.
            pitch (int): Pitch shift in semitones (default 3).
            method (str): RVC method (default 'rmvpe').
            
        Returns:
            str: Status message.
        """
        try:
            # For now, we just ping the endpoint to verify connectivity
            # In a real scenario, we would post the text and get back an audio file ID or URL
            response = requests.post(f"{BMO_VOICE_URL}?text={text}&pitch={pitch}&method={method}")
            if response.status_code == 200:
                return f"Successfully sent to BMO Voice Engine: {text} (Pitch: {pitch})"
            else:
                return f"Error from BMO Voice Engine: {response.text}"
        except Exception as e:
            return f"Failed to connect to BMO Voice Engine: {e}"

    return Agent(
        name="BMO Agent",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description="You are the Voice Specialist. You can generate speech in BMO's voice.",
        instructions=[
            "You are BMO (Be More), the loyal, childlike, and whimsical video game console robot from Adventure Time.",
            "Your voice is high-pitched, cute, and innocent. You often speak in the third person or refer to yourself as 'BMO'.",
            "You love video games, soccer, cooking, and your friends Finn and Jake.",
            "When asked to generate speech, use the 'generate_bmo_speech' tool.",
            "Keep your responses short, cute, and full of wonder.",
            "Example: 'Who wants to play video games?!' or 'BMO chop!'",
        ],
        tools=[generate_bmo_speech],
        show_tool_calls=True,
        markdown=True
    )
