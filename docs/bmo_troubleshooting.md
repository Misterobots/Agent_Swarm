# BMO Voice Satellite Troubleshooting Guide

This document outlines known issues, symptoms, and fixes for the BMO Voice Satellite (`voice_satellite.py`), specifically running on low-resource ARM hardware like a Raspberry Pi.

---

## 1. Microphone Fails to Open / "Device is Busy"

**Symptom:**

```text
🛠️ DEBUG: Attempting to open sd.InputStream (This may hang if device is busy)...
🛠️ DEBUG: ALSA Error or Busy Device: ...
```

**Cause:**
ALSA (Advanced Linux Sound Architecture) only allows one application to use a microphone device at a time natively unless `dsnoop` is configured. If another script (like `bmo_driver.py` testing the mic or an old ghost process of `voice_satellite.py`) is holding the device open, `sounddevice` will fail or hang.

**Fix:**

1. **Kill zombie processes:** Find and kill any hung Python processes holding the mic.
   ```bash
   pkill -f voice_satellite.py
   pkill -f bmo_driver.py
   ```
2. **Check active audio users:**
   ```bash
   lsof /dev/snd/*
   ```
3. **Hardware reset:** Unplug and re-plug the USB microphone if the ALSA driver state is completely locked.

---

## 2. "Input Overflow" Warnings

**Symptom:**

```text
Audio Status: input overflow
```

**Cause:**
This means the microphone is capturing audio faster than the Python script can process it. The internal audio ring buffer fills up and drops frames. This is very common on Raspberry Pis when the CPU spikes.

**Fix (Implemented in Code):**

- **ALSA latency:** Set `latency='high'` in `sd.InputStream` to allocate a larger underlying buffer.
- **If it persists:** It's usually harmless if it happens occasionally. If it's constant, the CPU is overwhelmed. Check what else is running on the Pi via `htop`.

---

## 3. High CPU Usage / Wake Word Lag

**Symptom:**
Wake word takes several seconds to recognize, or `audio_queue` backs up (`Q sizes: audio=7...`).

**Cause:**
The openwakeword model expects 16,000Hz audio, but the hardware mic runs at 48,000Hz. Previously, using `scipy.signal.resample` to downsample live audio on a Raspberry Pi CPU caused massive lag.

**Fix (Implemented in Code):**

- **Decimation over Resampling:** We use simple array slicing (`processed_chunk = chunk[::3]`) instead of FFT-based resampling to convert 48kHz to 16kHz. This is ~100x faster on ARM.
- **Queue clearing:** If the queue backs up too much (> 5 chunks), the script drops old frames to catch up to real-time.

---

## 4. Fake Wake Word Activations (False Positives)

**Symptom:**
BMO wakes up when no one said "Hey BMO".

**Cause:**
The default `THRESHOLD = 0.5` in `voice_satellite.py` might be too low for your environment's ambient noise.

**Fix:**
Open `voice_satellite.py` and increase the threshold:

```python
THRESHOLD = 0.65  # Increase from 0.5 if it triggers too easily
```

---

## 5. Agent "Internal Server Error" after Wake Word

**Symptom:**
The wake word works, STT transcribes correctly, but the agent responds with:

```text
Agent Error: Internal Server Error
```

**Cause:**
The AI backend (Ollama / Home AI Lab server) failed to process the request. The most common cause is **VRAM Out-of-Memory (OOM)** on the server GPU when trying to load a large LLM while ComfyUI or other models are active.

**Fix:**

1. Ensure the BMO model in the server's `.env` specifies a small, fast model that fits in remaining VRAM alongside ComfyUI.
   ```env
   # In execution_plane/.env
   BMO_LLM_MODEL=qwen2.5:3b  # ~1.9GB, excellent for tool calling
   ```
2. Restart the agent runtime on the server:
   ```bash
   docker restart agent_runtime
   ```

---

## 6. No Audio Output or "aplay error"

**Symptom:**
Agent responds with text, but no audio plays, or you see `aplay error`.

**Cause:**
The script tries to auto-detect the HDMI audio out (`vc4-hdmi`). If the TV/monitor is off, asleep, or disconnected, ALSA might lose the device node.

**Fix:**

1. Ensure the HDMI monitor/speaker is powered on.
2. The script will automatically fall back to the ALSA `default` device if the specific direct hardware device fails. If `default` is also wrong, check `aplay -l` to find the correct card and update `PLAYBACK_DEVICE` in the script.

