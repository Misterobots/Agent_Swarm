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
import re
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

# Wake word / mic capture — ported from the retired scripts/voice_satellite.py, which
# used to own this; see _wake_word_loop() and record_with_vad() below.
import pvporcupine
import sounddevice as sd
import soundfile as sf

# Import Face Renderer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pygame_face import PygameFace

# Configuration
SAMPLE_RATE = 44100 # For playback/recording logic
BMO_VOICE_URL = "http://{host}:{port}/speak"

# Wake word / mic-capture config — values tuned against the real Pi hardware in
# scripts/voice_satellite.py; carried over as-is.
MIC_SAMPLE_RATE = 16000
POST_INTERACTION_COOLDOWN = 0.5  # brief cooldown after playback to absorb echo
FOLLOWUP_WINDOW = 8.0            # seconds BMO stays in conversation mode after a response
FOLLOWUP_SPEECH_FRAMES = 15      # ~480ms of confirmed speech needed (harder to false-trigger)
SILENCE_GATE_FRAMES = 12         # ~384ms of quiet required BEFORE follow-up speech counts
                                  # TV audio is continuous and never passes this gate;
                                  # conversation speech comes after a pause.
_speech_threshold = 10000        # calibrated at startup in _wake_word_loop(); used by record_with_vad()
SPEAKER_VERIFY_ENABLED = os.getenv("BMO_SPEAKER_VERIFY", "false").lower() == "true"

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bmo_driver")


def _find_ppn_model():
    """Find the Beem-Moe .ppn wake-word model file next to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        for f in os.listdir(script_dir):
            if f.lower().endswith(".ppn"):
                return os.path.join(script_dir, f)
    except Exception:
        pass
    return None


def detect_mic_device():
    """Auto-detect the USB microphone index (sounddevice). Fallback when --input_device isn't given."""
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if ("usb" in name or "plantronics" in name or "blackwire" in name) and dev['max_input_channels'] > 0:
                logger.info(f"🎙️ Auto-detected Mic: Index {i} ({dev['name']})")
                return i
    except Exception as e:
        logger.warning(f"Mic detection failed: {e}")
    logger.warning("⚠️ No USB Mic found, falling back to System Default.")
    return None


def clean_stt_text(text):
    """Remove model tags like <|en|><|Speech|> and filter common blank-audio hallucinations."""
    if not text:
        return ""
    cleaned = re.sub(r"<\|.*?\|>", "", text).strip()
    # Strip non-ASCII (kills Whisper's Korean/Chinese/Russian hallucinations on silence)
    cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned).strip()
    lower_c = cleaned.lower()
    hallucinations = [
        "thank you.", "thanks for watching.", "amara.org", "bye.", "you.", ".",
        "thanks for watching!", "subscribe", "thank you", "thanks", "thanks for watching",
        "hello?", "hello.", "hello", "hi.", "hi", "testing.", "test.", "test", "...",
        ",,,", "www", "okay.", "okay",
    ]
    if lower_c in hallucinations or len(lower_c) <= 2:
        return ""
    return cleaned


