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
import re
import subprocess
import socket
from dotenv import load_dotenv

# --- Global Queues & Sockets ---
face_queue = queue.Queue()
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- Configuration ---
WAKE_WORD_MODELS = ["hey_beeMo"] # Custom BMO model
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280 # 80ms
THRESHOLD = 0.5
POST_INTERACTION_COOLDOWN = 2.0  # seconds to ignore audio after speaking

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
AGENT_URL = f"http://{HOST_IP}:8000/v1/voice/chat"

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
                url = f"http://{HOST_IP}:8000/voice_samples/{filename}"
            else:
                url = f"http://{HOST_IP}:8000/delivered_artifacts/{filename}"
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

# --- Main Logic ---
def main():
    print("--- 🛰️ AI Lab Voice Satellite Online ---")
    
    # 1. Load Model
    print("Loading Wake Word Model...")
    
    # Resolve absolute paths for older openwakeword versions
    import openwakeword
    all_models = openwakeword.get_pretrained_model_paths()
    
    # Check for local models first
    local_models = [f for f in os.listdir(".") if f.endswith(".onnx") and any(m in f for m in WAKE_WORD_MODELS)]
    model_paths = [os.path.abspath(f) for f in local_models]
    
    if not model_paths:
        # Fallback to built-ins
        model_paths = [p for p in all_models if any(m in p for m in WAKE_WORD_MODELS)]
    
    if not model_paths:
        print(f"⚠️ Warning: Could not find model {WAKE_WORD_MODELS} in local directory or built-ins.")
        print("Falling back to 'hey_jarvis_v0.1' for now so you can use the manual trigger.")
        model_paths = [p for p in all_models if "hey_jarvis_v0.1" in p]
        # Update the active models list to match the fallback
        active_models = ["hey_jarvis_v0.1"]
    else:
        active_models = WAKE_WORD_MODELS
        
    if not model_paths:
        print("❌ Critical Error: No built-in models found at all.")
        sys.exit(1)
        
    owwModel = Model(wakeword_model_paths=model_paths)
    print(f"Model Loaded: {[os.path.basename(p) for p in model_paths]}")
    
    # Use the active models for prediction checks
    WW_TO_CHECK = active_models

    # 2. Queues & Threads
    audio_queue = queue.Queue()
    trigger_queue = queue.Queue()
    
    # Start Face worker
    threading.Thread(target=face_worker, daemon=True).start()

    def callback(indata, frames, time, status):
        if status and 'input overflow' not in str(status):
            print(f"Audio Status: {status}")
        audio_queue.put(indata.copy())

    # 3. Keyboard Trigger Thread
    def keyboard_listener():
        while True:
            try:
                input("\n⌨️ Press ENTER to trigger BMO manually...\n")
                print("🛠️ DEBUG: Keyboard Input Detected. Sending trigger...")
                trigger_queue.put("manual")
            except EOFError:
                # Running as a background service without a terminal
                time.sleep(3600)  # Wait forever without burning CPU

    threading.Thread(target=keyboard_listener, daemon=True).start()

    # 4. Detect MIC device and start Main Loop
    MIC_DEVICE = detect_mic_device()
    HARDWARE_RATE = 48000
    HARDWARE_CHUNK = int(CHUNK_SIZE * (HARDWARE_RATE / SAMPLE_RATE))
    
    print(f"\n🛰️  Satellite Listening at {HARDWARE_RATE}Hz...")
    print("⌨️   Trigger: Press ENTER in this terminal.")
    print("🎙️   Wake Word: 'Hey Jarvis' (or custom hey_bmo.onnx)\n")
    update_bmo_face("neutral")

    last_heartbeat = time.time()
    while True:
        try:
            print(f"🛠️ DEBUG: Attempting to open sd.InputStream on Mic {MIC_DEVICE} (This may hang if device is busy)...")
            # We wrap the listener in a context manager so it stops/releases the mic during interaction
            with sd.InputStream(samplerate=HARDWARE_RATE, blocksize=HARDWARE_CHUNK, device=MIC_DEVICE, channels=1, callback=callback, dtype='int16', latency='high'):
                print("🛠️ DEBUG: InputStream SUCCESS! Loop entering active state...")
                interacted = False
                while not interacted:
                    # Loop Heartbeat every 5s
                    if time.time() - last_heartbeat > 5:
                        print(f"🛠️ DEBUG: Main loop is alive. Q sizes: audio={audio_queue.qsize()}, trigger={trigger_queue.qsize()}")
                        last_heartbeat = time.time()

                    # 1. Check for manual/keyboard trigger (High Priority)
                    while not trigger_queue.empty():
                        trigger = trigger_queue.get_nowait()
                        if trigger == "manual":
                            print("⚡ Manual Trigger Detected!")
                            update_bmo_face("listening")
                            interacted = True
                            break
                    if interacted: break

                    # 2. Check for audio data (Wake Word)
                    try:
                        # Timeout must be short to keep manual trigger reactive
                        chunk = audio_queue.get(timeout=0.05)
                        
                        # Handle potential audio overflow - if the queue is backing up, 
                        # just skip wake word processing to let it catch up without crashing
                        if audio_queue.qsize() > 5:
                            # Still take the item out to drain the queue quickly, 
                            # but skip the expensive prediction step
                            continue

                        # PERFORMANCE OPTIMIZATION: 
                        # Raspberry Pi chokes on scipy.signal.resample for live 48k audio.
                        # Since 48000 / 16000 = 3, we simply take every 3rd sample (decimation).
                        # This is nearly 100x faster than FFT-based resampling.
                        processed_chunk = chunk[::3]
                        
                        # Ensure correct shape for ONNX
                        if len(processed_chunk.shape) > 1:
                            processed_chunk = processed_chunk.flatten()

                        prediction = owwModel.predict(processed_chunk)
                    
                        for mdl in WW_TO_CHECK:
                            # Extract basic name for key check (e.g. 'hey_beeMo' from 'hey_beeMo.onnx')
                            # Match both raw name and name with extension to be safe
                            mdl_raw = mdl.replace(".onnx", "")
                            score = prediction.get(mdl, prediction.get(mdl_raw, 0))
                            
                            if score >= THRESHOLD:
                                print(f"⚡ Wake Word Detected: {mdl_raw}!")
                                
                                # 1. Visual Confirmation — "acknowledged" flash
                                update_bmo_face("acknowledged")
                                
                                # 2. Auditory Confirmation — two-tone chime
                                play_wake_ping()
                                
                                # 3. Transition to "listening" for recording phase
                                update_bmo_face("listening")
                                
                                # 4. Brief sleep so face_worker thread can push FIFO 
                                time.sleep(0.1)
                                
                                interacted = True
                                break
                                
                    except queue.Empty:
                        pass
        except Exception as e:
            print(f"🛠️ DEBUG: ALSA Error or Busy Device: {e}")
            print("Tip: Make sure no other program (like bmo_driver.py) is using the microphone.")
            time.sleep(2)

        # --- OUTSIDE MIC STREAM ---
        if interacted:
            wants_reply = handle_interaction()
            # Flush queues to ensure we don't process stale audio/triggers
            with audio_queue.mutex: audio_queue.queue.clear()
            with trigger_queue.mutex: trigger_queue.queue.clear()
            
            # Reset the wake word model to clear any internal state
            owwModel.reset()
            
            if wants_reply:
                print("❓ BMO asked a question. Triggering continuous conversation...")
                # Instantly queue a manual trigger to loop listening
                trigger_queue.put("manual")
            else:
                # Cooldown: wait before listening again to avoid speaker feedback
                print(f"💤 Cooldown ({POST_INTERACTION_COOLDOWN}s)...")
                time.sleep(POST_INTERACTION_COOLDOWN)
                print("\nListening...")