---

## 7. Troubleshooting Mic Input (Capture)

**Symptom:**
The script runs without crashing, but the wake word is never detected, or the STT constantly returns "No speech detected."

**Cause:**
The microphone is either physically muted, claimed by the wrong ALSA device index, or not capturing at the expected hardware rate (48000Hz).

**Fix:**

1. **Check recognized capture devices:**
   ```bash
   arecord -l
   ```
2. The script auto-detects USB mics. If it fails, you can hardcode `MIC_DEVICE = (number)` in `voice_satellite.py` using the index from the command above.
3. Test recording raw audio outside the script:
   ```bash
   arecord -D hw:1,0 -d 5 -f S16_LE -c1 -r48000 test.wav
   ```
   _(Change `hw:1,0` to your actual mic card/device number)._ Play back `test.wav` to ensure the mic isn't broken.
4. **Check Mic Gain (Volume is too high/low):**
   If the mic works but the wake word triggers randomly or captures static, the gain might be maxed out. Open `alsamixer -c (card_number)`, press `F4`, and lower the capture volume from 100 to ~50-70. Save with `sudo alsactl store`.

---

## 8. HDMI Audio "Goes to Sleep" (Beginning of Audio is Cut Off)

**Symptom:**
BMO speaks, but the first 1-2 seconds of the sentence are missing. You only hear the end of the audio.

**Cause:**
Modern HDMI TVs and AV Receivers go into an energy-saving "sleep" mode when the audio stream stops. When BMO starts speaking, the ALSA stream opens, but the receiver takes 1-2 seconds to "wake up" and decode the audio, "swallowing" the beginning of the sentence.

**Fix (Implemented in Code):**

- **The Silence Pre-Roll:** `voice_satellite.py` automatically generates a 1.2-second silent WAV file (`/tmp/silence.wav`) and passes it to `aplay` _before_ the actual BMO snippet.
- **How it works:** `aplay silence.wav bmo_speech.wav`. This forces the TV to wake up during the silent file, so by the time the actual BMO audio starts playing, the receiver is fully active and you hear the entire sentence.

---

## 8. Troubleshooting Speaker Output (Playback)

**Symptom:**
The script plays audio (no errors printed), but it is completely silent, distorted, or too quiet to hear.

**Cause:**
ALSA mixer volumes are muted or near 0%, or the display (e.g., HDMI TV) has its physical volume down.

**Fix:**

1. Check physical knobs and TV remotes first.
2. Open the ALSA hardware mixer:

   ```bash
   alsamixer
   ```

   - Press `F6` to select your sound card (e.g., `vc4-hdmi` for the Raspberry Pi).
   - Ensure bars are green/high. If it says `MM` at the bottom, the channel is muted — press the `m` key to toggle it to `00`.

3. Test raw playback of a system sound:
   ```bash
   aplay /usr/share/sounds/alsa/Front_Center.wav
   ```

---

## 9. Troubleshooting Wakeword Detection (General)

**Symptom:**
Mic captures fine (checked via `arecord`), but saying "Hey BMO" never triggers it.

**Cause:**
Distance, reverb, model string mismatches, or the confidence threshold is too strict.

**Fix:**

1. Check the logs for: `Model Loaded: ['hey_beeMo.onnx']`
   If it fell back to Jarvis, the `.onnx` file is missing from the directory where you ran the script.
2. The wake word library needs clear audio. Move closer (within 1-2 meters) or point the mic directly at you to rule out room acoustics.
3. If it's too strict for your voice, lower the confidence threshold slightly in `voice_satellite.py`:
   ```python
   THRESHOLD = 0.4  # Lowered from 0.5 to make it more sensitive
   ```

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `voice_satellite.py` | Implementation | Wake word, audio pipeline, confidence threshold |
| `hey_beeMo.onnx` | Model | Custom wake word model |
| `bmo_client/` | Implementation | BMO client codebase |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-02-01 | AI-Copilot | Initial BMO troubleshooting guide |

</details>

---

## Maintenance & Update Guide

- Add new troubleshooting entries when recurring issues are reported.
- Update threshold values if the wake word model is retrained.

---

## Functionality Testing

| Issue Category | Quick Test |
|---------------|------------|
| Microphone | `arecord -d 3 test.wav && aplay test.wav` |
| Wake word | Say "Hey BMO" from 1m distance |
| Audio playback | `speaker-test -t wav` |
