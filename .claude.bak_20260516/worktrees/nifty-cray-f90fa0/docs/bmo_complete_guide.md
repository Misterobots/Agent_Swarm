# BMO Complete Guide

BMO is an animated robot companion inspired by *Adventure Time*. It runs a full
voice pipeline: wake-word detection on a Raspberry Pi → speech-to-text →
LLM response (Ollama) → emotion-aware TTS + RVC voice conversion → animated
face. This guide covers the sandbox, voice satellite, troubleshooting, and
testing workflows.

---

## Table of Contents

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Sandbox – Quick Testing Without Hardware](#2-sandbox--quick-testing-without-hardware)
3. [Voice Operation – Raspberry Pi Satellite](#3-voice-operation--raspberry-pi-satellite)
4. [bmo-voice Service – Docker Container on R730](#4-bmo-voice-service--docker-container-on-r730)
5. [Testing Reference](#5-testing-reference)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Infrastructure Overview

### Nodes

| Host | IP | Role |
|---|---|---|
| R730 (shivelyserver) | 192.168.2.103 | GPU inference – Ollama, bmo-voice Docker |
| Wyse 5070 (control) | 192.168.2.102 | Control plane |
| Home Assistant | 192.168.2.100 | Smart home integration |
| Windows dev machine | 192.168.2.101 | Development, sandbox |
| Raspberry Pi (BMO) | (DHCP) | Wake-word satellite, face display |

### Services

| Service | Host:Port | Purpose |
|---|---|---|
| Ollama | 192.168.2.103:11434 | LLM inference (llama3.2:3b, qwen3:14b, …) |
| bmo-voice | 192.168.2.103:8100 | TTS (`/speak`) + STT (`/listen`) via Kokoro/RVC/Whisper |
| voice-engine | 192.168.2.103:8020 | Alternative STT endpoint |
| agent-runtime | 192.168.2.103:8008 | Main agent orchestrator |

### Complete Pipeline

```
User says "Hey Beemo"
        │
        ▼
[Raspberry Pi] voice_satellite.py
  └─ openwakeword (hey_beeMo.onnx) detects wake phrase
  └─ play_wake_ping()  →  chime (C6 → E6)
  └─ face: "acknowledged"
  └─ sd.rec() 3.8 s at 48 kHz → decimate 3× → 16 kHz
        │
        ▼ POST /listen (WAV)
[R730:8100] bmo-voice/server.py
  └─ faster-whisper medium.en → transcript text
        │
        ▼ POST /v1/voice/chat
[R730:8008] agent-runtime
  └─ Ollama LLM → BMO persona response text
        │
        ▼ detect_emotion() → pitch + speed
  Check voice_samples_map → pre-recorded clip match?
  ├─ YES → play_audio(sample_path)
  └─ NO  → POST /speak (text, pitch)
              └─ Kokoro TTS → RVC (bmo.pth / bmo.index) → WAV
        │
        ▼
[Raspberry Pi] aplay via HDMI
  └─ extract_mouth_sync_from_wav() → RMS envelope
  └─ pygame_face: emotion expression + mouth animation
  └─ reset to neutral
```

---

## 2. Sandbox – Quick Testing Without Hardware

`scripts/bmo_sandbox.py` exercises the full pipeline from a Windows terminal.
No Raspberry Pi required.

### Prerequisites

- Python 3.11: `C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe`
- `requests` package: `pip install requests --user`
- R730 reachable: 192.168.2.103

### Preflight Check

Always run preflight first to verify all services are up:

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py --host 192.168.2.103 --port 11434 --model llama3.2:3b `
  --preflight
```

Expected output:
```
  Ollama API          ✅ OK     http://192.168.2.103:11434
  Model llama3.2:3b   ✅ OK     available
  BMO Voice (TTS)     ✅ OK     http://192.168.2.103:8100
  Agent imports       ✅ OK     ok
  All critical services OK — sandbox is ready.
```

If BMO Voice shows ⚠️ WARN, the bmo-voice container is not running. See
[section 4](#4-bmo-voice-service--docker-container-on-r730).

### Single Prompt

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host 192.168.2.103 --port 11434 --model llama3.2:3b `
  --prompt "Hey BMO, who wants to play video games?"
```

Add `--tts` to also generate and save the audio response:

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host 192.168.2.103 --port 11434 --model llama3.2:3b `
  --tts --prompt "Hey BMO, say hello"
```

Audio is saved to `delivered_artifacts/`.

### Interactive Mode (REPL)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py --host 192.168.2.103 --port 11434 --model llama3.2:3b
```

REPL commands:

| Command | Effect |
|---|---|
| (type anything) | Full pipeline: sample match → LLM → emotion → optional TTS |
| `/emotion sad` | Force emotion for next response |
| `/sample hello` | Play a pre-recorded voice sample by key |
| `/prompt` | Multi-line prompt entry |
| `/quit` | Exit |

### Batch Mode

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host 192.168.2.103 --port 11434 --model llama3.2:3b `
  --batch tests/bmo_test_prompts.txt
```

One prompt per line in the batch file. Useful for regression testing.

### All CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--host` | 192.168.2.103 | Ollama host |
| `--port` | 11434 | Ollama port |
| `--model` | $BMO_LLM_MODEL or qwen3:14b | LLM model name |
| `--tts` | off | Enable TTS audio generation |
| `--tts-host` | same as --host | bmo-voice host |
| `--tts-port` | 8100 | bmo-voice port |
| `--prompt TEXT` | — | Single shot prompt |
| `--batch FILE` | — | Batch test file |
| `--preflight` | — | Check services and exit |

### Response Quality Warnings

The sandbox automatically warns about common BMO persona violations:

| Warning | Rule |
|---|---|
| Markdown / emojis detected | BMO never uses markdown or emoji |
| First-person pronoun | Should say "Beemo will…" not "I will…" |
| AI self-reference | Must never say "As an AI" or "language model" |
| Numeric digits | Must spell out: "twenty three" not "23" |
| "BMO" instead of "Beemo" | TTS engine pronounces "Beemo" correctly |
| Response > 300 chars | Too long for voice delivery |

---

## 3. Voice Operation – Raspberry Pi Satellite

`scripts/voice_satellite.py` (and the copy at `agents/bmo_voice/voice_satellite.py`)
runs on the Raspberry Pi.

### Key Configuration

Edit these constants at the top of `voice_satellite.py`:

```python
WAKE_WORD_MODELS = ["hey_beeMo"]   # Custom ONNX model name (no extension)
THRESHOLD        = 0.5             # Wake-word confidence threshold (0–1)
SAMPLE_RATE      = 16000           # Target rate for openwakeword
CHUNK_SIZE       = 1280            # 80 ms chunks at 16 kHz
POST_INTERACTION_COOLDOWN = 2.0    # Seconds to ignore BMO's own audio

# Network – read from environment or hardcoded fallback
HOST_IP          = os.getenv("LOVELACE_IP", "192.168.2.103")
VOICE_ENGINE_URL = f"http://{HOST_IP}:8020/stt"
AGENT_URL        = f"http://{HOST_IP}:8000/v1/voice/chat"
```

### Raspberry Pi Setup

```bash
# Install system packages
sudo apt update && sudo apt install -y \
  python3-pip python3-venv \
  portaudio19-dev libsndfile1 \
  espeak-ng

# Create project directory and venv
mkdir -p ~/bmo_client && cd ~/bmo_client
python3 -m venv venv
source venv/bin/activate

# Core dependencies
pip install sounddevice numpy requests openwakeword

# Copy files from dev machine
scp scripts/voice_satellite.py pi@<PI_IP>:~/bmo_client/
scp agents/bmo_voice/hey_beeMo.onnx pi@<PI_IP>:~/bmo_client/
```

### Running the Satellite

```bash
cd ~/bmo_client
source venv/bin/activate
python voice_satellite.py
```

BMO will print heartbeat logs every 5 seconds while waiting for the wake phrase.
Say **"Hey Beemo"** to trigger the interaction.

### Wake-Word Model Resolution

The satellite searches for `hey_beeMo.onnx` in this order:

1. Current working directory (where you launched the script)
2. The script's own directory (`scripts/` or `agents/bmo_voice/`)
3. Repository root (`~/bmo_client` or `~/Home_AI_Lab`)
4. `agents/bmo_voice/` relative to repo root

If not found, it falls back to the built-in `hey_jarvis_v0.1` model.

**Ensure `hey_beeMo.onnx` is co-located with `voice_satellite.py`.**

### Running as a Systemd Service

```bash
# Copy service file
sudo cp agents/bmo_voice/bmo_satellite.service /etc/systemd/system/

# Edit to set correct paths and LOVELACE_IP
sudo nano /etc/systemd/system/bmo_satellite.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable bmo_satellite
sudo systemctl start bmo_satellite

# Check status
sudo systemctl status bmo_satellite
journalctl -u bmo_satellite -f
```

### Face + Voice (Full BMO Experience)

Run `bmo_driver.py` for the complete animated face + voice pipeline:

```bash
python bmo_driver.py \
  --host 192.168.2.103 \
  --port 8100 \
  --pitch 3 \
  --output_device 1 \
  --volume 80
```

Key flags:

| Flag | Default | Description |
|---|---|---|
| `--host` | required | R730 IP (192.168.2.103) |
| `--port` | 8100 | bmo-voice port |
| `--input_device` | auto | ALSA mic device index |
| `--output_device` | auto | ALSA speaker device (name or index) |
| `--volume` | 80 | Speaker volume 0–100 |
| `--pitch` | 3 | TTS pitch offset (semitones) |
| `--method` | rmvpe | RVC pitch algorithm: rmvpe, crepe, harvest |

The pygame face renderer opens fullscreen at 1024×600 (set `SDL_VIDEODRIVER=kmsdrm`
for headless HDMI on Pi).

### HDMI Audio Setup (ALSA)

If BMO's audio output is silent, identify the correct HDMI device:

```bash
aplay -l
# Look for: card N: ... HDMI [...]

# Test playback
aplay -D plughw:N,0 /usr/share/sounds/alsa/Front_Left.wav
```

For software volume control, use the provided `asoundrc.example`:

```bash
cp agents/bmo_voice/asoundrc.example ~/.asoundrc
# Edit slave.pcm to match your card number
```

---

## 4. bmo-voice Service – Docker Container on R730

### Container Details

| Property | Value |
|---|---|
| Container name | `bmo_voice_gpu` |
| Image | `execution_plane-bmo-voice` |
| Port mapping | `8100 → 8000 (inside container)` |
| GPU | NVIDIA RTX 3070 Ti (all devices) |
| Models directory | `/app/models/` (mounted from `agents/bmo_voice/`) |

### Start / Stop

SSH to R730 and use the execution plane compose:

```bash
ssh misterobots@192.168.2.103   # password: jcknows1
cd ~/Home_AI_Lab/execution_plane

# Start
docker compose up -d bmo-voice

# Stop
docker compose stop bmo-voice

# Restart
docker compose restart bmo-voice

# Status
docker ps --filter name=bmo_voice_gpu
```

### Rebuild After Code Changes

```bash
cd ~/Home_AI_Lab/execution_plane
docker compose build bmo-voice
docker compose up -d bmo-voice
```

The build takes ~25 minutes on first run (large CUDA image). Subsequent builds
use the pip cache layer and take ~2 minutes for code-only changes.

### Container Logs

```bash
docker logs bmo_voice_gpu --tail=50
docker logs bmo_voice_gpu -f    # Follow live
```

### API Endpoints

#### `POST /speak`

Generate audio in BMO's voice.

```bash
curl -X POST http://192.168.2.103:8100/speak \
  -F "text=Beemo wants to play video games!" \
  -F "pitch=3" \
  -F "speed=1.15" \
  --output bmo_response.wav
```

Parameters:

| Parameter | Default | Description |
|---|---|---|
| `text` | required | Text to synthesize |
| `pitch` | 0 | Semitone shift (positive = higher) |
| `speed` | 1.0 | Speed multiplier |
| `method` | rmvpe | RVC pitch method: rmvpe, crepe, harvest |

Response: `audio/wav` binary.

#### `POST /listen`

Transcribe audio using Whisper.

```bash
curl -X POST http://192.168.2.103:8100/listen \
  -F "file=@recording.wav"
```

Response:
```json
{"text": "hey beemo who wants to play video games"}
```

#### `GET /health`

```bash
curl http://192.168.2.103:8100/health
```

### Required Model Files

The container expects these files in `agents/bmo_voice/models/`:

| File | Purpose |
|---|---|
| `models/bmo.pth` | RVC voice model weights |
| `models/bmo.index` | RVC feature index for voice texture |

If these are missing, `/speak` will raise HTTP 500. Whisper (`/listen`) and
preflight (`/health`) still work without them.

---

## 5. Testing Reference

### Preflight (Fastest)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py --host 192.168.2.103 --port 11434 `
  --model llama3.2:3b --preflight
```

### End-to-End LLM Test (No TTS)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py --host 192.168.2.103 --port 11434 `
  --model llama3.2:3b --prompt "Hey BMO, say hello"
```

### End-to-End TTS Test (Full Pipeline)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py --host 192.168.2.103 --port 11434 `
  --model llama3.2:3b --tts `
  --prompt "Hey BMO, who wants to play video games?"
```

### Sample Fast-Path Test

The sandbox checks `voice_samples_map.py` before hitting the LLM. These phrases
trigger pre-recorded clips directly:

| Phrase | Sample file |
|---|---|
| `hello` | `Intro02_Hello_ItsMeBEEMO.wav` |
| `who wants to play video games` | `General_Games01_whoWantsToPlayVideoGames.wav` |
| `victory` | `Player_Win07_VICTORY.wav` |
| `game over` | `Player_Lose09_GAMEOVER.wav` |
| `hahaha` | `Giggle01.wav` |

### Ollama Direct Test

Verify the LLM is reachable independently:

```bash
curl -s http://192.168.2.103:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"Say hello as BMO","stream":false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['response'])"
```

### bmo-voice Direct Test

```bash
curl -X POST http://192.168.2.103:8100/speak \
  -F "text=Beemo says hello!" \
  -F "pitch=3" \
  --output /tmp/bmo_test.wav
aplay /tmp/bmo_test.wav   # or play on Windows
```

### Whisper STT Test

```bash
# Record a test clip (5s)
arecord -d 5 -f cd /tmp/test_mic.wav

# Transcribe
curl -X POST http://192.168.2.103:8100/listen \
  -F "file=@/tmp/test_mic.wav"
```

### Monitor BMO State (UDP)

From any machine on the network, watch BMO face state changes:

```bash
python scripts/bmo_monitor.py
# Listens on UDP port 8123, prints color-coded state events
```

---

## 6. Troubleshooting

### Sandbox: Ollama Timeout on /api/chat

**Symptom:** `--prompt` hangs for 30 s then errors.

**Cause:** This Ollama deployment does not reliably serve `/api/chat`.

**Fix:** Already handled — `bmo_sandbox.py` automatically falls back to
`/api/generate`. If you see a 404 error from `/api/generate` too, the model
name is wrong.

```powershell
# List available models
curl http://192.168.2.103:11434/api/tags
```

---

### Sandbox: TTS ⚠️ WARN in Preflight

**Symptom:** Preflight shows `BMO Voice (TTS) ⚠️ WARN — connection refused`.

**Cause:** `bmo_voice_gpu` container is not running.

**Fix:**

```bash
ssh misterobots@192.168.2.103
cd ~/Home_AI_Lab/execution_plane
docker compose up -d bmo-voice
docker ps --filter name=bmo_voice_gpu
```

If the container exits immediately after starting, check logs:

```bash
docker logs bmo_voice_gpu --tail=30
```

---

### bmo-voice: HTTP 500 on /speak

**Symptom:** `curl /speak` returns 500.

**Causes and fixes:**

| Cause | Fix |
|---|---|
| `models/bmo.pth` not found | Copy RVC model to `agents/bmo_voice/models/` and rebuild |
| GPU OOM (other models loaded) | `docker compose stop` other GPU services, restart bmo-voice |
| PyTorch weights_only error | Already patched in server.py monkey-patch |

---

### Wake-Word: "Hey Beemo" Not Detected

**Symptom:** Satellite is running, heartbeat logs appear, but saying "Hey Beemo"
does nothing.

**Diagnosis steps:**

1. Check which model loaded:
   ```
   # Look for this line in satellite logs:
   Loaded wake-word models: ['hey_beemo']    ← custom model (correct)
   Loaded wake-word models: ['hey_jarvis']   ← fallback (wrong - model not found)
   ```

2. Verify model file location:
   ```bash
   ls ~/bmo_client/hey_beeMo.onnx   # Must exist in same dir as voice_satellite.py
   ```

3. Check prediction scores (add temporary debug print to `voice_satellite.py`):
   ```python
   # In the detection loop, temporarily add:
   print("scores:", normalized_scores)
   ```

4. If scores are consistently low (< 0.3), the model may not match the speaker.
   Lower the threshold or re-train.

**Fix:** Ensure `hey_beeMo.onnx` is in the working directory:

```bash
cp agents/bmo_voice/hey_beeMo.onnx ~/bmo_client/
```

---

### Wake-Word: False Positives (BMO Wakes Up Randomly)

**Symptom:** BMO triggers without anyone speaking the wake phrase.

**Fix:** Raise the threshold in `voice_satellite.py`:

```python
THRESHOLD = 0.65   # default 0.5 — increase for noisy environments
```

---

### Wake-Word: High Lag / Queue Backup

**Symptom:** Recognition takes several seconds; logs show `Q sizes: audio=7+`.

**Cause:** CPU overloaded on the Raspberry Pi. Check:

```bash
htop
```

**Fixes:**
- The satellite already uses decimation (`chunk[::3]`) instead of `scipy.resample`
  which is ~100× faster on ARM. If lag persists, reduce `CHUNK_SIZE`:
  ```python
  CHUNK_SIZE = 640   # 40ms chunks (tighter loop)
  ```
- Ensure no other heavy Python processes are running.

---

### Microphone: "Device is Busy" / Hangs on Open

**Symptom:**
```
ALSA Error or Busy Device: ...
```

**Fix:**

```bash
# Kill any leftover processes
pkill -f voice_satellite.py
pkill -f bmo_driver.py

# Check what is holding the device
lsof /dev/snd/*

# If still locked, reset the ALSA driver
sudo rmmod snd_usb_audio && sudo modprobe snd_usb_audio
```

---

### Audio: Input Overflow Warnings

**Symptom:**
```
Audio Status: input overflow
```

**Cause:** The Pi CPU cannot consume audio chunks fast enough. This is usually
harmless if occasional. Constant overflow means the CPU is saturated.

**Fix:** Already mitigated by `latency='high'` in the `InputStream`. If it
persists, lower `CHUNK_SIZE` to reduce per-chunk processing time.

---

### Audio Playback: Silence on HDMI

**Symptom:** `aplay` exits cleanly but no sound comes out of HDMI.

**Cause:** HDMI audio device not selected, or HDMI sink not initialized.

**Fix:**

```bash
# List audio devices
aplay -l

# Identify HDMI device (e.g., card 2, device 0)
# Test with explicit device
aplay -D plughw:2,0 /path/to/test.wav

# The satellite uses a 500ms silence pre-roll to wake HDMI sinks:
# Already implemented in play_audio() — if it's still silent,
# check TV/monitor is on the correct HDMI input.
```

---

### LLM: Response Fails Persona Quality Checks

The sandbox warns about persona violations. Common fixes:

| Warning | Likely cause | Fix |
|---|---|---|
| "First-person pronoun" | Model reverted to standard chat | Ensure system prompt is injected; try a different model |
| "Response > 300 chars" | Model being too verbose | Add "Keep responses to one or two sentences." to system prompt |
| "Markdown detected" | Model adding formatting | Reinforce "no markdown, no asterisks" in system prompt |
| "Numeric digits" | Model writing "5" not "five" | Add explicit rule to system prompt or post-process response |

The BMO system prompt is defined in `agents/specialized/bmo_persona.py`.
Temporary overrides can be tested interactively in the sandbox with `/prompt`.

---

### Container: Build Stalls at "#13 exporting layers"

**Symptom:** `docker compose build` appears frozen during image export.

**Cause:** Writing ~10 GB of CUDA image layers to disk. This is not a hang —
it produces no log output because BuildKit uses in-memory progress animation.

**Expected duration:** 15–25 minutes depending on disk speed.

**Verify it is still running (from a second SSH session):**

```bash
docker ps -a   # Build container should still appear
# OR
ls -la /var/lib/docker/overlay2/  # New directories appear as layers write
```

---

### Raspberry Pi Service: BMO Doesn't Start on Boot

**Check service status:**

```bash
sudo systemctl status bmo_satellite
journalctl -u bmo_satellite -n 50
```

**Common causes:**

| Cause | Fix |
|---|---|
| `LOVELACE_IP` not set | Add `Environment=LOVELACE_IP=192.168.2.103` to service file |
| venv path wrong | Check `ExecStart=` path in service file matches actual venv |
| Display not available | Ensure `SDL_VIDEODRIVER=kmsdrm` is set for headless Pi |
| Pi boots before network | Add `After=network-online.target` and `Wants=network-online.target` |

```bash
# After editing service file:
sudo systemctl daemon-reload
sudo systemctl restart bmo_satellite
```

---

## Appendix: Important File Locations

| File | Location | Purpose |
|---|---|---|
| Sandbox | `scripts/bmo_sandbox.py` | Windows test harness |
| Voice satellite | `scripts/voice_satellite.py` | Pi wake-word listener |
| BMO persona | `agents/specialized/bmo_persona.py` | System prompt + emotion triggers |
| Voice samples map | `agents/specialized/voice_samples_map.py` | Pre-recorded clip index |
| Server (TTS/STT) | `agents/bmo_voice/server.py` | FastAPI container entrypoint |
| Face renderer | `agents/bmo_voice/pygame_face.py` | Pygame animated face (Pi) |
| Driver (Pi) | `agents/bmo_voice/bmo_driver.py` | Full Pi voice+face driver |
| Custom wake model | `agents/bmo_voice/hey_beeMo.onnx` | OpenWakeWord ONNX model |
| Dockerfile | `agents/bmo_voice/Dockerfile` | CUDA 12.4.1 container build |
| Compose | `execution_plane/docker-compose.yml` | Service definitions on R730 |
| Delivered audio | `delivered_artifacts/` | Sandbox TTS output files |

## Appendix: Emotion Reference

| Emotion | Trigger keywords | Pitch shift | Speed |
|---|---|---|---|
| excited | !, yay, awesome, love, happy | +6 | 1.30× |
| happy | nice, good, wonderful, fun | +3 | 1.15× |
| sad | sad, sorry, bad news, oh no | −5 | 0.70× |
| surprised | whoa, wow, oh my, no way | +5 | 1.20× |
| sleeping | yawn, sleep, nap, dream | −6 | 0.60× |
| thinking | ?, hmm, wonder, what if | 0 | 0.90× |
| error | error, confused, broken, fail | −2 | 0.85× |
| neutral | (default) | 0 | 1.00× |