def handle_interaction():
    # Wait briefly for the listener stream to release the hardware
    time.sleep(0.3)
    # Using Hardware Rate for the G933
    HW_RATE = 48000
    STT_RATE = 16000
    duration = 3.8 # Reduced from 5 to decrease latency
    
    # Ensure the face is definitely listening while recording
    update_bmo_face("listening")
    print(f"🎤 Recording Command ({duration}s)...")
    
    recording = sd.rec(int(duration * HW_RATE), samplerate=HW_RATE, channels=1, dtype='int16')
    sd.wait()
    
    # Resample to 16k for the STT engine
    import scipy.signal
    num_samples = int(len(recording) * (STT_RATE / HW_RATE))
    recording_resampled = scipy.signal.resample(recording, num_samples)
    
    # Save to temp
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, recording_resampled.astype(np.int16), STT_RATE)
        temp_path = tmp.name
        
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
                return process_agent_response(text)
            else:
                print("No speech detected.")
                return False
        else:
            print(f"STT Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Interaction Error: {e}")
        return False
    finally:
        os.remove(temp_path)
        update_bmo_face("neutral")

def process_agent_response(text):
    """Sends text to LLM and plays response. Returns True if BMO asked a question."""
    print("🤖 Sending to Agent...")
    t_start = time.time()
    try:
        payload = {"text": text}
        response = requests.post(AGENT_URL, json=payload)
        t_resp = time.time()
        print(f"⏱  Agent Response Time: {t_resp - t_start:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            reply = data.get("text", "")
            raw_audio_path = data.get("audio_path")
            audio_path = extract_audio_path(raw_audio_path)
            
            print(f"🗣️ Agent: {reply}")
            
            if audio_path:
                print(f"🔊 Playing Audio: {audio_path}")
                # Use a specific tool or just play locally if path is accessible?
                # The path returned is inside the container: /app/agents/bmo_voice/voice_samples/... or delivered_artifacts
                # The Host maps ../agents -> /app/agents
                # We need to map container path to host path.
                
                # Container: /app/agents/... -> Host: scripts/../agents/...
                # Container: /app/delivered_artifacts/... -> Host: scripts/../delivered_artifacts/...
                # Container: /workspace/delivered_artifacts/... -> Host: scripts/../delivered_artifacts/...
                
                host_path = audio_path.replace("/app/agents", os.path.abspath(os.path.join(os.path.dirname(__file__), "../agents")))
                host_path = host_path.replace("/app", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                host_path = host_path.replace("/workspace", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                
                # Also handle Windows path separators if needed
                host_path = os.path.normpath(host_path)
                
                emotion = detect_emotion(reply)
                if emotion == "neutral":
                    face_cmd = "speaking"
                else:
                    face_cmd = f"{emotion}_speaking"
                    
                play_audio(host_path, face_cmd)
                update_bmo_face("neutral")
            else:
                print("(No Audio Response)")
                
            # Check if it was a question so we can keep the conversation going
            if "?" in reply or "what do you think" in reply.lower() or "how about" in reply.lower():
                return True
            return False
                
        else:
            print(f"Agent Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Agent Request Error: {e}")
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSee you later!")


