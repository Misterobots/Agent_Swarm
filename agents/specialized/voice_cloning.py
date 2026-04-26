
import os
import requests
import uuid
import time
from logger_setup import setup_logger
from phi.agent import Agent
from phi.model.ollama import Ollama

# Logging Setup
logger = setup_logger("VoiceCloningExpert")

# Configuration
VOICE_ENGINE_HOST = os.getenv("VOICE_ENGINE_HOST", "http://voice_engine_gpu:8020")
MODEL_NAME = "qwen2.5-coder:14b" # Logic model for the agent itself
BMO_ENGINE_URL = os.getenv("BMO_ENGINE_URL", "http://bmo_voice_gpu:8000/speak")
DEFAULT_REF_AUDIO = "/app/agents/bmo_voice/voice_samples/Intro02_Hello_ItsMeBEEMO.wav"

# Multiple reference samples give the cloner a richer picture of BMO's voice.
# Using varied natural conversation clips rather than a single intro line.
DEFAULT_REF_AUDIO_MULTI = [
    "/app/agents/bmo_voice/voice_samples/Conversation_Parade_Interested01.wav",
    "/app/agents/bmo_voice/voice_samples/Conversation_Parade_Interested02.wav",
    "/app/agents/bmo_voice/voice_samples/Conversation_Parade_Interested03.wav",
    "/app/agents/bmo_voice/voice_samples/Conversation_Parade_Interested04.wav",
    "/app/agents/bmo_voice/voice_samples/Conversation_Parade_Interested05.wav",
    "/app/agents/bmo_voice/voice_samples/Intro02_Hello_ItsMeBEEMO.wav",
]

# Fish Audio (band-aid until local RVC is trained)
# Set FISH_AUDIO_API_KEY env var to enable. When set, overrides local RVC for BMO voice.
FISH_AUDIO_API_KEY = os.getenv("FISH_AUDIO_API_KEY", "")
FISH_AUDIO_MODEL_ID = os.getenv("FISH_AUDIO_MODEL_ID", "323847d4c5394c678e5909c2206725f6")
FISH_AUDIO_URL = "https://api.fish.audio/v1/tts"

