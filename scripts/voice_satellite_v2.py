"""
BMO Voice Satellite v2 — Conversational Voice Pipeline

State machine with:
  IDLE → WAKE_DETECTED → LISTENING → PROCESSING → SPEAKING → IDLE

Key improvements over v1 (voice_satellite.py):
  - VAD-based recording (Silero VAD) instead of fixed-duration
  - Barge-in: interrupt BMO while speaking to re-enter LISTENING
  - Continuous conversation: BMO stays in LISTENING after asking a question
  - Session lifecycle: calls /v1/voice/new_session on start,
    /v1/voice/end_session after inactivity timeout
  - Face expression synced to each state transition

Requires: openwakeword, sounddevice, numpy, requests, torch (for Silero VAD)
"""

import os
import sys
import time
import re
import math
import wave
import struct
import queue
import socket
import tempfile
import threading
import subprocess
from enum import Enum, auto
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WAKE_WORD_MODELS = ["hey_beeMo"]
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280            # 80ms at 16kHz
WAKE_THRESHOLD = 0.5

# VAD settings
VAD_SILENCE_TIMEOUT = 1.5    # Seconds of silence to stop recording
VAD_MAX_DURATION = 15.0      # Hard cap on recording length
VAD_MIN_SPEECH = 0.3         # Minimum speech duration to count as valid

# Conversation settings
CONVERSATION_TIMEOUT = 30.0  # Seconds of idle before ending session
SESSION_INACTIVITY = 300.0   # Seconds before auto-ending session (5 min)

# Network
_script_dir = os.path.dirname(os.path.abspath(__file__))
for _candidate in [os.path.join(_script_dir, "..", "network.env"),
                   os.path.join(_script_dir, "network.env")]:
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break

HOST_IP = os.getenv("EXECUTION_NODE_IP", os.getenv("JUSTIN_PC_IP", os.getenv("BMO_HOST_IP", "")))
if not HOST_IP:
    print("ERROR: HOST_IP not set. Set EXECUTION_NODE_IP in network.env.")
    sys.exit(1)

VOICE_ENGINE_URL = f"http://{HOST_IP}:8020/stt"
AGENT_URL = f"http://{HOST_IP}:8008/v1/voice/chat"
AGENT_SESSION_URL = f"http://{HOST_IP}:8008/v1/voice"
STREAM_URL = f"http://{HOST_IP}:8008/v1/voice/stream"

# Face sync
BMO_FIFO = "/tmp/bmo_cmd.fifo"
face_queue = queue.Queue()
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

class BMOState(Enum):
    IDLE = auto()
    WAKE_DETECTED = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()


class StateMachine:
    """Thread-safe state machine for BMO voice satellite."""

    def __init__(self):
        self._state = BMOState.IDLE
        self._lock = threading.Lock()
        self._listeners = []

    @property
    def state(self) -> BMOState:
        with self._lock:
            return self._state

    def transition(self, new_state: BMOState) -> bool:
        """Transition to new state. Returns True if transition was valid."""
        valid = {
            BMOState.IDLE: {BMOState.WAKE_DETECTED},
            BMOState.WAKE_DETECTED: {BMOState.LISTENING, BMOState.IDLE},
            BMOState.LISTENING: {BMOState.PROCESSING, BMOState.IDLE},
            BMOState.PROCESSING: {BMOState.SPEAKING, BMOState.LISTENING, BMOState.IDLE},
            BMOState.SPEAKING: {BMOState.LISTENING, BMOState.IDLE},
        }
        with self._lock:
            if new_state in valid.get(self._state, set()):
                old = self._state
                self._state = new_state
                print(f"  [{old.name}] -> [{new_state.name}]")
                for cb in self._listeners:
                    try:
                        cb(old, new_state)
                    except Exception:
                        pass
                return True
            return False

    def force(self, new_state: BMOState):
        """Force state (for barge-in / error recovery)."""
        with self._lock:
            old = self._state
            self._state = new_state
            print(f"  [{old.name}] => [{new_state.name}] (FORCED)")
            for cb in self._listeners:
                try:
                    cb(old, new_state)
                except Exception:
                    pass

    def on_change(self, callback):
        self._listeners.append(callback)


