import os
import sys
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
import pvporcupine
import tempfile
import threading
import queue
import re
import subprocess
import socket
from dotenv import load_dotenv

# --- Global Queues & Sockets ---
face_queue = queue.Queue()
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- Configuration ---
SAMPLE_RATE = 16000
POST_INTERACTION_COOLDOWN = 0.5  # brief cooldown after playback to absorb echo
FOLLOWUP_WINDOW = 8.0            # seconds BMO stays in conversation mode after a response
FOLLOWUP_SPEECH_FRAMES = 15      # ~480ms of confirmed speech needed (harder to false-trigger)
SILENCE_GATE_FRAMES = 12         # ~384ms of quiet required BEFORE follow-up speech counts
                                 # TV audio is continuous and never passes this gate;
                                 # conversation speech comes after a pause.
_speech_threshold = 10000         # calibrated at startup in main(); used by record_with_vad()

def _find_ppn_model():
    """Find the Beem-Moe .ppn file from common locations."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))
    candidate_dirs = [
        os.getcwd(),
        script_dir,
        repo_root,
        os.path.join(repo_root, "agents", "bmo_voice"),
    ]
    for d in candidate_dirs:
        try:
            for f in os.listdir(d):
                if f.lower().endswith(".ppn"):
                    return os.path.join(d, f)
        except Exception:
            pass
    return None

# --- NETWORK CONFIGURATION ---
# Load from network.env (single source of truth) or environment variable
_script_dir = os.path.dirname(os.path.abspath(__file__))
# Try scripts/../network.env (when run from repo) or bmo_client/network.env (when deployed to Pi)
for _candidate in [os.path.join(_script_dir, "..", "network.env"), os.path.join(_script_dir, "network.env")]:
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break

# Try centralized config first, then env var, then fallback
HOST_IP = os.getenv("LOVELACE_IP") or os.getenv("BMO_HOST_IP", "")

if not HOST_IP:
    print("\n❌ ERROR: HOST_IP could not be determined.")
    print("Set LOVELACE_IP in network.env or BMO_HOST_IP environment variable.")
    sys.exit(1)

print(f"🌐 Host IP: {HOST_IP}")

VOICE_ENGINE_URL = f"http://{HOST_IP}:8020/stt"
SPEAKER_VERIFY_URL = f"http://{HOST_IP}:8020/verify_speaker"
SPEAKER_VERIFY_ENABLED = os.getenv("BMO_SPEAKER_VERIFY", "false").lower() == "true"
AGENT_URL = f"http://{HOST_IP}:8008/v1/voice/chat"

# --- BMO Face Sync ---
BMO_FIFO = "/tmp/bmo_cmd.fifo"

def update_bmo_face(expression):
    """Queue a face expression update (Thread-safe) and broadcast state."""
    face_queue.put(expression)
    try:
        # Broadcast the state change to the Host PC for instant monitoring
        udp_sock.sendto(f"BMO_STATE:{expression}".encode('utf-8'), (HOST_IP, 8123))
    except Exception:
        pass

def send_rms_to_face(rms_value):
    """Write mic RMS level to the FIFO for bmo_driver's mic indicator (non-blocking)."""
    if not os.path.exists(BMO_FIFO):
        return
    try:
        fd = os.open(BMO_FIFO, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, f"rms:{rms_value}\n".encode())
        os.close(fd)
    except OSError:
        pass  # Not readable (nobody on the other end) or busy — skip silently

def face_worker():
    """Background worker to handle persistent FIFO writes."""
    print("🎨 Face Worker Thread Started.")
    while True:
        expression = face_queue.get()
        try:
            if os.path.exists(BMO_FIFO):
                # Open the FIFO, write the command, and close it immediately.
                # This guarantees that bmo_driver reads it immediately without buffering issues.
                with open(BMO_FIFO, 'w') as f:
                    f.write(f"face:{expression}\n")
                    f.flush()
            else:
                print(f"⚠️ BMO_FIFO not found at {BMO_FIFO}.")
        except Exception as e:
            print(f"Face Worker Error: {expression} -> {e}")
        face_queue.task_done()
# Note: If accessing from WSL or container, localhost might need adjustment. 
# Assuming script runs on Host Windows Machine.

