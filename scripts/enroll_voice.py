#!/usr/bin/env python3
"""
BMO Speaker Enrollment Script
------------------------------
Records N voice samples from the Pi microphone and sends them to
voice_engine_gpu's /enroll_speaker endpoint to build a speaker profile.

Run this ON the Pi (or via SSH) after deploying voice_satellite.py:
  python3 /home/misterobots/bmo_client/enroll_voice.py --speaker justin

Each recording is 8 seconds. You'll be prompted to speak a different
sentence each time so the profile captures natural variation.

Usage:
  python3 enroll_voice.py --speaker justin [--samples 5] [--host 192.168.2.101]
"""

import os
import sys
import time
import argparse
import tempfile
import requests
import numpy as np
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv

# Load network.env so HOST_IP resolves correctly on the Pi
_script_dir = os.path.dirname(os.path.abspath(__file__))
for _candidate in [os.path.join(_script_dir, "..", "network.env"), os.path.join(_script_dir, "network.env")]:
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break

SAMPLE_RATE = 16000
RECORD_SECONDS = 8  # seconds per utterance

PROMPTS = [
    "Hey Beemo, what's the weather going to be like today? I'm thinking of going for a walk.",
    "Beemo, remind me to check my emails at three o'clock this afternoon.",
    "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
    "Beemo, turn on the living room lights and set the volume to fifty percent.",
    "I'd like you to tell me a joke. Something short and clever, please.",
    "Beemo, what time is it right now? Also, how many days until the weekend?",
    "Set a timer for twenty minutes and play some lo-fi music while I work.",
    "Good morning! Can you summarise the news headlines for today?",
]


def detect_mic_card() -> str:
    """Return the ALSA card number for the USB audio codec as a string.
    Used with arecord -D plughw:<card>,0."""
    import re as _re
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            name = dev["name"].lower()
            if "usb" in name or "codec" in name:
                m = _re.search(r"hw:(\d+)", dev["name"])
                card = m.group(1) if m else str(idx)
                print(f"  Mic: {dev['name']} → arecord plughw:{card},0")
                return card
    except Exception as e:
        print(f"  Mic detection error: {e}")
    print("  ⚠️  No USB mic found — falling back to card 2")
    return "2"


def record_utterance(device, seconds: int, prompt: str) -> np.ndarray:
    """Record a single utterance. Returns int16 numpy array."""
    print()
    print("  ┌─ SAY THIS ──────────────────────────────────────────────────┐")
    # Word-wrap the prompt at ~60 chars
    words = prompt.split()
    line, lines = [], []
    for w in words:
        if sum(len(x) + 1 for x in line) + len(w) > 60:
            lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    for l in lines:
        print(f"  │  {l:<61}│")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()
    input("  Press Enter when ready, then speak …")
    print(f"  🔴 Recording for {seconds}s …")

    # Use arecord (native ALSA) — avoids PortAudio channel negotiation issues on the Pi
    import subprocess, tempfile
    wav_path = tempfile.mktemp(suffix=".wav")  # path only — don't pre-create, let arecord write the WAV header
    alsa_dev = f"plughw:{device},0"
    cmd = ["arecord", "-D", alsa_dev, "-f", "S16_LE",
           "-r", str(SAMPLE_RATE), "-c", "1", "-d", str(seconds), wav_path]
    try:
        # Show a live countdown while arecord runs in background
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        for remaining in range(seconds, 0, -1):
            print(f"    {remaining}s remaining …", end="\r")
            time.sleep(1)
        _, stderr_bytes = proc.communicate(timeout=5)
        if proc.returncode != 0 or not os.path.exists(wav_path):
            stderr_msg = stderr_bytes.decode(errors="replace").strip()
            if "busy" in stderr_msg.lower() or "device or resource busy" in stderr_msg.lower():
                raise RuntimeError(
                    f"Mic is busy (bmo_satellite.service is using it).\n"
                    f"Stop it first:  sudo systemctl stop bmo_satellite.service\n"
                    f"Then re-run enrollment, and restart afterwards:\n"
                    f"  sudo systemctl start bmo_satellite.service"
                )
            raise RuntimeError(f"arecord failed (rc={proc.returncode}): {stderr_msg}")
        print("  Done.                          ")
        audio, _ = sf.read(wav_path, dtype="int16")
        return audio.flatten()
    except Exception as e:
        print(f"\n  ❌ Recording error: {e}")
        raise
    finally:
        try:
            os.remove(wav_path)
        except Exception:
            pass


def enroll_sample(wav_path: str, speaker_id: str, host: str) -> dict:
    """POST a WAV file to /enroll_speaker. Returns the JSON response."""
    url = f"http://{host}:8020/enroll_speaker"
    with open(wav_path, "rb") as f:
        resp = requests.post(
            url,
            data={"speaker_id": speaker_id},
            files={"audio": (os.path.basename(wav_path), f, "audio/wav")},
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Enroll a speaker for BMO voice verification")
    parser.add_argument("--speaker", required=True, help="Speaker ID (e.g. 'justin')")
    parser.add_argument("--samples", type=int, default=5, help="Number of voice samples to record")
    parser.add_argument("--host", default=None, help="Host IP of voice_engine_gpu (default: LOVELACE_IP from network.env)")
    args = parser.parse_args()

    host = args.host or os.getenv("LOVELACE_IP") or os.getenv("BMO_HOST_IP")
    if not host:
        print("ERROR: Could not determine host IP. Set --host or LOVELACE_IP in network.env")
        sys.exit(1)

    num_samples = min(args.samples, len(PROMPTS))
    print(f"\n🎙️  BMO Speaker Enrollment")
    print(f"   Speaker  : {args.speaker}")
    print(f"   Samples  : {num_samples}  ×  {RECORD_SECONDS}s")
    print(f"   Engine   : http://{host}:8020")
    print()
    print("You'll record several short utterances. Speak naturally.")
    print("The more varied they are, the more robust your profile will be.")
    input("  Press Enter to begin …")

    device = detect_mic_card()

    for i in range(num_samples):
        print(f"\n[{i+1}/{num_samples}]")
        prompt = PROMPTS[i % len(PROMPTS)]
        audio = record_utterance(device, RECORD_SECONDS, prompt)

        rms = int(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        if rms < 500:
            print(f"  ⚠️  Audio very quiet (RMS={rms}) — mic may not be working. Retrying.")
            audio = record_utterance(device, RECORD_SECONDS, "Please speak louder.")
            rms = int(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio, SAMPLE_RATE, subtype="PCM_16")
            wav_path = tmp.name

        try:
            print(f"  Sending sample {i+1} to voice engine … (RMS={rms})")
            result = enroll_sample(wav_path, args.speaker, host)
            action = result.get("action", "?")
            enrolled = result.get("enrolled_speakers", [])
            print(f"  ✅ Profile {action}. Enrolled speakers: {enrolled}")
        except Exception as e:
            print(f"  ❌ Enrollment failed for sample {i+1}: {e}")
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass

    print(f"\n🎉 Enrollment complete for '{args.speaker}'!")
    print("Run a quick test by saying BMO's wake word — your voice should be accepted.")
    print("To enable the gate, set BMO_SPEAKER_VERIFY=true in network.env on the Pi, then restart bmo_satellite.service.")


if __name__ == "__main__":
    main()
