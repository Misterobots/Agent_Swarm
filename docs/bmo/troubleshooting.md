# BMO Voice Assistant — Troubleshooting

## Quick Diagnostics

Run these checks first to narrow down the issue:

```bash
# 1. Are all services running?
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
# Expected: agent_runtime, bmo_voice_gpu, ollama — all "Up"

# 2. Is Ollama loaded with the correct model?
curl http://localhost:11434/api/ps
# Should show qwen3.5:9b loaded

# 3. Can the agent-runtime reach Ollama?
docker exec agent_runtime curl -s http://ollama:11434/api/tags | head -5

# 4. Is the BMO voice engine healthy?
curl http://localhost:8100/health

# 5. Is PostgreSQL reachable from the agent?
docker exec agent_runtime python3 -c "
from specialized.bmo_memory import get_recent_messages
print('DB OK' if get_recent_messages('test') is not None else 'DB FAIL')
"
```

## Common Issues

### BMO Doesn't Respond to Wake Word

**Symptom**: Saying "Hey BMO" produces no reaction.

**Checks**:
1. Verify the satellite is running and in IDLE state (`voice_satellite_v2.py` logs).
2. Check microphone detection:
   ```bash
   # On the Pi
   arecord -l
   # Should list a USB capture device
   ```
3. Confirm the wake word model exists:
   ```bash
   ls ~/Home_AI_Lab/scripts/hey_beeMo.onnx
   ```
4. Lower the wake threshold if detection is too strict — edit `WAKE_THRESHOLD = 0.5` in `voice_satellite_v2.py` (try 0.4).
5. Check that `openwakeword` is installed: `pip3 show openwakeword`.

### BMO Hears Me But Doesn't Respond

**Symptom**: Wake word detected, recording happens, but no response comes back.

**Checks**:
1. Check satellite logs for HTTP errors to the agent API.
2. Verify network connectivity from Pi to execution node:
   ```bash
   curl http://192.168.2.101:8008/health
   curl http://192.168.2.101:8100/health
   ```
3. Check if Whisper STT is working:
   ```bash
   # Test STT directly
   curl -X POST http://192.168.2.101:8100/listen \
     -F "file=@test_audio.wav"
   ```
4. Check agent-runtime logs:
   ```bash
   docker logs agent_runtime --tail 50
   ```
5. If you see `DB unavailable, running without persistent memory` — PostgreSQL is unreachable. BMO still works but without memory. Check `AGNO_DB_URL` and PostgreSQL health on the control node.

### Audio Playback Has Static or Distortion

**Symptom**: BMO's voice has crackling, hissing, or static noise.

**Cause**: Sample rate or format mismatch between the generated WAV and HDMI audio.

**Fix**:
1. The voice pipeline resamples to 44100 Hz, 16-bit PCM mono. Verify:
   ```bash
   # Check a generated file
   soxi /workspace/delivered_artifacts/voice_clone_*.wav
   # Should show: 44100 Hz, 16-bit, Mono
   ```
2. Check HDMI device detection:
   ```bash
   aplay -l
   # Note the card and device numbers for HDMI
   ```
3. If using a USB sound card, the satellite's `detect_hdmi_device()` may pick the wrong one. Set the device manually in `voice_satellite_v2.py`.

### BMO Responds With Text But No Audio

**Symptom**: The agent returns text content but `audio_path` is `None`.

**Checks**:
1. Check GPU availability — the RVC model needs CUDA:
   ```bash
   docker exec bmo_voice_gpu nvidia-smi
   ```
2. Check if another service holds the GPU lock:
   ```bash
   docker exec agent_runtime python3 -c "
   from utils.gpu_queue import get_redis_client
   c = get_redis_client()
   print('Lock:', c.get('swarm_gpu_lock'))
   print('Zone:', c.get('swarm_gpu_zone'))
   "
   ```
3. If the lock is held by a stale process, clear it:
   ```bash
   docker exec agent_runtime python3 -c "
   from utils.gpu_queue import get_redis_client
   c = get_redis_client()
   c.delete('swarm_gpu_lock')
   print('Lock cleared')
   "
   ```
4. Check voice engine logs:
   ```bash
   docker logs bmo_voice_gpu --tail 30
   ```
5. If RVC models are missing:
   ```bash
   docker exec bmo_voice_gpu ls /app/models/
   # Should contain bmo.pth and bmo.index
   ```

### BMO Doesn't Remember Previous Conversations

**Symptom**: BMO doesn't recall facts or past sessions.

**Checks**:
1. Verify PostgreSQL connectivity:
   ```bash
   psql -h 192.168.2.102 -U agno -d agno_memory -c "SELECT COUNT(*) FROM bmo_conversations;"
   ```