# Audio Playback
def generate_silence(duration=1.0, filename="/tmp/silence.wav"):
    """Generate a silent WAV file to wake up sleeping HDMI receivers."""
    if not os.path.exists(filename):
        import wave
        import struct
        sample_rate = 44100
        n_samples = int(duration * sample_rate)
        with wave.open(filename, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            for _ in range(n_samples):
                f.writeframesraw(struct.pack('<h', 0))
    return filename

def play_audio(file_path, face_cmd="speaking"):
    """Play audio via aplay for HDMI compatibility."""
    try:
        # 1. Check if path is actually a URL or local filename
        filename = os.path.basename(file_path)
        local_tmp = os.path.join(tempfile.gettempdir(), filename)
        
        # 2. Download if it doesn't exist locally
        if not os.path.exists(file_path):
            print(f"📥 Downloading: {filename} from server...")
            # Route to the correct static mount based on the container path
            if "voice_samples" in file_path:
                url = f"http://{HOST_IP}:8008/voice_samples/{filename}"
            else:
                url = f"http://{HOST_IP}:8008/delivered_artifacts/{filename}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(local_tmp, 'wb') as f:
                    f.write(r.content)
                file_path = local_tmp
            else:
                print(f"❌ Download failed: {r.status_code} from {url}")
                return

        # 3. Play via aplay on HDMI
        # Dynamically auto-detect HDMI device right before playback (handles TV power cycling)
        aplay_device = detect_hdmi_device()
        print(f"🔊 Playing via HDMI: {filename} on {aplay_device}")
        
        # HDMI Wake-up Trick: Play 1.2s of silence FIRST to wake the receiver
        silence_wav = generate_silence(1.2)
        subprocess.run(["aplay", "-D", aplay_device, silence_wav], check=False, capture_output=True)
        
        # NOW that the HDMI is awake, send the Face command to the Pipe!
        if face_cmd:
            update_bmo_face(face_cmd)
        
        # Play the actual audio file
        result = subprocess.run(
            ["aplay", "-D", aplay_device, file_path],
            check=False, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️ aplay error on {aplay_device}: {result.stderr.strip()}")
            # Fallback to default
            print("🔄 Retrying with 'default' device...")
            subprocess.run(["aplay", file_path], check=False)
        
        if local_tmp == file_path and os.path.exists(local_tmp):
            os.remove(local_tmp)
            
    except Exception as e:
        print(f"Error in play_audio: {e}")

def play_wake_ping():
    """Play a pleasant two-tone ascending chime (C6→E6) to confirm wake word detection."""
    try:
        ping_wav = os.path.join(tempfile.gettempdir(), "bmo_wake.wav")
        if not os.path.exists(ping_wav):
            import wave
            import struct
            import math
            sample_rate = 44100
            tone_duration = 0.1   # 100ms per tone
            gap_duration = 0.03   # 30ms between tones
            n_tone = int(tone_duration * sample_rate)
            n_gap = int(gap_duration * sample_rate)
            
            freqs = [1047.0, 1319.0]  # C6, E6 — ascending major third
            
            with wave.open(ping_wav, 'w') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sample_rate)
                for fi, freq in enumerate(freqs):
                    for i in range(n_tone):
                        # Envelope: quick attack, smooth decay
                        env = min(1.0, i / (n_tone * 0.05)) * max(0.0, 1.0 - (i / n_tone) * 0.5)
                        value = int(32767.0 * 0.25 * env * math.sin(2.0 * math.pi * freq * i / sample_rate))
                        f.writeframesraw(struct.pack('<h', value))
                    # Add gap between tones (silence)
                    if fi < len(freqs) - 1:
                        for _ in range(n_gap):
                            f.writeframesraw(struct.pack('<h', 0))
                    
        aplay_device = detect_hdmi_device()
        # Wake the HDMI receiver first (same trick as play_audio) so the chime isn't dropped
        silence_wav = generate_silence(0.5)
        subprocess.run(["aplay", "-D", aplay_device, silence_wav], check=False, capture_output=True)
        subprocess.run(["aplay", "-D", aplay_device, ping_wav], check=False, capture_output=True)
    except Exception as e:
        print(f"Wake Ping Error: {e}")

def detect_hdmi_device():
    """Auto-detect the HDMI ALSA device name."""
    try:
        result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if "hdmi" in line.lower() or "vc4" in line.lower():
                # Example: 'card 1: vc4hdmi [vc4-hdmi], device 0: MAI PCM ...'
                card_match = re.search(r'card\s+(\d+)', line)
                dev_match = re.search(r'device\s+(\d+)', line)
                if card_match:
                    card = card_match.group(1)
                    dev = dev_match.group(1) if dev_match else '0'
                    device = f"plughw:{card},{dev}"
                    print(f"🔊 Auto-detected HDMI: {device} ({line.strip()})")
                    return device
    except Exception as e:
        print(f"HDMI detection failed: {e}")
    print("⚠️ No HDMI device found, using 'default'")
    return "default"

def detect_mic_device():
    """Auto-detect the USB microphone index (sounddevice)."""
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            # Prioritize external USB / Plantronics mics over default board mics
            if ("usb" in name or "plantronics" in name or "blackwire" in name) and dev['max_input_channels'] > 0:
                print(f"🎙️ Auto-detected Mic: Index {i} ({dev['name']})")
                return i
    except Exception as e:
        print(f"Mic detection failed: {e}")
    print("⚠️ No USB Mic found, falling back to System Default.")
    return None # None tells sounddevice to use system default

def _verify_speaker(wav_path: str) -> bool:
    """
    POST the audio to voice_engine's /verify_speaker endpoint.
    Returns True if the speaker is recognized OR if no profiles are enrolled yet.
    Returns False only when a profile exists and the speaker doesn't match.
    Fails open (returns True) on network/service errors so BMO isn't silently broken.
    """
    try:
        with open(wav_path, "rb") as f:
            resp = requests.post(
                SPEAKER_VERIFY_URL,
                files={"audio": (os.path.basename(wav_path), f, "audio/wav")},
                timeout=5.0,
            )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("no_profiles"):
                return True  # Nothing enrolled yet — allow all (setup mode)
            accepted = data.get("accepted", False)
            score = data.get("score", 0.0)
            speaker = data.get("matched_speaker") or "unknown"
            print(f"🔐 Speaker: {speaker}  score={score:.3f}  {'✅ allowed' if accepted else '🚫 rejected'}")
            return accepted
        else:
            print(f"⚠️ Speaker verify returned {resp.status_code} — failing open")
            return True
    except Exception as e:
        print(f"⚠️ Speaker verify error: {e} — failing open")
        return True

def clean_stt_text(text):
    """Remove special model tags like <|en|><|Speech|> from transcription."""
    if not text:
        return ""
    # Remove everything between <| and |>
    cleaned = re.sub(r"<\|.*?\|>", "", text).strip()
    
    # Strip all non-ASCII characters (Kills Whisper's Korean/Chinese/Russian hallucinations on silence)
    cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned).strip()
    
    # Filter common Whisper hallucination triggers on blank audio
    lower_c = cleaned.lower()
    hallucinations = [
        "thank you.", "thanks for watching.", "amara.org", "bye.", "you.", ".", 
        "thanks for watching!", "subscribe", "thank you", "thanks", "thanks for watching",
        "hello?", "hello.", "hello", "hi.", "hi", "testing.", "test.", "test", "...", 
        ",,,", "www", "okay.", "okay"
    ]
    if lower_c in hallucinations or len(lower_c) <= 2:
        return ""
        
    return cleaned

