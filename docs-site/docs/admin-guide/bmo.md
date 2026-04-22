---
title: BMO Complete Guide
---

# BMO Complete Guide

BMO is an animated robot companion inspired by *Adventure Time*. It runs a full
voice pipeline: wake-word detection on a Raspberry Pi → speech-to-text →
LLM response (Ollama) → emotion-aware TTS + RVC voice conversion → animated
face.

---

## Infrastructure Overview

### Nodes

| Host | IP | Role |
|---|---|---|
| R730 (shivelyserver) | `{{ gateway_node_ip }}` | GPU inference — Ollama, bmo-voice Docker |
| Wyse 5070 (control) | `{{ control_node_ip }}` | Control plane |
| Home Assistant | `{{ home_assistant_ip }}` | Smart home integration |
| Raspberry Pi (BMO) | DHCP | Wake-word satellite, face display |

### Services

| Service | URL | Purpose |
|---|---|---|
| Ollama | `{{ gateway_node_ip }}:{{ ollama_port }}` | LLM inference |
| bmo-voice | `{{ gateway_node_ip }}:8100` | TTS (`/speak`) + STT (`/listen`) |
| agent-runtime | `{{ gateway_node_ip }}:{{ agent_runtime_port }}` | Main agent orchestrator |

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
        ▼  POST /listen (WAV)
[R730:8100] bmo-voice/server.py
  └─ faster-whisper medium.en → transcript text
        │
        ▼  POST /v1/voice/chat
[R730:8008] agent-runtime
  └─ Ollama LLM → BMO persona response text
        │
        ▼  detect_emotion() → pitch + speed
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

## Sandbox – Quick Testing Without Hardware

`scripts/bmo_sandbox.py` exercises the full pipeline from a Windows terminal.
No Raspberry Pi required.

### Prerequisites

- Python 3.11: `C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe`
- `requests` package: `pip install requests --user`
- R730 reachable at `{{ gateway_node_ip }}`

### Preflight Check

Always run preflight first to verify all services are up:

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --preflight
```

Expected output:

```
  Ollama API          ✅ OK     http://{{ gateway_node_ip }}:{{ ollama_port }}
  Model llama3.2:3b   ✅ OK     available
  BMO Voice (TTS)     ✅ OK     http://{{ gateway_node_ip }}:8100
  Agent imports       ✅ OK     ok
  All critical services OK — sandbox is ready.
```

!!! warning "BMO Voice shows ⚠️ WARN"
    The `bmo_voice_gpu` container is not running. See
    [bmo-voice Service](#bmo-voice-service--docker-container) below.

### Single Prompt

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --prompt "Hey BMO, who wants to play video games?"
```

Add `--tts` to also generate and save the audio response (saved to `delivered_artifacts/`):

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --tts --prompt "Hey BMO, say hello"
```

### Interactive Mode (REPL)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b
```

REPL commands:

| Command | Effect |
|---|---|
| *(type anything)* | Full pipeline: sample match → LLM → emotion → optional TTS |
| `/emotion sad` | Force emotion for next response |
| `/sample hello` | Play a pre-recorded voice sample by key |
| `/prompt` | Multi-line prompt entry |
| `/quit` | Exit |

### Batch Mode

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --batch tests/bmo_test_prompts.txt
```

### CLI Flags Reference

| Flag | Default | Description |
|---|---|---|
| `--host` | `{{ gateway_node_ip }}` | Ollama host |
| `--port` | `{{ ollama_port }}` | Ollama port |
| `--model` | `$BMO_LLM_MODEL` or `qwen3:14b` | LLM model name |
| `--tts` | off | Enable TTS audio generation |
| `--tts-host` | same as `--host` | bmo-voice host |
| `--tts-port` | `8100` | bmo-voice port |
| `--prompt TEXT` | — | Single-shot prompt |
| `--batch FILE` | — | Batch test file |
| `--preflight` | — | Check services and exit |

### Response Quality Warnings

The sandbox automatically warns about BMO persona violations:

| Warning | Rule |
|---|---|
| Markdown / emojis detected | BMO never uses markdown or emoji |
| First-person pronoun | Should say "Beemo will…" not "I will…" |
| AI self-reference | Must never say "As an AI" or "language model" |
| Numeric digits | Must spell out: "twenty three" not "23" |
| "BMO" instead of "Beemo" | TTS engine pronounces "Beemo" correctly |
| Response > 300 chars | Too long for voice delivery |

---

## Voice Operation – Raspberry Pi Satellite

`scripts/voice_satellite.py` runs on the Raspberry Pi.

### Key Configuration

Edit these constants at the top of `voice_satellite.py`:

```python
WAKE_WORD_MODELS = ["hey_beeMo"]    # Custom ONNX model name (no extension)
THRESHOLD        = 0.5              # Wake-word confidence (0–1)
SAMPLE_RATE      = 16000            # Target rate for openwakeword
CHUNK_SIZE       = 1280             # 80 ms chunks at 16 kHz
POST_INTERACTION_COOLDOWN = 2.0     # Seconds to ignore BMO's own audio