2. Check if `MEMORY_AVAILABLE` was set to False. Look for this in agent-runtime logs:
   ```
   DB unavailable, running without persistent memory
   ```
3. Verify the `AGNO_DB_URL` environment variable is set correctly in `docker-compose.yml`.
4. Check if cleanup is too aggressive (default: 30 days). Session summaries and user profiles are permanent, but raw messages expire.

### BMO's Personality Seems Generic

**Symptom**: Responses don't sound like BMO, or feel like a generic assistant.

**Checks**:
1. Verify the correct model is loaded:
   ```bash
   curl http://localhost:11434/api/ps
   # Should show qwen3.5:9b — not a smaller model
   ```
2. Smaller models (qwen2.5:3b) struggle to maintain character. The system prompt is tuned for qwen3.5:9b.
3. Check that the system prompt in `voice_assistant.py` hasn't been accidentally truncated.
4. Verify mood hints are being injected — enable DEBUG logging:
   ```python
   logger.setLevel(logging.DEBUG)
   ```

### Barge-In Doesn't Work

**Symptom**: You can't interrupt BMO while it's speaking.

**Checks**:
1. The barge-in monitor requires the microphone to be active during SPEAKING state.
2. Verify the VAD threshold is detecting your speech:
   ```bash
   # Test VAD locally on the Pi
   python3 -c "
   import torch
   model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
   print('VAD loaded OK')
   "
   ```
3. The detection window is 240ms (15 consecutive speech frames). If your environment is noisy, background noise may already be triggering false positives, or the threshold may need adjustment.
4. Ensure `aplay` is being used as a subprocess (not a blocking call) — check that `play_audio()` uses `subprocess.Popen`.

### GPU Lock Timeout Errors

**Symptom**: Logs show `[Voice Cloning] GPU lock timeout — cannot generate voice`.

**Cause**: Another process (ComfyUI, image generation, etc.) holds the GPU lock for longer than 30 seconds.

**Fixes**:
1. Check what's holding the lock:
   ```bash
   docker exec agent_runtime python3 -c "
   from utils.gpu_queue import get_redis_client
   c = get_redis_client()
   print('Lock holder:', c.get('swarm_gpu_lock'))
   print('Current zone:', c.get('swarm_gpu_zone'))
   "
   ```
2. If ComfyUI is generating a large image, wait for it to finish.
3. For persistent issues, increase the voice lock timeout in `voice_cloning.py`:
   ```python
   with request_lock("voice", timeout=60):
   ```
4. Clear a stale lock (if the holder crashed):
   ```bash
   docker exec agent_runtime python3 -c "
   from utils.gpu_queue import get_redis_client
   c = get_redis_client(); c.delete('swarm_gpu_lock'); print('Cleared')
   "
   ```

### Docker Build Fails for bmo-voice

**Symptom**: `docker compose build bmo-voice` fails.

**Common causes**:
1. **PyTorch nightly URL changed** — The Dockerfile pins a CUDA 12.8 nightly wheel. Check [PyTorch nightly](https://download.pytorch.org/whl/nightly/cu128) for current URLs.
2. **espeak-ng not found** — Ensure `espeak-ng` and `espeak-ng-data` are in the `apt-get install` line.
3. **CUDA version mismatch** — The base image is `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`. Your driver must support CUDA 12.4+.

### Satellite Can't Find network.env

**Symptom**: `voice_satellite_v2.py` fails to find the execution node IP.

The satellite searches for `network.env` in:
1. Same directory as the script
2. Parent directory (`../network.env`)
3. `/workspace/network.env` (Docker mount)

**Fix**: Either place `network.env` in the scripts directory or set `EXECUTION_NODE_IP` as an environment variable:
```bash
export EXECUTION_NODE_IP=192.168.2.101
python3 voice_satellite_v2.py
```

## Log Locations

| Component | How to Access |
|-----------|---------------|
| agent-runtime | `docker logs agent_runtime` |
| bmo-voice | `docker logs bmo_voice_gpu` |
| ollama | `docker logs ollama` |
| voice satellite | Terminal output (stdout/stderr) |
| PostgreSQL | `docker logs postgres` or `/var/log/postgresql/` on control node |

## Health Check Endpoints

| Service | URL | Expected |
|---------|-----|----------|
| agent-runtime | `http://192.168.2.101:8008/health` | `200 OK` |
| bmo-voice | `http://192.168.2.101:8100/health` | `200 OK` |
| ollama | `http://192.168.2.101:11434/api/tags` | JSON with model list |
| Home Assistant | `http://192.168.2.100:8123/api/` | `{"message": "API running."}` |