def extract_audio_path(path_str):
    """Extract a raw file path from potentially descriptive agent output."""
    if not path_str:
        return None
    
    # If it's already a clean path, return it
    if path_str.startswith("/") and os.path.exists(path_str):
        return path_str
        
    # Look for patterns like /app/... or /workspace/... inside the string
    match = re.search(r"((?:/app|/workspace)[a-zA-Z0-9_\-/]+\.wav)", path_str)
    if match:
        return match.group(1)
        
    return path_str # Fallback


def detect_emotion(text):
    """Simple keyword-based emotion detection for syncing faces."""
    text = text.lower()
    
    if "!" in text or any(w in text for w in ["excited", "yay", "awesome", "great", "love", "happy", "yes!"]):
        if "!" in text:
            return "excited"
        return "happy"

    if any(w in text for w in ["sad", "sorry", "unfortunately", "bad news", "miss", "tired", "no..."]):
        return "sad"

    if any(w in text for w in ["whoa", "wow", "oh my", "gasp", "no way"]):
        return "surprised"
        
    if any(w in text for w in ["yawn", "sleep", "bedtime", "nap", "dream", "tired ", "sleepy"]):
        return "sleeping"

    if "?" in text or any(w in text for w in ["hmm", "wonder", "think", "what if", "wait"]):
        return "thinking"

    if any(w in text for w in ["error", "confused", "weird", "broken", "fail"]):
        return "error"

    return "neutral"