HOST_IP          = os.getenv("LOVELACE_IP", "{{ gateway_node_ip }}")
VOICE_ENGINE_URL = f"http://{HOST_IP}:8020/stt"
AGENT_URL        = f"http://{HOST_IP}:8000/v1/voice/chat"
```

### Raspberry Pi Setup

```bash
# System packages
sudo apt update && sudo apt install -y \
  python3-pip python3-venv portaudio19-dev libsndfile1 espeak-ng

# Project directory and venv
mkdir -p ~/bmo_client && cd ~/bmo_client
python3 -m venv venv
source venv/bin/activate

pip install sounddevice numpy requests openwakeword

# Copy files from dev machine
scp scripts/voice_satellite.py misterobots@<PI_IP>:~/bmo_client/
scp agents/bmo_voice/hey_beeMo.onnx misterobots@<PI_IP>:~/bmo_client/
```

### Running the Satellite

```bash
cd ~/bmo_client
source venv/bin/activate
python voice_satellite.py
```

BMO prints heartbeat logs every 5 seconds while waiting. Say **"Hey Beemo"**
to trigger the interaction.

### Wake-Word Model Resolution

The satellite searches for `hey_beeMo.onnx` in this order:

1. Current working directory
2. The script's own directory
3. Repository root
4. `agents/bmo_voice/` relative to repo root

!!! warning "Fallback model"
    If `hey_beeMo.onnx` is not found, the satellite silently falls back to
    `hey_jarvis_v0.1`. Check satellite logs for the loaded model name and ensure
    `hey_beeMo.onnx` is co-located with `voice_satellite.py`.

### Running as a Systemd Service

```bash
sudo cp agents/bmo_voice/bmo_satellite.service /etc/systemd/system/
sudo nano /etc/systemd/system/bmo_satellite.service   # set LOVELACE_IP and paths

sudo systemctl daemon-reload
sudo systemctl enable bmo_satellite
sudo systemctl start bmo_satellite

# Check
sudo systemctl status bmo_satellite
journalctl -u bmo_satellite -f
```

### Full BMO Experience (Face + Voice)

Run `bmo_driver.py` for the animated face + voice pipeline:

```bash
python bmo_driver.py \
  --host {{ gateway_node_ip }} \
  --port 8100 \
  --pitch 3 \
  --output_device 1 \
  --volume 80
```

| Flag | Default | Description |
|---|---|---|
| `--host` | required | R730 IP |
| `--port` | `8100` | bmo-voice port |
| `--input_device` | auto | ALSA mic device index |
| `--output_device` | auto | ALSA speaker (name or index) |
| `--volume` | `80` | Speaker volume 0–100 |
| `--pitch` | `3` | TTS pitch offset (semitones) |
| `--method` | `rmvpe` | RVC pitch algorithm: `rmvpe`, `crepe`, `harvest` |

!!! tip "Headless Pi display"
    Set `SDL_VIDEODRIVER=kmsdrm` for native HDMI framebuffer (no X11 needed).

### HDMI Audio Setup

```bash
aplay -l                               # Find the HDMI card number N
aplay -D plughw:N,0 <test.wav>         # Verify playback

# Soft volume (optional) — edit slave.pcm to match card number
cp agents/bmo_voice/asoundrc.example ~/.asoundrc
```

---

## bmo-voice Service – Docker Container

### Container Details

| Property | Value |
|---|---|
| Container name | `bmo_voice_gpu` |
| Port mapping | `8100 → 8000` |
| GPU | NVIDIA RTX 3070 Ti (all devices) |
| Model files | `agents/bmo_voice/models/` |

### Start / Stop

```bash
ssh misterobots@{{ gateway_node_ip }}
cd ~/Home_AI_Lab/execution_plane