def _is_speech_frame(pcm, threshold: int) -> bool:
    """RMS above threshold AND zero-crossing rate in the voiced-speech range — rejects
    continuous TV/music noise (ZCR too high) and low-frequency rumble (ZCR too low)."""
    rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
    if rms < threshold:
        return False
    signs = np.sign(pcm.astype(np.float32))
    signs[signs == 0] = 1
    crossings = int(np.sum(np.abs(np.diff(signs))) // 2)
    return 20 <= crossings <= 350


def record_with_vad(device, sample_rate=16000, frame_size=512,
                     silence_frames_needed=20, max_duration=15.0):
    """Record until silence_frames_needed consecutive quiet frames or max_duration.
    Returns a numpy int16 array, or None if no speech starts within a 3s timeout."""
    buf = queue.Queue()
    collected = []
    speech_started = False
    silent_frames = 0
    total_frames = 0
    speech_frame_count = 0
    max_frames = int(max_duration * sample_rate / frame_size)
    no_speech_timeout_frames = int(3.0 * sample_rate / frame_size)
    min_speech_frames = int(0.3 * sample_rate / frame_size)

    def _cb(indata, frames, time_info, status):
        buf.put(indata.copy())

    try:
        with sd.InputStream(samplerate=sample_rate, blocksize=frame_size,
                             device=device, channels=1, dtype='int16',
                             callback=_cb, latency='high'):
            while total_frames < max_frames:
                try:
                    chunk = buf.get(timeout=0.5)
                except queue.Empty:
                    break

                pcm = chunk.flatten()
                rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                collected.append(pcm)
                total_frames += 1

                if rms > _speech_threshold:
                    speech_started = True
                    silent_frames = 0
                    speech_frame_count += 1
                elif speech_started:
                    silent_frames += 1
                    if silent_frames >= silence_frames_needed and speech_frame_count >= min_speech_frames:
                        logger.info(f"🔇 End of speech ({speech_frame_count * frame_size / sample_rate:.1f}s spoken)")
                        break
                else:
                    if total_frames > no_speech_timeout_frames:
                        return None
    except Exception as e:
        logger.error(f"VAD Error: {e}")
        return None

    if not collected or speech_frame_count < min_speech_frames:
        return None
    return np.concatenate(collected)

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

        # Wake word / mic capture — needs self.loop ready to hand off detected
        # interactions via asyncio.run_coroutine_threadsafe(). Non-fatal if it can't
        # start (missing PICOVOICE_KEY, no .ppn model, etc.) — face + FIFO still work.
        t_wake = threading.Thread(target=self._wake_word_loop, daemon=True)
        t_wake.start()

    def _run_server(self):
        """The actual async loop running in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Initial Expressions
        self.face.set_expression("happy")
        time.sleep(2)
        self.face.set_expression("neutral")

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
                    print("🎤 Recording (VAD — stops on silence)...")
                    device = self.args.input_device if self.args.input_device is not None else detect_mic_device()
                    recording = record_with_vad(device=device, sample_rate=MIC_SAMPLE_RATE)
                    if recording is None:
                        print("⚠️ No speech detected.")
                    else:
                        asyncio.run_coroutine_threadsafe(self.handle_voice_interaction(recording), self.loop)
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
            resp = requests.post(url, params=params, timeout=90)
            t1 = time.time()
            logger.info(f"⏱ HTTP POST: {t1-t0:.1f}s ({len(resp.content)} bytes)")
            if resp.status_code == 200:
                # Unique temp file per response — overlapping interactions (FIFO command +
                # wake word) must not race on a shared filename. play_audio() deletes it;
                # on a write failure we delete it here so it doesn't orphan on disk.
                tmp_name = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, prefix="bmo_response_", suffix=".wav") as f:
                        tmp_name = f.name
                        f.write(resp.content)
                    return tmp_name
                except Exception:
                    if tmp_name:
                        try:
                            os.remove(tmp_name)
                        except Exception:
                            pass
                    raise
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

    def _verify_speaker(self, wav_path: str) -> bool:
        """POST to voice_engine's /verify_speaker. True if recognized or nothing is
        enrolled yet; False only when a profile exists and the speaker doesn't match.
        Fails open on network/service errors so BMO isn't silently broken."""
        url = f"http://{self.args.host}:8020/verify_speaker"
        try:
            with open(wav_path, "rb") as f:
                resp = requests.post(url, files={"audio": (os.path.basename(wav_path), f, "audio/wav")}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("no_profiles"):
                    return True
                accepted = data.get("accepted", False)
                speaker = data.get("matched_speaker") or "unknown"
                logger.info(f"🔐 Speaker: {speaker} score={data.get('score', 0.0):.3f} "
                            f"{'✅ allowed' if accepted else '🚫 rejected'}")
                return accepted
            logger.warning(f"⚠️ Speaker verify returned {resp.status_code} — failing open")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Speaker verify error: {e} — failing open")
            return True

    async def handle_voice_interaction(self, recording) -> bool:
        """Take VAD-recorded audio through STT → bmo_brain → TTS + playback.
        Returns True if BMO's reply sounds like it's inviting a follow-up.
        """
        t0 = time.time()
        self.face.set_expression("listening")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, recording.astype(np.int16), MIC_SAMPLE_RATE)
            temp_path = tmp.name

        try:
            if SPEAKER_VERIFY_ENABLED:
                verified = await self.loop.run_in_executor(None, self._verify_speaker, temp_path)
                if not verified:
                    logger.info("🚫 Unrecognized speaker — ignoring interaction.")
                    self.face.set_expression("neutral")
                    return False

            self.face.set_expression("thinking")
            stt_url = f"http://{self.args.host}:8020/stt"
            try:
                with open(temp_path, 'rb') as f:
                    resp = await self.loop.run_in_executor(
                        None, lambda: requests.post(stt_url, files={'audio_file': (temp_path, f, 'audio/wav')}))
            except Exception as e:
                logger.error(f"STT Request Error: {e}")
                self.face.set_expression("neutral")
                return False

            if resp.status_code != 200:
                logger.error(f"STT Error: {resp.text}")
                self.face.set_expression("neutral")
                return False

            text = clean_stt_text(resp.json().get("text", ""))
            if not text:
                logger.info("No speech detected.")
                self.face.set_expression("neutral")
                return False
            logger.info(f"📝 Transcribed: {text}")

            reply = await self.loop.run_in_executor(None, self.chat, text)
            if not reply:
                logger.error("No reply from bmo_brain.")
                self.face.set_expression("neutral")
                return False

            logger.info(f"⏱ Voice interaction total (pre-TTS): {time.time()-t0:.1f}s")
            await self.handle_text_interaction(reply)
            return "?" in reply or "what do you think" in reply.lower() or "how about" in reply.lower()
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def play_wake_ping(self):
        """Two-tone ascending chime (C6→E6) confirming wake-word detection."""
        try:
            ping_wav = os.path.join(tempfile.gettempdir(), "bmo_wake.wav")
            if not os.path.exists(ping_wav):
                import math
                sample_rate = 44100
                tone_duration, gap_duration = 0.1, 0.03
                n_tone = int(tone_duration * sample_rate)
                n_gap = int(gap_duration * sample_rate)
                freqs = [1047.0, 1319.0]  # C6, E6 — ascending major third
                with wave.open(ping_wav, 'w') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(sample_rate)
                    for fi, freq in enumerate(freqs):
                        for i in range(n_tone):
                            env = min(1.0, i / (n_tone * 0.05)) * max(0.0, 1.0 - (i / n_tone) * 0.5)
                            value = int(32767.0 * 0.25 * env * math.sin(2.0 * math.pi * freq * i / sample_rate))
                            f.writeframesraw(struct.pack('<h', value))
                        if fi < len(freqs) - 1:
                            for _ in range(n_gap):
                                f.writeframesraw(struct.pack('<h', 0))

            cmd_prefix = ["aplay"]
            alsa_dev = self._get_aplay_device()
            if alsa_dev:
                cmd_prefix = ["aplay", "-D", alsa_dev]
            self._wake_hdmi(alsa_dev)
            subprocess.run(cmd_prefix + [ping_wav], check=False, capture_output=True)
        except Exception as e:
            logger.error(f"Wake Ping Error: {e}")

    def _wake_hdmi(self, alsa_dev):
        """Play brief silence first — sleeping HDMI receivers drop the start of the
        next clip otherwise. No-op cost is ~1.2s; only called right before real audio."""
        try:
            silence_path = os.path.join(tempfile.gettempdir(), "bmo_silence.wav")
            if not os.path.exists(silence_path):
                with wave.open(silence_path, 'w') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(44100)
                    f.writeframesraw(b"\x00\x00" * int(1.2 * 44100))
            cmd = ["aplay", silence_path] if not alsa_dev else ["aplay", "-D", alsa_dev, silence_path]
            subprocess.run(cmd, check=False, capture_output=True)
        except Exception as e:
            logger.debug(f"HDMI wake silence skipped: {e}")

    def _wake_word_loop(self):
        """Listen for the "Beemo" wake word (Porcupine) and hand detected interactions
        off to handle_voice_interaction() on the async loop. Ported from the retired
        scripts/voice_satellite.py — calibration/threshold formulas and hardware
        workarounds (mic gain, attenuation) are tuned against this specific Pi and
        carried over unchanged. Non-fatal on any init failure: logs and returns,
        leaving face display + FIFO control still working.
        """
        access_key = os.getenv("PICOVOICE_KEY", "")
        if not access_key:
            logger.error("❌ PICOVOICE_KEY not set — wake word disabled (face/FIFO still work).")
            return
        ppn_path = _find_ppn_model()
        if not ppn_path:
            logger.error("❌ No .ppn wake word model file found — wake word disabled.")
            return

        try:
            porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[ppn_path], sensitivities=[0.65])
        except Exception as e:
            logger.error(f"❌ Failed to initialize Porcupine: {e} — wake word disabled.")
            return

        global _speech_threshold
        FRAME_LENGTH = porcupine.frame_length
        HARDWARE_RATE = MIC_SAMPLE_RATE
        HARDWARE_CHUNK = FRAME_LENGTH
        logger.info(f"✅ Porcupine ready. frame_length={FRAME_LENGTH}, hw_rate={HARDWARE_RATE}")

        MIC_DEVICE = self.args.input_device if self.args.input_device is not None else detect_mic_device()

        # This USB codec resets capture gain to max every time the device is opened.
        try:
            subprocess.run(["amixer", "-c", "2", "sset", "Mic", "35", "cap"], capture_output=True, check=False)
        except Exception as e:
            logger.warning(f"⚠️ Could not set mic gain: {e}")

        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())

        SPEECH_THRESHOLD = 10000
        logger.info("📏 Calibrating ambient noise floor — please stay quiet for 3 seconds...")
        _cal_rms_samples = []
        try:
            def _cal_callback(indata, frames, time_info, status):
                _cal_rms_samples.append(int(np.sqrt(np.mean(indata.astype(np.float32) ** 2))))
            with sd.InputStream(samplerate=HARDWARE_RATE, blocksize=HARDWARE_CHUNK, device=MIC_DEVICE,
                                 channels=1, callback=_cal_callback, dtype='int16', latency='high'):
                time.sleep(3.0)
        except Exception as e:
            logger.warning(f"⚠️ Calibration failed: {e} — using default threshold {SPEECH_THRESHOLD}")
            _cal_rms_samples = []

        if _cal_rms_samples:
            ambient_mean = int(np.mean(_cal_rms_samples))
            ambient_std = int(np.std(_cal_rms_samples))
            SPEECH_THRESHOLD = min(max(int(ambient_mean + 2.0 * ambient_std), 5000), 30000)
            _speech_threshold = SPEECH_THRESHOLD
            logger.info(f"📏 Ambient RMS: mean={ambient_mean}, std={ambient_std} → SPEECH_THRESHOLD={SPEECH_THRESHOLD}")

        logger.info("🎙️ Wake Word: 'Beemo' (Porcupine custom model)")
        self.face.set_expression("neutral")

        followup_until = 0.0
        silence_gate = 0
        speech_frames = 0
        last_heartbeat = time.time()

        while self.running:
            interacted = False
            try:
                with sd.InputStream(samplerate=HARDWARE_RATE, blocksize=HARDWARE_CHUNK, device=MIC_DEVICE,
                                     channels=1, callback=callback, dtype='int16', latency='high'):
                    while not interacted and self.running:
                        if time.time() - last_heartbeat > 30:
                            logger.debug(f"wake-word thread alive. Q={audio_queue.qsize()}")
                            last_heartbeat = time.time()
                        try:
                            chunk = audio_queue.get(timeout=0.05)
                            while audio_queue.qsize() > 1:
                                audio_queue.get_nowait()
                            pcm = chunk.flatten()
                            rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                            self.face.set_mic_rms(rms)

                            # Attenuate to 25% — mic AGC saturates near int16 max regardless of
                            # room volume; this brings levels back into Porcupine's trained range.
                            pcm_ppn = (pcm.astype(np.float32) * 0.25).clip(-32768, 32767).astype(np.int16)
                            detected = False
                            for i in range(0, len(pcm_ppn) - FRAME_LENGTH + 1, FRAME_LENGTH):
                                if porcupine.process(pcm_ppn[i:i + FRAME_LENGTH]) >= 0:
                                    detected = True
                                    break

                            if detected:
                                logger.info("⚡ Wake Word Detected: Beemo!")
                                speech_frames = 0
                                self.face.set_expression("acknowledged")
                                self.play_wake_ping()
                                self.face.set_expression("listening")
                                interacted = True
                            elif followup_until > time.time():
                                if rms < SPEECH_THRESHOLD:
                                    silence_gate = min(silence_gate + 1, SILENCE_GATE_FRAMES + 1)
                                    speech_frames = 0
                                elif silence_gate >= SILENCE_GATE_FRAMES:
                                    if _is_speech_frame(pcm, SPEECH_THRESHOLD):
                                        speech_frames += 1
                                        if speech_frames >= FOLLOWUP_SPEECH_FRAMES:
                                            logger.info("💬 Follow-up speech detected")
                                            speech_frames = 0
                                            silence_gate = 0
                                            self.face.set_expression("acknowledged")
                                            interacted = True
                                    else:
                                        speech_frames = 0
                                else:
                                    speech_frames = 0
                            else:
                                silence_gate = 0
                                speech_frames = 0
                        except queue.Empty:
                            pass
            except Exception as e:
                logger.error(f"Wake-word stream error: {e}")
                time.sleep(2)
                continue

            if interacted:
                time.sleep(0.3)  # let the listener stream release the hardware
                recording = record_with_vad(device=MIC_DEVICE, sample_rate=HARDWARE_RATE)
                if recording is None:
                    logger.info("⚠️ No speech detected — skipping.")
                    self.face.set_expression("neutral")
                else:
                    fut = asyncio.run_coroutine_threadsafe(self.handle_voice_interaction(recording), self.loop)
                    try:
                        wants_followup = fut.result(timeout=120)
                    except Exception as e:
                        logger.error(f"Voice interaction error: {e}")
                        wants_followup = False
                    followup_until = time.time() + FOLLOWUP_WINDOW if wants_followup else followup_until
                time.sleep(POST_INTERACTION_COOLDOWN)

        porcupine.delete()

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
        """Play audio using aplay (subprocess.run) — safest method. Deletes the file after."""
        try:
            cmd = ["aplay", filename]
            alsa_dev = self._get_aplay_device()
            if alsa_dev:
                cmd = ["aplay", "-D", alsa_dev, filename]

            # Sleeping HDMI receivers drop the first ~second of a clip otherwise.
            self._wake_hdmi(alsa_dev)

            logger.info(f"Playing: {' '.join(cmd)}")

            # Timeout from the WAV's actual duration — a fixed 10s cut off any answer
            # longer than ten seconds mid-playback.
            timeout = 30
            try:
                with wave.open(filename, "rb") as w:
                    timeout = max(30, w.getnframes() / w.getframerate() + 10)
            except Exception:
                pass

            # Use subprocess.run with timeout and DEVNULL to prevent hangs
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False
            )

        except subprocess.TimeoutExpired:
            logger.error("Audio Playback Timeout!")
        except Exception as e:
            logger.error(f"Audio Error: {e}")
        finally:
            try:
                os.remove(filename)
            except Exception:
                pass

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