def record_with_vad(device, sample_rate=16000, frame_size=512,
                   silence_frames_needed=20, max_duration=15.0):
    """
    Record audio dynamically using Voice Activity Detection.
    Stops when the speaker pauses (silence_frames_needed × ~32ms of quiet)
    or max_duration is reached. Returns numpy int16 array, or None if no
    speech starts within a 3-second timeout.
    """
    buf = queue.Queue()
    collected = []
    speech_started = False
    silent_frames = 0
    total_frames = 0
    speech_frame_count = 0
    max_frames = int(max_duration * sample_rate / frame_size)
    no_speech_timeout_frames = int(3.0 * sample_rate / frame_size)  # give up after 3s silence
    min_speech_frames = int(0.3 * sample_rate / frame_size)          # at least 0.3s of content

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
                        print(f"🔇 End of speech ({speech_frame_count * frame_size / sample_rate:.1f}s spoken)")
                        break
                else:
                    # No speech yet — abort if timeout exceeded
                    if total_frames > no_speech_timeout_frames:
                        return None
    except Exception as e:
        print(f"VAD Error: {e}")
        return None

    if not collected or speech_frame_count < min_speech_frames:
        return None

    return np.concatenate(collected)


def _is_speech_frame(pcm: np.ndarray, threshold: int) -> bool:
    """
    Lightweight speech discriminator: RMS above threshold AND zero-crossing rate
    within the voiced-speech range (roughly 20-250 ZCR per 512 samples at 16kHz).
    Music and TV audio typically have ZCR outside this window (very high for
    broadband noise/music, very low for low-frequency rumble).
    """
    rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
    if rms < threshold:
        return False
    # Zero-crossing rate: count sign changes, normalised to per-512-sample range
    signs = np.sign(pcm.astype(np.float32))
    signs[signs == 0] = 1  # treat silence as positive
    crossings = int(np.sum(np.abs(np.diff(signs))) // 2)
    # Voiced speech: ~20–250 crossings per 512 samples. Broadband TV/music
    # is often higher; low-frequency thumps are lower.
    return 20 <= crossings <= 350


# --- Main Logic ---
def main():
    global _speech_threshold
    print("--- 🛰️ AI Lab Voice Satellite Online ---")

    # 1. Load Porcupine wake word engine
    print("Loading Wake Word Model (Porcupine)...")
    access_key = os.getenv("PICOVOICE_KEY", "")
    if not access_key:
        print("❌ Critical Error: PICOVOICE_KEY not set in environment/network.env")
        sys.exit(1)

    ppn_path = _find_ppn_model()
    if not ppn_path:
        print("❌ Critical Error: No .ppn wake word model file found.")
        sys.exit(1)
    print(f"🐷 PPN model: {os.path.basename(ppn_path)}")

    try:
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[ppn_path],
            sensitivities=[0.65],  # 0.99 causes TV/ambient false positives; 0.65 is reliable
        )
    except Exception as e:
        print(f"❌ Failed to initialize Porcupine: {e}")
        sys.exit(1)

    # Capture directly at 16kHz — no decimation, cleaner audio for Porcupine
    FRAME_LENGTH = porcupine.frame_length  # typically 512
    HARDWARE_RATE = 16000
    HARDWARE_CHUNK = FRAME_LENGTH  # 512 samples = 32ms at 16kHz
    print(f"✅ Porcupine ready. frame_length={FRAME_LENGTH}, hw_rate={HARDWARE_RATE}")

    # 2. Queues & Threads
    audio_queue = queue.Queue()
    trigger_queue = queue.Queue()

    # Start Face worker
    threading.Thread(target=face_worker, daemon=True).start()

    def callback(indata, frames, time_info, status):
        if status and 'input overflow' not in str(status):
            print(f"Audio Status: {status}")
        audio_queue.put(indata.copy())

    # 3. Keyboard Trigger Thread (only in interactive/debug mode, not as a service)
    if sys.stdin and sys.stdin.isatty():
        def keyboard_listener():
            while True:
                try:
                    input("\n⌨️ Press ENTER to trigger BMO manually...\n")
                    print("🛠️ DEBUG: Keyboard Input Detected. Sending trigger...")
                    trigger_queue.put("manual")
                except EOFError:
                    time.sleep(3600)

        threading.Thread(target=keyboard_listener, daemon=True).start()

    # 4. Detect MIC device and start Main Loop
    MIC_DEVICE = detect_mic_device()

    # Force mic capture gain to a sane level — this USB codec resets to max (42/42)
    # every time the device is opened. Set it here so it applies on every restart.
    try:
        subprocess.run(["amixer", "-c", "2", "sset", "Mic", "35", "cap"],
                       capture_output=True, check=False)
        print("🎚️  Mic capture gain set to 35/42 (+21dB)")
    except Exception as _e:
        print(f"⚠️  Could not set mic gain: {_e}")

    print(f"\n🛰️  Satellite Listening at {HARDWARE_RATE}Hz (direct 16kHz, no decimation)...")
    if sys.stdin and sys.stdin.isatty():
        print("⌨️   Trigger: Press ENTER in this terminal.")
    print("🎙️   Wake Word: 'Beemo' (Porcupine custom model)\n")
    update_bmo_face("neutral")

    followup_until = 0.0  # timestamp until which conversation mode is active
    silence_gate = 0       # consecutive quiet frames accumulated before follow-up speech
    last_heartbeat = time.time()
    last_rms_log = time.time()
    last_rms_face = time.time()
    rms_max = 0
    speech_frames = 0  # consecutive frames above speech threshold
    SPEECH_THRESHOLD = 10000  # default; overwritten by calibration below
    SPEECH_FRAMES_NEEDED = 8  # ~256ms of sustained speech

    # ── Calibrate ambient noise floor ─────────────────────────────────────────
    # Measure for 3s then set threshold at 2.5× ambient mean so speech (louder
    # than ambient) reliably triggers while continuous background noise does not.
    print("📏 Calibrating ambient noise floor — please stay quiet for 3 seconds...")
    _cal_rms_samples = []
    _cal_start = time.time()
    try:
        def _cal_callback(indata, frames, time_info, status):
            _cal_rms_samples.append(int(np.sqrt(np.mean(indata.astype(np.float32) ** 2))))
        with sd.InputStream(samplerate=HARDWARE_RATE, blocksize=HARDWARE_CHUNK,
                            device=MIC_DEVICE, channels=1, callback=_cal_callback,
                            dtype='int16', latency='high'):
            while time.time() - _cal_start < 3.0:
                time.sleep(0.05)
    except Exception as _e:
        print(f"⚠️ Calibration failed: {_e} — using default threshold {SPEECH_THRESHOLD}")
        _cal_rms_samples = []

    if _cal_rms_samples:
        _ambient_mean = int(np.mean(_cal_rms_samples))
        _ambient_std  = int(np.std(_cal_rms_samples))
        # mean + 2×std: statistically, 10 consecutive frames at this level from
        # ambient alone has probability ~(0.023)^10 ≈ 0 — but speech sustains it.
        # Cap at 30000 so we never go above int16 max (32767).
        SPEECH_THRESHOLD = min(max(int(_ambient_mean + 2.0 * _ambient_std), 5000), 30000)
        _speech_threshold = SPEECH_THRESHOLD  # expose to record_with_vad()
        print(f"📏 Ambient RMS: mean={_ambient_mean}, std={_ambient_std} → SPEECH_THRESHOLD={SPEECH_THRESHOLD}")
    else:
        print(f"📏 Using default threshold: {SPEECH_THRESHOLD}")
    # ──────────────────────────────────────────────────────────────────────────

    while True:
        interacted = False
        try:
            with sd.InputStream(samplerate=HARDWARE_RATE, blocksize=HARDWARE_CHUNK,
                                device=MIC_DEVICE, channels=1, callback=callback,
                                dtype='int16', latency='high'):
                print("🛠️ DEBUG: InputStream open. Listening for wake word...")
                interacted = False
                while not interacted:
                    if time.time() - last_heartbeat > 5:
                        print(f"🛠️ DEBUG: alive. Q={audio_queue.qsize()}")
                        last_heartbeat = time.time()

                    # 1. Check for manual/keyboard trigger
                    while not trigger_queue.empty():
                        trigger = trigger_queue.get_nowait()
                        if trigger == "manual":
                            print("⚡ Manual Trigger Detected!")
                            update_bmo_face("listening")
                            interacted = True
                            break
                    if interacted:
                        break

                    # 2. Check for audio data — Porcupine wake word
                    try:
                        chunk = audio_queue.get(timeout=0.05)

                        # Drain stale chunks; keep only the freshest
                        while audio_queue.qsize() > 1:
                            audio_queue.get_nowait()

                        # Direct 16kHz capture — no decimation needed
                        pcm = chunk.flatten()

                        # RMS monitoring
                        rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                        if rms > rms_max:
                            rms_max = rms
                        if time.time() - last_rms_log > 10:
                            print(f"🎙️ Mic RMS (peak 10s): {rms_max}  (silent if <50, low if <500)")
                            rms_max = 0
                            last_rms_log = time.time()
                        # Send live RMS to BMO face display every 0.5s
                        if time.time() - last_rms_face >= 0.5:
                            send_rms_to_face(rms)
                            last_rms_face = time.time()

                        # Porcupine needs exactly frame_length samples.
                        # Attenuate to 25% before passing: mic AGC saturates output at ~30k
                        # RMS regardless of room volume, destroying spectral features at full
                        # scale. 25% brings it to ~7.5k which matches Porcupine's trained range.
                        pcm_ppn = (pcm.astype(np.float32) * 0.25).clip(-32768, 32767).astype(np.int16)
                        detected = False
                        for i in range(0, len(pcm_ppn) - FRAME_LENGTH + 1, FRAME_LENGTH):
                            frame = pcm_ppn[i:i + FRAME_LENGTH]
                            result = porcupine.process(frame)
                            if result >= 0:
                                detected = True
                                break

                        if detected:
                            print("⚡ Wake Word Detected: Beemo!")
                            speech_frames = 0
                            update_bmo_face("acknowledged")
                            play_wake_ping()
                            update_bmo_face("listening")
                            time.sleep(0.1)
                            interacted = True

                        else:
                            # Follow-up conversation window — re-trigger without wake word.
                            # GATE: requires SILENCE_GATE_FRAMES of quiet before speech.
                            # This rejects continuous TV audio (no silence → no gate)
                            # and accepts conversational speech (pause → then speak).
                            if followup_until > time.time():
                                if rms < SPEECH_THRESHOLD:
                                    # Quiet frame — advance silence gate, reset speech counter
                                    silence_gate = min(silence_gate + 1, SILENCE_GATE_FRAMES + 1)
                                    speech_frames = 0
                                elif silence_gate >= SILENCE_GATE_FRAMES:
                                    # Pre-silence gate passed — check it's speech-like (ZCR)
                                    if _is_speech_frame(pcm, SPEECH_THRESHOLD):
                                        speech_frames += 1
                                        if speech_frames >= FOLLOWUP_SPEECH_FRAMES:
                                            print(f"💬 Follow-up speech detected (gate={silence_gate}, frames={speech_frames})")
                                            speech_frames = 0
                                            silence_gate = 0
                                            update_bmo_face("acknowledged")
                                            interacted = True
                                    else:
                                        speech_frames = 0  # ZCR check failed (probably TV/music)
                                else:
                                    # Loud but no pre-silence — TV/continuous noise, ignore
                                    speech_frames = 0
                            else:
                                silence_gate = 0
                                speech_frames = 0

                    except queue.Empty:
                        pass
        except Exception as e:
            print(f"🛠️ DEBUG: Stream error: {e}")
            print("Tip: Make sure no other program is using the microphone.")
            time.sleep(2)

        # --- OUTSIDE MIC STREAM ---
        if interacted:
            speech_frames = 0  # reset counter so we don't re-trigger immediately
            handle_interaction()
            followup_until = time.time() + FOLLOWUP_WINDOW
            with audio_queue.mutex:
                audio_queue.queue.clear()
            with trigger_queue.mutex:
                trigger_queue.queue.clear()
            time.sleep(POST_INTERACTION_COOLDOWN)  # absorb echo before follow-up detection starts
            print(f"\n💬 Conversation mode active for {FOLLOWUP_WINDOW:.0f}s — speak to continue without wake word...")
            print("\nListening...")

    porcupine.delete()

