"""
BMO Driver (Raspberry Pi Edition)

Manages the Face display (pygame), audio playback (aplay), and voice interaction.
- Runs a native pygame face renderer (no browser needed).
- Manages audio recording and playback via ALSA.
- Syncs face state (Listening, Thinking, Speaking) with actions.

Usage:
  python bmo_driver.py --host <HIVE_IP> --output_device <ALSA_CARD>
"""

import asyncio
import logging
import argparse
import sys
import os
import requests
import json
import pygame # For Native Mixer Playback
import threading
import queue
import time
import subprocess
import wave
import struct
import tempfile
from dotenv import load_dotenv

# Load .env from the script's directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Audio Libs
try:
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: numpy missing ({e})")
    AUDIO_AVAILABLE = False

# Wake Word and STT migrated to voice_satellite.py

# Import Face Renderer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pygame_face import PygameFace

# Configuration
SAMPLE_RATE = 44100 # For playback/recording logic
BMO_VOICE_URL = "http://{host}:{port}/speak"

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bmo_driver")

class BMODriver:
    def __init__(self, args):
        self.args = args
        self.face = PygameFace()
        self.loop = None # Will be set in the server thread
        self.running = True
        
    def start_server_thread(self):
        """Start the Face Server in a separate thread."""
        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        
        # Start Command Listener (SSH/FIFO)
        t_cmd = threading.Thread(target=self._command_fifo_thread, daemon=True)
        t_cmd.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.1)
        logger.info("Server Thread Started")

    def _run_server(self):
        """The actual async loop running in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Initial Expressions
        self.face.set_expression("happy")
        time.sleep(2)
        self.face.set_expression("neutral")
        
        # Start Wake Word logic is now handled by voice_satellite.py
        
        # Run forever (needed for async coroutine scheduling)
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()

    def input_loop(self):
        """Main Blocking Input Loop."""
        # Check if running as a service (no TTY)
        # Check if running as a service (no TTY)
        if not sys.stdin or not sys.stdin.isatty():
            logger.info("Service Mode: No interactive TTY. Entering wait loop.")
            while self.running:
                time.sleep(1)
            return

        print("\n🎮 BMO Interactive Mode (Voice + Text)")
        print("Type 'talk' to record voice, or type a message to send directly.")
        print("Type 'exit' to quit.\n")
        
        while self.running:
            try:
                cmd = input("BMO> ").strip()
                if not cmd: continue
                
                if cmd == "exit":
                    self.running = False
                    # Signal the async loop to stop if it's running run_forever
                    if self.loop and self.loop.is_running():
                        self.loop.call_soon_threadsafe(self.loop.stop)
                    break
                
                if cmd == "talk":
                    logger.warning("Mic input migrated to voice_satellite.py! Say 'Hey Beemo' instead.")
                else:
                    # Text input
                    asyncio.run_coroutine_threadsafe(self.handle_text_interaction(cmd), self.loop)
                    
            except EOFError:
                self.running = False
                if self.loop and self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                break
            except KeyboardInterrupt:
                self.running = False
                if self.loop and self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                break
            except Exception as e:
                logger.error(f"Input Error: {e}")



    async def handle_text_interaction(self, text):
        """Send text to server, play response."""
        t0 = time.time()
        logger.info(f"Processing text: {text}")
        try:
            self.face.set_expression("thinking")
        except Exception as e:
            logger.error(f"Face Error: {e}")
            
        # 1. Detect Emotion from INPUT (optional, mostly we care about OUTPUT emotion)
        # But here we process the response *text* which we don't have yet if it's chat.
        # Wait, if this is 'say:' command, 'text' IS the output.
        # If this is chat input, the response comes from Hive.
        
        # If text is a direct command (via input loop), we might want to analyze it.
        # But actually, usually we analyze the RESPONSE.
        
        # Let's see: this method seems to be used for BOTH direct chat input via keyboard
        # AND via fifo 'say:' (which calls _say_only).
        
        # Wait, handle_text_interaction calls send_text_request which gets audio back.
        # If 'text' is user input, we shouldn't speak it back?
        # Aah, Looking at line 256: sends 'text' to 'send_text_request'.
        # This implies 'handle_text_interaction' is actually 'handle_tts_request' or 'say_this'.
        # Let's check where it's called.
        # Line 142 (input loop): calls handle_text_interaction(cmd) -> likely meant to chat? 
        # But the code inside calls `send_text_request(text)` which hits `/speak` (TTS).
        # So `handle_text_interaction` currently makes BMO **repeat** what you type?
        # Or does it chat?
        # Line 312 (send_audio_request) calls send_text_request(response_text).
        
        # Steps inside `handle_text_interaction`:
        # 1. Shows "thinking"
        # 2. Calls `send_text_request(text)` -> TTS
        # 3. Plays audio.
        
        # So YES, `handle_text_interaction` is basically "Speech Synthesis + Animation".
        # So we SHOULD analyze `text` here.
        
        emotion, pitch_off, speed_fac = self.detect_emotion(text)
        logger.info(f"🎭 Emotion: {emotion} (p={pitch_off}, s={speed_fac})")

        # Send TTS request with emotion params
        t1 = time.time()
        response_audio = await self.loop.run_in_executor(None, self.send_text_request, text, pitch_off, speed_fac)
        t2 = time.time()
        logger.info(f"⏱ TTS Response: {t2-t1:.1f}s")
        
        if response_audio:
            try:
                logger.info(f"Speaking ({emotion})...")
                # Extract mouth sync data from the audio file
                mouth_sync = self.extract_mouth_sync_from_wav(response_audio)
                
                # Use emotional speaking face with mouth sync
                if emotion == "neutral":
                    self.face.set_expression("speaking", mouth_sync)
                else:
                    self.face.set_expression(f"{emotion}_speaking", mouth_sync)
                    
                await self.loop.run_in_executor(None, self.play_audio, response_audio)
                logger.info(f"⏱ Total: {time.time()-t0:.1f}s")
            finally:
                # Always return to neutral
                self.face.set_expression("neutral")
        else:
            logger.error("No audio response received.")
            self.face.set_expression("error")



    def chat(self, text, hive_port=8000):
        """Chat with Hive Swarm."""
        url = f"http://{self.args.host}:{hive_port}/v1/chat/completions"
        payload = {
            "model": "default",
            "messages": [{"role": "user", "content": text}]
        }
        try:
            t0 = time.time()
            resp = requests.post(url, json=payload, timeout=60)
            logger.info(f"⏱ Brain: {time.time()-t0:.1f}s")
            
            if resp.status_code == 200:
                data = resp.json()
                # OpenAI format
                content = data["choices"][0]["message"]["content"]
                logger.info(f"🧠 Brain: '{content}'")
                return content
            else:
                logger.error(f"Hive Chat Error: {resp.text}")
        except Exception as e:
            logger.error(f"Hive Chat Connection Error: {e}")
        return None

    def send_text_request(self, text, pitch_offset=0, speed=1.0):
        """Send text to BMO Voice TTS."""
        url = BMO_VOICE_URL.format(host=self.args.host, port=self.args.port)
        
        # Phonetics formatting for BMO's name
        text = text.replace("BMO", "Beemo").replace("bmo", "beemo").replace("Bmo", "Beemo")

        # Base pitch + offset
        final_pitch = self.args.pitch + pitch_offset
        
        params = {
            "text": text,
            "pitch": final_pitch,
            "speed": speed,
            "method": self.args.method
        }
        
        try:
            t0 = time.time()
            resp = requests.post(url, params=params, timeout=10)
            t1 = time.time()
            logger.info(f"⏱ HTTP POST: {t1-t0:.1f}s ({len(resp.content)} bytes)")
            if resp.status_code == 200:
                filename = "bmo_response.wav"
                with open(filename, "wb") as f:
                    f.write(resp.content)
                return filename
            else:
                logger.error(f"Server Error: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            return None

    def _get_aplay_device(self):
        """Get the ALSA device string for aplay."""
        dev = self.args.output_device
        if dev is not None:
            # If it's a digit, assume it's a card index -> plughw:X,0
            if dev.isdigit():
                return f"plughw:{dev},0"
            # Otherwise, assume it's a named device (e.g., "bmo_softvol")
            return dev
        return None  # Use system default

    async def _say_only(self, text):
        """Speak text without LLM processing (Direct TTS)."""
        logger.info(f"Saying: {text}")
        emotion, pitch_off, speed_fac = self.detect_emotion(text)
        
        try:
            logger.info(f"🎭 Say Emotion: {emotion}")
            resp = await self.loop.run_in_executor(None, self.send_text_request, text, pitch_off, speed_fac)
            if resp:
                # Extract mouth sync from audio
                mouth_sync = self.extract_mouth_sync_from_wav(resp)
                if emotion == "neutral":
                    self.face.set_expression("speaking", mouth_sync)
                else:
                    self.face.set_expression(f"{emotion}_speaking", mouth_sync)
                await self.loop.run_in_executor(None, self.play_audio, resp)
        except Exception as e:
            logger.error(f"Say Error: {e}")
        finally:
            self.face.set_expression("neutral")

    def _command_fifo_thread(self):
        """Listen for commands on a named pipe (e.g. echo 'say:Hello' > /tmp/bmo_cmd.fifo)."""
        fifo_path = "/tmp/bmo_cmd.fifo"
        if os.path.exists(fifo_path):
            os.remove(fifo_path)
        try:
            os.mkfifo(fifo_path)
            os.chmod(fifo_path, 0o666)
        except Exception as e:
            logger.error(f"Failed to create FIFO: {e}")
            return

        logger.info(f"🐚 Command Listener ready: {fifo_path}")
        
        while self.running:
            try:
                # Open blocks until a writer connects
                with open(fifo_path, "r") as f:
                    for line in f:
                        cmd = line.strip()
                        if cmd:
                            self._handle_external_command(cmd)
            except Exception as e:
                logger.error(f"FIFO Error: {e}")
                time.sleep(1)
        
        if os.path.exists(fifo_path):
            os.remove(fifo_path)

    def _handle_external_command(self, cmd):
        logger.info(f"🐚 Command: {cmd}")
        if self.loop is None: return

        if cmd.startswith("say:"):
            text = cmd[4:].strip()
            asyncio.run_coroutine_threadsafe(self._say_only(text), self.loop)
        elif cmd.startswith("face:"):
            expression = cmd[5:].strip()
            logger.info(f"🎭 External Face CMD: {expression}")
            self.face.set_expression(expression)
        elif cmd.startswith("rms:"):
            try:
                self.face.set_mic_rms(int(cmd[4:].strip()))
            except (ValueError, AttributeError):
                pass
        else:
            # Treat as chat input
            asyncio.run_coroutine_threadsafe(self.handle_text_interaction(cmd), self.loop)

    def set_volume(self, volume_percent):
        """Set volume for the specific output device using amixer."""
        if volume_percent is None:
            return

        # Determine Card Index
        card_index = 0
        dev = self.args.output_device
        if dev and dev.isdigit():
            card_index = int(dev)
        elif dev == "bmo_softvol":
            card_index = 1 # We hardcoded card 1 in asoundrc.example

        logger.info(f"🔊 Setting Volume to {volume_percent}% on Card {card_index}...")
        
        # Heuristic: Try common control names
        controls = ["BMOVolume", "PCM", "Speaker", "Master", "Headphone", "Playback", "HDMI", "Digital"]
        
        # 1. Try to find a valid control
        valid_control = None
        for control in controls:
            # Check if control exists
            check_cmd = ["amixer", "-c", str(card_index), "get", control]
            res = subprocess.run(check_cmd, capture_output=True, text=True)
            if res.returncode == 0:
                valid_control = control
                break
        
        if valid_control:
            cmd = ["amixer", "-c", str(card_index), "set", valid_control, f"{volume_percent}%"]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"✅ Volume set to {volume_percent}% on control '{valid_control}'")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to set volume: {e}")
        else:
            logger.warning(f"⚠️ Could not find a valid mixer control for Card {card_index}. Volume not set.")
            # Fallback: List controls for debugging
            subprocess.run(["amixer", "-c", str(card_index), "scontrols"])

    def run_sound_check(self):
        """Play a startup beep to verify speaker using aplay."""
        logger.info("🎵 Performing Sound Check...")
        try:
            # Generate a 0.5s 440Hz beep as a WAV file
            fs = 48000
            duration = 0.5
            n_samples = int(fs * duration)
            
            beep_path = os.path.join(tempfile.gettempdir(), "bmo_beep.wav")
            with wave.open(beep_path, 'w') as wf:
                wf.setnchannels(2)  # Stereo for HDMI
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(fs)
                # Vectorized generation (fast on Pi vs per-sample loop)
                t = np.arange(n_samples)
                samples = (0.3 * 32767 * np.sin(2 * np.pi * 440 * t / fs)).astype(np.int16)
                # Interleave L+R channels
                stereo = np.column_stack((samples, samples)).flatten()
                wf.writeframes(stereo.tobytes())
            
            # Play with aplay
            cmd = ["aplay", beep_path]
            alsa_dev = self._get_aplay_device()
            if alsa_dev:
                cmd = ["aplay", "-D", alsa_dev, beep_path]
                
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info("✅ Sound Check Complete (Did you hear a beep?)")
            else:
                logger.error(f"Sound Check Failed: {result.stderr}")
                
            os.remove(beep_path)
        except Exception as e:
            logger.error(f"Sound Check Error: {e}")

    def play_audio(self, filename):
        """Play audio using aplay (subprocess.run) — safest method."""
        try:
            cmd = ["aplay", filename]
            alsa_dev = self._get_aplay_device()
            if alsa_dev:
                cmd = ["aplay", "-D", alsa_dev, filename]
            
            logger.info(f"Playing: {' '.join(cmd)}")
            
            # Use subprocess.run with timeout and DEVNULL to prevent hangs
            subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                timeout=10, 
                check=False
            )
                 
        except subprocess.TimeoutExpired:
            logger.error("Audio Playback Timeout!")
        except Exception as e:
            logger.error(f"Audio Error: {e}")

    def detect_emotion(self, text):
        """
        Simple keyword-based emotion detection.
        Returns: (emotion_name, pitch_offset, speed_factor)
        """
        text = text.lower()
        
        # 1. Excited / Happy
        if "!" in text or any(w in text for w in ["excited", "yay", "awesome", "great", "love", "happy", "yes!"]):
            if "!" in text:
                return "excited", 6, 1.3 # Super fast, super high (BMO squeak)
            return "happy", 3, 1.15

        # 2. Sad / Apologetic
        if any(w in text for w in ["sad", "sorry", "unfortunately", "bad news", "miss", "tired", "no..."]):
            return "sad", -5, 0.7  # Very slow, very deep/sad

        # 3. Surprised
        if any(w in text for w in ["whoa", "wow", "oh my", "gasp", "no way"]):
            return "surprised", 5, 1.2
            
        # 4. Sleeping
        if any(w in text for w in ["yawn", "sleep", "bedtime", "nap", "dream", "tired ", "sleepy"]):
            return "sleeping", -6, 0.6

        # 5. Thinking / Questioning
        if "?" in text or any(w in text for w in ["hmm", "wonder", "think", "what if", "wait"]):
            return "thinking", 0, 0.9

        # 6. Confused / Error
        if any(w in text for w in ["error", "confused", "weird", "broken", "fail"]):
            return "error", -2, 0.85

        # Default
        return "neutral", 0, 1.0

    def extract_mouth_sync_from_wav(self, wav_path):
        """Extract amplitude envelope from a WAV file for mouth animation.
        
        Returns a list of normalized amplitude values (0.0-1.0), one per ~50ms window,
        that the pygame face can use to animate the mouth in sync with speech.
        """
        try:
            with wave.open(wav_path, 'r') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                
                raw = wf.readframes(n_frames)
            
            # Convert raw bytes to numpy array
            if sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            else:
                logger.warning(f"Unsupported sample width {sampwidth}, skipping mouth sync")
                return None
            
            samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
            
            # If stereo, take only first channel
            if n_channels > 1:
                samples = samples[::n_channels]
            
            # Window size: ~50ms worth of samples
            window_size = int(framerate * 0.05)
            if window_size < 1:
                return None
            
            # Calculate RMS amplitude per window
            n_windows = len(samples) // window_size
            if n_windows < 1:
                return None
                
            amplitudes = []
            for i in range(n_windows):
                chunk = samples[i * window_size : (i + 1) * window_size]
                rms = np.sqrt(np.mean(chunk ** 2))
                amplitudes.append(rms)
            
            # Normalize to 0.0-1.0
            max_amp = max(amplitudes) if amplitudes else 1.0
            if max_amp > 0:
                amplitudes = [a / max_amp for a in amplitudes]
            
            logger.info(f"👄 Mouth sync: {len(amplitudes)} frames from {wav_path}")
            return amplitudes
            
        except Exception as e:
            logger.error(f"Mouth sync extraction failed: {e}")
            return None

    def list_audio_devices(self):
        """Print ALSA audio device info."""
        print("\n🔊 ALSA Playback Devices:")
        try:
            result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
            print(result.stdout if result.stdout else "  (none found)")
        except Exception as e:
            print(f"  Could not run aplay -l: {e}")
        
        print("🎤 ALSA Capture Devices:")
        try:
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
            print(result.stdout if result.stdout else "  (none found)")
        except Exception as e:
            print(f"  Could not run arecord -l: {e}")
        print("")

def main():
    parser = argparse.ArgumentParser(description="BMO Driver (Face + Voice)")
    parser.add_argument("--host", required=True, help="IP of Hive Server")
    parser.add_argument("--port", default="8100", help="Port of BMO Service")
    
    # Audio Devices
    parser.add_argument("--input_device", type=int, default=None, help="Microphone Device ID")
    parser.add_argument("--output_device", type=str, default=None, help="Speaker Device ID (int) or Name (str)")
    
    parser.add_argument("--volume", type=int, default=None, help="Volume Level (0-100)")
    parser.add_argument("--duration", type=int, default=5, help="Recording Duration")
    parser.add_argument("--pitch", type=int, default=3, help="Pitch")
    parser.add_argument("--method", default="rmvpe", help="RVC Method")
    
    
    args = parser.parse_args()
    
    driver = BMODriver(args)
    driver.list_audio_devices() # Show list on startup
    if args.volume is not None:
        driver.set_volume(args.volume)
        
    driver.run_sound_check()    # Beep
    
    driver.face.start()         # Start pygame face (background thread)
    driver.start_server_thread() # Start async loop for interactions
    driver.input_loop()

if __name__ == "__main__":
    main()
