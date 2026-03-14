import os
import sys
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
import openwakeword
from openwakeword.model import Model
import tempfile
import threading
import queue

# --- Configuration ---
WAKE_WORD_MODELS = ["hey_jarvis_v0.1"] 
MIC_DEVICE = None 
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280 
THRESHOLD = 0.5

# --- NETWORK CONFIGURATION ---
# If running on the SAME machine as Docker (e.g. your PC):
# HOST_IP = "localhost"

# If running on Raspberry Pi (Remote):
# Replace with your PC's actual LAN IP (e.g., 192.168.1.100)
HOST_IP = "192.168.1.X" # <--- UPDATE THIS

VOICE_ENGINE_URL = f"http://{HOST_IP}:8020/stt"
AGENT_URL = f"http://{HOST_IP}:8001/v1/voice/chat"

# Audio Playback
def play_audio(file_path):
    try:
        # If running remotely, we need to fetch the audio file first if it's a local path on the server
        # But wait, the Agent returns a path *inside the container*.
        # If we are on a Pi, we can't access "C:\Users\..."
        # We need an endpoint to DOWNLOAD the audio bytes.
        
        # For now, let's assume we just play a beep if remote, 
        # OR we need to update the backend to return audio BYTES or a URL.
        
        # Current implementation assumes Shared File System (Localhost).
        # For Pi support, we really need a /speech/tts endpoint that returns bytes.
        
        # Temporary workaround for Pi:
        if HOST_IP != "localhost" and HOST_IP != "127.0.0.1":
            print(f"⚠️ Remote Playback Not Yet Fully Supported for file: {file_path}")
            print("To fix: We need to expose a file serving endpoint.")
            return

        data, fs = sf.read(file_path)
        sd.play(data, fs)
        sd.wait()
    except Exception as e:
        print(f"Error playing audio: {e}")

# ... (Rest of logic is same, omitting for brevity in this specific tool call, 
# likely better to just Explain this to user first)