docker compose up -d bmo-voice          # Start
docker compose stop bmo-voice           # Stop
docker compose restart bmo-voice        # Restart
docker ps --filter name=bmo_voice_gpu   # Status
```

### Rebuild After Code Changes

```bash
cd ~/Home_AI_Lab/execution_plane
docker compose build bmo-voice
docker compose up -d bmo-voice
```

!!! info "First build time"
    The first build takes ~25 minutes (large CUDA image). Subsequent
    code-only rebuilds take ~2 minutes (pip cache layer is preserved).

### Container Logs

```bash
docker logs bmo_voice_gpu --tail=50
docker logs bmo_voice_gpu -f
```

### API Reference

=== "POST /speak"

    Generate audio in BMO's voice.

    ```bash
    curl -X POST http://{{ gateway_node_ip }}:8100/speak \
      -F "text=Beemo wants to play video games!" \
      -F "pitch=3" \
      -F "speed=1.15" \
      --output bmo_response.wav
    ```

    | Parameter | Default | Description |
    |---|---|---|
    | `text` | required | Text to synthesize |
    | `pitch` | `0` | Semitone shift (positive = higher) |
    | `speed` | `1.0` | Speed multiplier |
    | `method` | `rmvpe` | RVC pitch: `rmvpe`, `crepe`, `harvest` |

    Response: `audio/wav` binary.

=== "POST /listen"

    Transcribe audio using Whisper.

    ```bash
    curl -X POST http://{{ gateway_node_ip }}:8100/listen \
      -F "file=@recording.wav"
    ```

    Response:
    ```json
    {"text": "hey beemo who wants to play video games"}
    ```

=== "GET /health"

    ```bash
    curl http://{{ gateway_node_ip }}:8100/health
    ```

### Required Model Files

The container expects these files in `agents/bmo_voice/models/`:

| File | Purpose |
|---|---|
| `models/bmo.pth` | RVC voice model weights |
| `models/bmo.index` | RVC feature index |

!!! danger "Missing models"
    If these files are absent, `/speak` returns HTTP 500.
    `/listen` and `/health` still work without them.

---

## Testing Reference

### Preflight (Fastest — use this first)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --preflight
```

### LLM-Only Test (No TTS)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --prompt "Hey BMO, say hello"
```

### Full Pipeline Test (TTS enabled)

```powershell
& "C:\Users\panca\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/bmo_sandbox.py `
  --host {{ gateway_node_ip }} --port {{ ollama_port }} --model llama3.2:3b `
  --tts --prompt "Hey BMO, who wants to play video games?"
```

### Pre-Recorded Sample Fast-Path

These phrases bypass the LLM and play a pre-recorded clip directly:

| Phrase | Sample file |
|---|---|
| `hello` | `Intro02_Hello_ItsMeBEEMO.wav` |
| `who wants to play video games` | `General_Games01_whoWantsToPlayVideoGames.wav` |
| `victory` | `Player_Win07_VICTORY.wav` |
| `game over` | `Player_Lose09_GAMEOVER.wav` |
| `hahaha` | `Giggle01.wav` |

### Direct Ollama Test

```bash
curl -s http://{{ gateway_node_ip }}:{{ ollama_port }}/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"Say hello as BMO","stream":false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['response'])"
```

### Direct bmo-voice Test

```bash
curl -X POST http://{{ gateway_node_ip }}:8100/speak \
  -F "text=Beemo says hello!" -F "pitch=3" \
  --output /tmp/bmo_test.wav
aplay /tmp/bmo_test.wav
```

### Monitor BMO State (UDP)

```bash
python scripts/bmo_monitor.py
# Listens on UDP port 8123, prints colour-coded state events
```

---

## Troubleshooting

### Sandbox: Ollama Timeout

**Symptom:** `--prompt` hangs for 30 s then errors.

The sandbox automatically falls back from `/api/chat` to `/api/generate`. If
both fail, verify the model name:

```bash
curl http://{{ gateway_node_ip }}:{{ ollama_port }}/api/tags
```

---

### Sandbox: TTS ⚠️ WARN in Preflight

**Cause:** `bmo_voice_gpu` container is not running.

```bash
ssh misterobots@{{ gateway_node_ip }}
cd ~/Home_AI_Lab/execution_plane
docker compose up -d bmo-voice
docker ps --filter name=bmo_voice_gpu
```

If it exits immediately, check logs:

```bash
docker logs bmo_voice_gpu --tail=30
```

---

### bmo-voice: HTTP 500 on /speak

| Cause | Fix |
|---|---|
| `models/bmo.pth` not found | Copy RVC model to `agents/bmo_voice/models/` and rebuild |
| GPU OOM | Stop other GPU containers, restart bmo-voice |
| PyTorch weights_only error | Already patched — rebuild image to pick up latest server.py |