def handle_interaction():
    # Wait briefly for the listener stream to release the hardware
    time.sleep(0.3)
    # Record directly at 16kHz (mic now captures at 16kHz natively — no resampling needed)
    HW_RATE = 16000
    STT_RATE = 16000
    # Ensure the face is definitely listening while recording
    update_bmo_face("listening")
    print("🎤 Recording (VAD — stops on silence)...")

    recording = record_with_vad(device=detect_mic_device(), sample_rate=HW_RATE)
    if recording is None:
        print("⚠️ No speech detected — skipping.")
        update_bmo_face("neutral")
        return False

    rec_rms = int(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))
    print(f"🎙️ Recording RMS: {rec_rms} | {len(recording)/HW_RATE:.1f}s captured")
    
    # Save to temp (already 16kHz, no resampling)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, recording.astype(np.int16), STT_RATE)
        temp_path = tmp.name

    # --- Speaker verification gate ---
    if SPEAKER_VERIFY_ENABLED:
        if not _verify_speaker(temp_path):
            print("🚫 Unrecognized speaker — ignoring interaction.")
            update_bmo_face("neutral")
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return False

    print("Sending to STT...")
    update_bmo_face("thinking")
    try:
        with open(temp_path, 'rb') as f:
            files = {'audio_file': (temp_path, f, 'audio/wav')}
            response = requests.post(VOICE_ENGINE_URL, files=files)
            
        if response.status_code == 200:
            raw_text = response.json().get("text", "")
            text = clean_stt_text(raw_text)
            print(f"📝 Transcribed: {text}")
            
            if text:
                update_bmo_face("thinking")
                return process_agent_response(text)
            else:
                print("No speech detected.")
                update_bmo_face("neutral")
                return False
        else:
            print(f"STT Error: {response.text}")
            update_bmo_face("neutral")
            return False
            
    except Exception as e:
        print(f"Interaction Error: {e}")
        update_bmo_face("neutral")
        return False
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