# ---------------------------------------------------------------------------
# Face Sync
# ---------------------------------------------------------------------------

_STATE_FACES = {
    BMOState.IDLE: "neutral",
    BMOState.WAKE_DETECTED: "acknowledged",
    BMOState.LISTENING: "listening",
    BMOState.PROCESSING: "thinking",
    BMOState.SPEAKING: "speaking",
}


def update_face(expression: str):
    face_queue.put(expression)
    try:
        udp_sock.sendto(f"BMO_STATE:{expression}".encode(), (HOST_IP, 8123))
    except Exception:
        pass


def face_worker():
    while True:
        expression = face_queue.get()
        try:
            if os.path.exists(BMO_FIFO):
                with open(BMO_FIFO, "w") as f:
                    f.write(f"face:{expression}\n")
                    f.flush()
        except Exception as e:
            print(f"Face error: {e}")
        face_queue.task_done()


def sync_face_to_state(_old: BMOState, new: BMOState):
    face = _STATE_FACES.get(new, "neutral")
    update_face(face)


# ---------------------------------------------------------------------------
# Audio Utilities (from v1, refined)
# ---------------------------------------------------------------------------

def detect_hdmi_device() -> str:
    try:
        result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "hdmi" in line.lower() or "vc4" in line.lower():
                card = re.search(r"card\s+(\d+)", line)
                dev = re.search(r"device\s+(\d+)", line)
                if card:
                    return f"plughw:{card.group(1)},{dev.group(1) if dev else '0'}"
    except Exception:
        pass
    return "default"


def detect_mic_device() -> Optional[int]:
    try:
        for i, dev in enumerate(sd.query_devices()):
            name = dev["name"].lower()
            if ("usb" in name or "plantronics" in name or "blackwire" in name) and dev["max_input_channels"] > 0:
                print(f"Mic: Index {i} ({dev['name']})")
                return i
    except Exception:
        pass
    return None


def generate_silence(duration=1.2) -> str:
    path = os.path.join(tempfile.gettempdir(), "silence.wav")
    if not os.path.exists(path):
        with wave.open(path, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b"\x00\x00" * int(44100 * duration))
    return path


def play_wake_ping():
    try:
        ping_wav = os.path.join(tempfile.gettempdir(), "bmo_wake.wav")
        if not os.path.exists(ping_wav):
            sr = 44100
            freqs = [1047.0, 1319.0]
            with wave.open(ping_wav, "w") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sr)
                for fi, freq in enumerate(freqs):
                    for i in range(int(0.1 * sr)):
                        env = min(1.0, i / (0.1 * sr * 0.05)) * max(0.0, 1.0 - i / (0.1 * sr) * 0.5)
                        val = int(32767 * 0.25 * env * math.sin(2 * math.pi * freq * i / sr))
                        f.writeframesraw(struct.pack("<h", val))
                    if fi < len(freqs) - 1:
                        f.writeframesraw(b"\x00\x00" * int(0.03 * sr))
        dev = detect_hdmi_device()
        subprocess.run(["aplay", "-D", dev, ping_wav], capture_output=True, check=False)
    except Exception as e:
        print(f"Wake ping error: {e}")


_barge_in_flag = threading.Event()
_playback_process: Optional[subprocess.Popen] = None