---

### Wake-Word: "Hey Beemo" Not Detected

**Diagnosis:**

```
# Correct (custom model loaded):
Loaded wake-word models: ['hey_beemo']

# Wrong (fallback — model file missing):
Loaded wake-word models: ['hey_jarvis']
```

**Fix:**

```bash
# Ensure model is in the working directory
cp agents/bmo_voice/hey_beeMo.onnx ~/bmo_client/
```

---

### Wake-Word: False Positives

Raise the threshold in `voice_satellite.py`:

```python
THRESHOLD = 0.65   # default 0.5
```

---

### Wake-Word: High Lag / Queue Backup

**Symptom:** Logs show `Q sizes: audio=7+`.

The satellite already uses decimation (`chunk[::3]`) instead of `scipy.resample`
(~100× faster on ARM). If lag persists, reduce chunk size:

```python
CHUNK_SIZE = 640   # 40 ms chunks
```

---

### Microphone: "Device is Busy"

```bash
pkill -f voice_satellite.py
pkill -f bmo_driver.py
lsof /dev/snd/*

# Hard reset if still locked:
sudo rmmod snd_usb_audio && sudo modprobe snd_usb_audio
```

---

### Audio Playback: Silence on HDMI

```bash
aplay -l                              # Find HDMI card number N
aplay -D plughw:N,0 /usr/share/sounds/alsa/Front_Left.wav   # Test
```

The satellite already sends a 500 ms silence pre-roll to wake HDMI sinks.
If it remains silent, confirm the TV/monitor is on the correct HDMI input.

---

### Container: Build Stalls at "#13 exporting layers"

!!! info "Not a hang"
    This step writes ~10 GB of CUDA image layers to disk and produces no
    terminal output (BuildKit uses in-memory progress spinners). Expected
    duration: **15–25 minutes**.

Verify from a second SSH session:

```bash
docker ps -a       # Build container still listed
ls -la /var/lib/docker/overlay2/   # New directories appear as layers write
```

---

### Raspberry Pi Service: BMO Doesn't Start on Boot

```bash
sudo systemctl status bmo_satellite
journalctl -u bmo_satellite -n 50
```

| Cause | Fix |
|---|---|
| `LOVELACE_IP` not set | Add `Environment=LOVELACE_IP={{ gateway_node_ip }}` to service file |
| venv path wrong | Check `ExecStart=` path matches actual venv location |
| Display unavailable | Set `SDL_VIDEODRIVER=kmsdrm` in service environment |
| Pi boots before network | Add `After=network-online.target` to `[Unit]` |

```bash
sudo systemctl daemon-reload
sudo systemctl restart bmo_satellite
```

---

## Reference

### Important File Locations

| File | Path | Purpose |
|---|---|---|
| Sandbox | `scripts/bmo_sandbox.py` | Windows test harness |
| Voice satellite | `scripts/voice_satellite.py` | Pi wake-word listener |
| BMO persona | `agents/specialized/bmo_persona.py` | System prompt + emotion triggers |
| Voice samples map | `agents/specialized/voice_samples_map.py` | Pre-recorded clip index |
| Server (TTS/STT) | `agents/bmo_voice/server.py` | FastAPI container entrypoint |
| Face renderer | `agents/bmo_voice/pygame_face.py` | Pygame animated face |
| Driver (Pi) | `agents/bmo_voice/bmo_driver.py` | Full Pi voice+face driver |
| Custom wake model | `agents/bmo_voice/hey_beeMo.onnx` | OpenWakeWord ONNX model |
| Dockerfile | `agents/bmo_voice/Dockerfile` | CUDA 12.4.1 container build |
| Compose | `execution_plane/docker-compose.yml` | Service definitions on R730 |
| Delivered audio | `delivered_artifacts/` | Sandbox TTS output files |

### Emotion Reference

| Emotion | Trigger keywords | Pitch | Speed |
|---|---|---|---|
| excited | !, yay, awesome, love, happy | +6 st | 1.30× |
| happy | nice, good, wonderful, fun | +3 st | 1.15× |
| sad | sad, sorry, bad news, oh no | −5 st | 0.70× |
| surprised | whoa, wow, oh my, no way | +5 st | 1.20× |
| sleeping | yawn, sleep, nap, dream | −6 st | 0.60× |
| thinking | ?, hmm, wonder, what if | 0 | 0.90× |
| error | error, confused, broken, fail | −2 st | 0.85× |
| neutral | *(default)* | 0 | 1.00× |