def clone_voice(
    text: str,
    reference_audio_path: str = None, 
    reference_audio_paths: list = None,
    prompt_text: str = None,
    effect: str = None
) -> str:
    """
    Generates speech from text using the Qwen3-TTS Voice Engine.
    
    Args:
        text: The text to speak.
        reference_audio_path: (Optional) Path to a single audio file or a directory containing audio files.
        reference_audio_paths: (Optional) List of paths to audio files.
        prompt_text: (Optional) Text transcript of the reference audio to improve cloning accuracy.
        effect: (Optional) Name of the post-processing effect to apply (e.g., "Old Radio").
        
    Returns:
        Path to the generated audio file.
    """
    
    # 1. Check for Pre-recorded Sample Match
    try:
        from specialized.voice_samples_map import get_sample_path
        sample_filename = get_sample_path(text)
        
        if sample_filename:
            # Construct absolute path to the sample
            # Assuming agent-runtime mounts ../agents:/app/agents
            sample_path = os.path.join("/app/agents/bmo_voice/voice_samples", sample_filename)
            
            if os.path.exists(sample_path):
                logger.info(f"--- [Voice Cloning] Using Pre-recorded Sample: {sample_filename} ---")
                return sample_path
            else:
                logger.warning(f"--- [Voice Cloning] Sample found in map but file missing: {sample_path} ---")
    except ImportError:
        logger.warning("Could not import voice_samples_map")
    except Exception as e:
        logger.error(f"Error checking voice samples: {e}")

    # Consolidate inputs
    audio_files = []
    
    if reference_audio_paths:
        audio_files.extend(reference_audio_paths)
        
    if reference_audio_path:
        if os.path.isdir(reference_audio_path):
             # Scan directory for audio
             for root, dirs, files in os.walk(reference_audio_path):
                 for file in files:
                     if file.lower().endswith(('.wav', '.mp3', '.flac', '.m4a')):
                         audio_files.append(os.path.join(root, file))
        elif os.path.isfile(reference_audio_path):
             audio_files.append(reference_audio_path)
    
    # Fallback to multi-reference samples if none provided — better cloning quality than single file
    if not audio_files:
        multi = [p for p in DEFAULT_REF_AUDIO_MULTI if os.path.exists(p)]
        if multi:
            logger.info(f"--- [Voice Cloning] Using {len(multi)} multi-reference samples ---")
            audio_files.extend(multi)
        elif os.path.exists(DEFAULT_REF_AUDIO):
            logger.info(f"--- [Voice Cloning] Falling back to single default reference ---")
            audio_files.append(DEFAULT_REF_AUDIO)
    
    logger.info(f"--- [Voice Cloning] Request: '{text}' (Refs: {len(audio_files)}) Effect: {effect} ---")
    
    # 2. Select Engine
    if effect == "BMO":
        url = BMO_ENGINE_URL
    else:
        url = f"{VOICE_ENGINE_HOST}/tts"
    
    try:
        t0 = time.time()
        
        if effect == "BMO" and FISH_AUDIO_API_KEY:
            # --- Fish Audio (Band-Aid) ---
            logger.info(f"Using Fish Audio API (model: {FISH_AUDIO_MODEL_ID})")
            import json
            payload = {
                "text": text,
                "reference_id": FISH_AUDIO_MODEL_ID,
                "format": "wav",
                "latency": "normal",
            }
            headers = {
                "Authorization": f"Bearer {FISH_AUDIO_API_KEY}",
                "Content-Type": "application/json",
            }
            response = requests.post(
                FISH_AUDIO_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
            )
            # Fall back to local RVC if Fish Audio fails (bad key, no credits, etc.)
            if response.status_code != 200:
                logger.warning(f"Fish Audio failed ({response.status_code}): {response.text[:100]}. Falling back to local RVC.")
                response = requests.post(BMO_ENGINE_URL, params={"text": text}, timeout=60)
        elif effect == "BMO":
            # --- Local RVC Engine (no Fish Audio key) ---
            logger.info("Using local RVC engine (no FISH_AUDIO_API_KEY set)")
            response = requests.post(BMO_ENGINE_URL, params={"text": text}, timeout=60)
        else:
            # Generic TTS Engine (/tts) expects form data + file uploads
            data = {"text": text}
            if prompt_text:
                data["prompt_text"] = prompt_text
            if effect:
                data["effect"] = effect
                
            upload_files = []
            opened_files = []
            
            for p in audio_files:
                if os.path.exists(p):
                    f = open(p, "rb")
                    opened_files.append(f)
                    upload_files.append(("reference_audio", (os.path.basename(p), f, "audio/wav")))
                else:
                    logger.warning(f"File not found: {p}")

            response = requests.post(url, data=data, files=upload_files, timeout=60)
            
            # Cleanup opened files
            for f in opened_files:
                f.close()
        
        t1 = time.time()
            
        if response.status_code == 200:
            # Save Output
            filename = f"voice_clone_{uuid.uuid4().hex[:8]}.wav"
            
            # Determine output directory (shared workspace)
            output_dir = "/workspace/delivered_artifacts"
            if not os.path.exists(output_dir):
                # Fallback if /workspace doesn't exist (local dev)
                workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                output_dir = os.path.join(workspace_root, "delivered_artifacts")
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            # 5. standardize for BMO hardware (44.1kHz, 16-bit mono)
            # This helps eliminate the static reported by the user.
            try:
                import soundfile as sf
                import numpy as np
                data, samplerate = sf.read(output_path)
                # If it's stereo, convert to mono
                if len(data.shape) > 1:
                    data = data.mean(axis=1)
                
                # We overwrite the file with a clean 44100Hz 16-bit PCM wav
                # Actually 16kHz is also fine, but 44100 is standard for HDMI
                TARGET_RATE = 44100
                if samplerate != TARGET_RATE:
                    from scipy.signal import resample
                    num_samples = int(len(data) * TARGET_RATE / samplerate)
                    data = resample(data, num_samples)
                
                sf.write(output_path, data, TARGET_RATE, subtype='PCM_16')
            except Exception as resample_err:
                logger.warning(f"Resampling failed/skipped: {resample_err}")
                
            logger.info(f"--- [Voice Cloning] Success: {filename} ({t1-t0:.2f}s) ---")
            return output_path
        else:
            error_msg = f"Voice Engine Error ({response.status_code}): {response.text[:100]}"
            logger.error(error_msg)
            return None  # Don't pass error strings as audio paths
            
    except Exception as e:
        logger.error(f"Connection Failed: {e}")
        return f"Error connecting to Voice Engine: {e}. Is the service running?"

def get_voice_cloning_agent():
    return Agent(
        name="Voice Cloning Expert",
        model=Ollama(id=MODEL_NAME),
        description="I am the Voice Cloning Expert. I can generate speech in any voice using Qwen3-TTS.",
        instructions="You are a voice synthesis specialist. Use `clone_voice` to generate audio. precise and technical.",
        tools=[clone_voice],
        show_tool_calls=True,
    )