def play_audio(file_path: str, face_cmd: str = "speaking"):
    """Play audio with barge-in support. Sets _barge_in_flag if interrupted."""
    global _playback_process
    _barge_in_flag.clear()

    try:
        filename = os.path.basename(file_path)
        local_tmp = os.path.join(tempfile.gettempdir(), filename)

        if not os.path.exists(file_path):
            # Download from agent-runtime
            if "voice_samples" in file_path:
                url = f"http://{HOST_IP}:8008/voice_samples/{filename}"
            else:
                url = f"http://{HOST_IP}:8008/delivered_artifacts/{filename}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(local_tmp, "wb") as f:
                    f.write(r.content)
                file_path = local_tmp
            else:
                print(f"Download failed: {r.status_code}")
                return

        dev = detect_hdmi_device()
        # Wake HDMI
        subprocess.run(["aplay", "-D", dev, generate_silence()], capture_output=True, check=False)

        if face_cmd:
            update_face(face_cmd)

        # Start playback as a Popen so we can kill it for barge-in
        _playback_process = subprocess.Popen(
            ["aplay", "-D", dev, file_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _playback_process.wait()
        _playback_process = None

        if local_tmp == file_path and os.path.exists(local_tmp):
            os.remove(local_tmp)

    except Exception as e:
        print(f"Playback error: {e}")
        _playback_process = None


def interrupt_playback():
    """Kill current audio playback (barge-in)."""
    global _playback_process
    if _playback_process and _playback_process.poll() is None:
        _playback_process.terminate()
        _playback_process = None
        _barge_in_flag.set()
        print("Barge-in: playback interrupted")
        return True
    return False


# ---------------------------------------------------------------------------
# Silero VAD
# ---------------------------------------------------------------------------

_vad_model = None


def _load_vad():
    global _vad_model
    if _vad_model is None:
        import torch
        _vad_model, _ = torch.hub.load(
            "snakers4/silero-vad", "silero_vad",
            force_reload=False, onnx=True,
        )
        print("Silero VAD loaded")
    return _vad_model


def vad_is_speech(audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
    """Check if an audio chunk contains speech using Silero VAD."""
    import torch
    model = _load_vad()
    tensor = torch.from_numpy(audio_chunk.astype(np.float32) / 32768.0)
    if tensor.dim() > 1:
        tensor = tensor.squeeze()
    prob = model(tensor, sample_rate).item()
    return prob > 0.5


# ---------------------------------------------------------------------------
# VAD-Based Recording
# ---------------------------------------------------------------------------

def record_with_vad(mic_device: Optional[int], state_machine: StateMachine) -> Optional[str]:
    """
    Record audio using VAD to detect speech boundaries.
    Returns path to temp WAV file, or None if no speech detected.
    Supports barge-in: if state is forced to LISTENING during recording, returns early.
    """
    HW_RATE = 48000
    CHUNK_SAMPLES = int(0.08 * HW_RATE)  # 80ms chunks
    audio_chunks = []
    speech_started = False
    silence_time = 0.0
    total_time = 0.0
    speech_time = 0.0
    chunk_duration = CHUNK_SAMPLES / HW_RATE

    print(f"Recording (VAD, max {VAD_MAX_DURATION}s)...")
    try:
        with sd.InputStream(samplerate=HW_RATE, blocksize=CHUNK_SAMPLES,
                            device=mic_device, channels=1, dtype="int16"):
            while total_time < VAD_MAX_DURATION:
                chunk = sd.rec(CHUNK_SAMPLES, samplerate=HW_RATE, channels=1, dtype="int16")
                sd.wait()

                # Decimate 48k -> 16k for VAD
                chunk_16k = chunk[::3].flatten()
                is_speech = vad_is_speech(chunk_16k)

                audio_chunks.append(chunk.copy())
                total_time += chunk_duration

                if is_speech:
                    speech_started = True
                    speech_time += chunk_duration
                    silence_time = 0.0
                elif speech_started:
                    silence_time += chunk_duration
                    if silence_time >= VAD_SILENCE_TIMEOUT:
                        print(f"VAD: silence detected ({silence_time:.1f}s), stopping")
                        break

    except Exception as e:
        print(f"Recording error: {e}")
        return None

    if speech_time < VAD_MIN_SPEECH:
        print("VAD: no significant speech detected")
        return None

    # Concatenate and save
    full_audio = np.concatenate(audio_chunks, axis=0)

    # Resample to 16k for STT
    from scipy.signal import resample as scipy_resample
    n_samples_16k = int(len(full_audio) * (16000 / HW_RATE))
    audio_16k = scipy_resample(full_audio.flatten(), n_samples_16k).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio_16k, 16000)
    print(f"Recorded: {speech_time:.1f}s speech, {total_time:.1f}s total")
    return tmp.name


# ---------------------------------------------------------------------------
# STT & Agent Communication
# ---------------------------------------------------------------------------

def clean_stt_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<\|.*?\|>", "", text).strip()
    cleaned = re.sub(r"[^\x00-\x7F]+", "", cleaned).strip()
    hallucinations = {
        "thank you.", "thanks for watching.", "amara.org", "bye.", "you.", ".",
        "thanks for watching!", "subscribe", "thank you", "thanks",
        "hello?", "hello.", "hello", "hi.", "hi", "testing.", "test.",
        "okay.", "okay", "...", ",,,", "www",
    }
    if cleaned.lower() in hallucinations or len(cleaned) <= 2:
        return ""
    return cleaned


def transcribe(audio_path: str) -> str:
    try:
        with open(audio_path, "rb") as f:
            resp = requests.post(VOICE_ENGINE_URL, files={"audio_file": f}, timeout=30)
        if resp.status_code == 200:
            raw = resp.json().get("text", "")
            return clean_stt_text(raw)
    except Exception as e:
        print(f"STT error: {e}")
    return ""


def send_to_agent(text: str) -> dict:
    """Send text to BMO agent. Returns {text, audio_path, session_id}."""
    try:
        resp = requests.post(AGENT_URL, json={"text": text}, timeout=60)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Agent error: {e}")
    return {}


def end_agent_session():
    try:
        requests.post(f"{AGENT_SESSION_URL}/end_session", timeout=10)
    except Exception:
        pass


def new_agent_session():
    try:
        resp = requests.post(f"{AGENT_SESSION_URL}/new_session", timeout=10)
        if resp.status_code == 200:
            sid = resp.json().get("session_id", "?")
            print(f"New session: {sid}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Emotion Detection (for face sync during speaking)
# ---------------------------------------------------------------------------

def detect_emotion(text: str) -> str:
    t = text.lower()
    if "!" in t or any(w in t for w in ["excited", "yay", "awesome", "great", "love", "happy"]):
        return "excited" if "!" in t else "happy"
    if any(w in t for w in ["sad", "sorry", "unfortunately", "bad news", "miss"]):
        return "sad"
    if any(w in t for w in ["whoa", "wow", "oh my", "gasp", "no way"]):
        return "surprised"
    if any(w in t for w in ["yawn", "sleep", "bedtime", "nap", "dream", "sleepy"]):
        return "sleeping"
    if "?" in t or any(w in t for w in ["hmm", "wonder", "think", "what if"]):
        return "thinking"
    if any(w in t for w in ["error", "confused", "weird", "broken"]):
        return "error"
    return "neutral"


def extract_audio_path(path_str: str) -> Optional[str]:
    if not path_str:
        return None
    if path_str.startswith("/") and os.path.exists(path_str):
        return path_str
    match = re.search(r"((?:/app|/workspace)[a-zA-Z0-9_\-/]+\.wav)", path_str)
    return match.group(1) if match else path_str


# ---------------------------------------------------------------------------
# Barge-In Monitor (runs during SPEAKING state)
# ---------------------------------------------------------------------------

def barge_in_monitor(mic_device: Optional[int], state_machine: StateMachine):
    """
    Background thread that listens for speech during playback.
    If speech is detected, interrupts playback and forces LISTENING state.
    """
    HW_RATE = 48000
    CHUNK = int(0.08 * HW_RATE)
    consecutive_speech = 0
    REQUIRED_FRAMES = 3  # ~240ms of continuous speech to trigger barge-in

    try:
        with sd.InputStream(samplerate=HW_RATE, blocksize=CHUNK,
                            device=mic_device, channels=1, dtype="int16") as stream:
            while state_machine.state == BMOState.SPEAKING:
                chunk, _ = stream.read(CHUNK)
                chunk_16k = chunk[::3].flatten()
                if vad_is_speech(chunk_16k):
                    consecutive_speech += 1
                    if consecutive_speech >= REQUIRED_FRAMES:
                        print("Barge-in detected!")
                        interrupt_playback()
                        state_machine.force(BMOState.LISTENING)
                        return
                else:
                    consecutive_speech = 0
    except Exception as e:
        print(f"Barge-in monitor error: {e}")


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def main():
    print("--- BMO Voice Satellite v2 ---")

    # Load wake word model
    import openwakeword
    from openwakeword.model import Model

    all_models = openwakeword.get_pretrained_model_paths()
    local_models = [f for f in os.listdir(".") if f.endswith(".onnx")
                    and any(m in f for m in WAKE_WORD_MODELS)]
    model_paths = [os.path.abspath(f) for f in local_models]
    if not model_paths:
        model_paths = [p for p in all_models if any(m in p for m in WAKE_WORD_MODELS)]
    active_models = WAKE_WORD_MODELS if model_paths else []

    if not model_paths:
        # Fallback
        model_paths = [p for p in all_models if "hey_jarvis_v0.1" in p]
        active_models = ["hey_jarvis_v0.1"]
    if not model_paths:
        print("FATAL: No wake word models found")
        sys.exit(1)

    oww = Model(wakeword_model_paths=model_paths)
    print(f"Wake word: {[os.path.basename(p) for p in model_paths]}")

    # Load VAD
    _load_vad()

    # State machine
    sm = StateMachine()
    sm.on_change(sync_face_to_state)

    # Face worker
    threading.Thread(target=face_worker, daemon=True).start()

    # Detect hardware
    mic = detect_mic_device()
    HW_RATE = 48000
    HW_CHUNK = int(CHUNK_SIZE * (HW_RATE / SAMPLE_RATE))

    # Keyboard trigger
    trigger_queue = queue.Queue()

    def keyboard_listener():
        while True:
            try:
                input()
                trigger_queue.put("manual")
            except EOFError:
                time.sleep(3600)

    threading.Thread(target=keyboard_listener, daemon=True).start()

    # Start new agent session
    new_agent_session()

    # Audio queue for wake word detection
    audio_q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status and "input overflow" not in str(status):
            print(f"Audio: {status}")
        audio_q.put(indata.copy())

    last_interaction = time.time()
    session_active = True

    print(f"\nListening on mic {mic} at {HW_RATE}Hz...")
    print("Press ENTER for manual trigger\n")
    update_face("neutral")

    while True:
        # Session inactivity check
        if session_active and (time.time() - last_interaction) > SESSION_INACTIVITY:
            print("Session timeout, ending...")
            end_agent_session()
            session_active = False

        # ========== IDLE: Listen for wake word ==========
        triggered = False
        try:
            with sd.InputStream(samplerate=HW_RATE, blocksize=HW_CHUNK,
                                device=mic, channels=1, callback=audio_callback,
                                dtype="int16", latency="high"):
                while not triggered:
                    # Manual trigger
                    try:
                        trigger_queue.get_nowait()
                        triggered = True
                        break
                    except queue.Empty:
                        pass

                    # Wake word
                    try:
                        chunk = audio_q.get(timeout=0.05)
                        if audio_q.qsize() > 5:
                            continue  # Drain backlog
                        processed = chunk[::3].flatten()
                        pred = oww.predict(processed)
                        for mdl in active_models:
                            key = mdl.replace(".onnx", "")
                            score = pred.get(mdl, pred.get(key, 0))
                            if score >= WAKE_THRESHOLD:
                                print(f"Wake word: {key}!")
                                triggered = True
                                break
                    except queue.Empty:
                        pass

        except Exception as e:
            print(f"Audio stream error: {e}")
            time.sleep(2)
            continue

        if not triggered:
            continue

        # ========== WAKE_DETECTED ==========
        sm.transition(BMOState.WAKE_DETECTED)
        play_wake_ping()

        if not session_active:
            new_agent_session()
            session_active = True

        # ========== LISTENING (VAD-based) ==========
        sm.transition(BMOState.LISTENING)
        oww.reset()

        # Drain queues
        with audio_q.mutex:
            audio_q.queue.clear()
        with trigger_queue.mutex:
            trigger_queue.queue.clear()

        audio_path = record_with_vad(mic, sm)
        if not audio_path:
            sm.force(BMOState.IDLE)
            update_face("neutral")
            continue

        # ========== PROCESSING ==========
        sm.transition(BMOState.PROCESSING)
        text = transcribe(audio_path)
        os.remove(audio_path)

        if not text:
            print("No speech transcribed")
            sm.force(BMOState.IDLE)
            update_face("neutral")
            continue

        print(f"User: {text}")
        data = send_to_agent(text)
        reply = data.get("text", "")
        raw_audio = data.get("audio_path")
        audio_file = extract_audio_path(raw_audio)
        last_interaction = time.time()

        if not reply and not audio_file:
            print("No agent response")
            sm.force(BMOState.IDLE)
            update_face("neutral")
            continue

        print(f"BMO: {reply}")

        # ========== SPEAKING (with barge-in) ==========
        sm.transition(BMOState.SPEAKING)

        if audio_file:
            emotion = detect_emotion(reply)
            face_cmd = f"{emotion}_speaking" if emotion != "neutral" else "speaking"

            # Start barge-in monitor in background
            barge_thread = threading.Thread(
                target=barge_in_monitor, args=(mic, sm), daemon=True
            )
            barge_thread.start()

            # Remap container paths to local paths
            host_path = audio_file
            host_path = host_path.replace("/app/agents", os.path.abspath(os.path.join(_script_dir, "..", "agents")))
            host_path = host_path.replace("/app", os.path.abspath(os.path.join(_script_dir, "..")))
            host_path = host_path.replace("/workspace", os.path.abspath(os.path.join(_script_dir, "..")))
            host_path = os.path.normpath(host_path)

            play_audio(host_path, face_cmd)
            barge_thread.join(timeout=0.5)

        # ========== Post-Speaking: Continue or idle ==========
        if _barge_in_flag.is_set():
            # Barge-in happened — already in LISTENING state
            _barge_in_flag.clear()
            print("Continuing after barge-in...")
            # Loop back: record again
            audio_path = record_with_vad(mic, sm)
            if audio_path:
                sm.transition(BMOState.PROCESSING)
                text = transcribe(audio_path)
                os.remove(audio_path)
                if text:
                    print(f"User (barge-in): {text}")
                    data = send_to_agent(text)
                    reply = data.get("text", "")
                    raw_audio = data.get("audio_path")
                    audio_file = extract_audio_path(raw_audio)
                    last_interaction = time.time()
                    if reply:
                        print(f"BMO: {reply}")
                    if audio_file:
                        sm.transition(BMOState.SPEAKING)
                        host_path = audio_file.replace("/app/agents", os.path.abspath(os.path.join(_script_dir, "..", "agents")))
                        host_path = host_path.replace("/app", os.path.abspath(os.path.join(_script_dir, "..")))
                        host_path = host_path.replace("/workspace", os.path.abspath(os.path.join(_script_dir, "..")))
                        host_path = os.path.normpath(host_path)
                        play_audio(host_path, "speaking")

        # Check if BMO asked a question — stay in conversation mode
        if reply and ("?" in reply or "what do you think" in reply.lower() or "how about" in reply.lower()):
            print("BMO asked a question, staying in conversation...")
            sm.force(BMOState.LISTENING)
            time.sleep(0.3)
            audio_path = record_with_vad(mic, sm)
            if audio_path:
                sm.transition(BMOState.PROCESSING)
                text = transcribe(audio_path)
                os.remove(audio_path)
                if text:
                    print(f"User: {text}")
                    data = send_to_agent(text)
                    reply = data.get("text", "")
                    raw_audio = data.get("audio_path")
                    last_interaction = time.time()
                    if reply:
                        print(f"BMO: {reply}")
                    audio_file = extract_audio_path(data.get("audio_path"))
                    if audio_file:
                        sm.transition(BMOState.SPEAKING)
                        host_path = audio_file.replace("/app/agents", os.path.abspath(os.path.join(_script_dir, "..", "agents")))
                        host_path = host_path.replace("/app", os.path.abspath(os.path.join(_script_dir, "..")))
                        host_path = host_path.replace("/workspace", os.path.abspath(os.path.join(_script_dir, "..")))
                        host_path = os.path.normpath(host_path)
                        play_audio(host_path, "speaking")

        # Return to idle
        sm.force(BMOState.IDLE)
        update_face("neutral")

        # Cooldown before next wake word
        time.sleep(2.0)
        oww.reset()
        with audio_q.mutex:
            audio_q.queue.clear()

        print("\nListening...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
        end_agent_session()