def process_agent_response(text):
    """Sends text to LLM and plays response. Returns True if BMO asked a question."""
    print("🤖 Sending to Agent...")
    update_bmo_face("thinking")
    t_start = time.time()
    try:
        payload = {"text": text}
        response = requests.post(AGENT_URL, json=payload, timeout=120)
        t_resp = time.time()
        print(f"⏱  Agent Response Time: {t_resp - t_start:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            reply = data.get("text", "")
            raw_audio_path = data.get("audio_path")
            audio_path = extract_audio_path(raw_audio_path)
            
            print(f"🗣️ Agent: {reply}")
            
            if audio_path:
                host_path = audio_path.replace("/app/agents", os.path.abspath(os.path.join(os.path.dirname(__file__), "../agents")))
                host_path = host_path.replace("/app", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                host_path = host_path.replace("/workspace", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                host_path = os.path.normpath(host_path)
                
                print(f"🔊 Audio path (raw): {audio_path}")
                print(f"🔊 Audio path (host): {host_path}")
                print(f"🔊 File exists locally: {os.path.exists(host_path)}")
                
                emotion = detect_emotion(reply)
                if emotion == "neutral":
                    face_cmd = "speaking"
                else:
                    face_cmd = f"{emotion}_speaking"
                    
                play_audio(host_path, face_cmd)
                update_bmo_face("neutral")
            else:
                print("(No Audio Response)")
                update_bmo_face("neutral")
                
            # Check if it was a question so we can keep the conversation going
            if "?" in reply or "what do you think" in reply.lower() or "how about" in reply.lower():
                return True
            return False
                
        else:
            print(f"Agent Error: {response.text}")
            update_bmo_face("neutral")
            return False
            
    except Exception as e:
        print(f"Agent Request Error: {e}")
        update_bmo_face("neutral")
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSee you later!")


