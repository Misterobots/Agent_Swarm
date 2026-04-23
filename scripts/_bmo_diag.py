"""BMO Wake Word Diagnostic - run on Pi to check mic level and model scores."""
import numpy as np
import sounddevice as sd
import sys, os
sys.path.insert(0, "/home/misterobots/bmo_client")
os.chdir("/home/misterobots/bmo_client")

from openwakeword.model import Model

MODEL_PATH = "/home/misterobots/bmo_client/hey_beeMo.onnx"
MIC_DEVICE = 2
HW_RATE = 48000
DURATION = 5  # seconds to record

# ── 1. Load model and show raw prediction keys ──────────────────────────────
print("Loading model:", MODEL_PATH)
m = Model(wakeword_model_paths=[MODEL_PATH])
zero = np.zeros(1280, dtype=np.int16)
raw_keys = list(m.predict(zero).keys())
print("RAW prediction keys from model:", raw_keys)

# ── 2. Record from mic ───────────────────────────────────────────────────────
print(f"\nRecording {DURATION}s from device {MIC_DEVICE} at {HW_RATE}Hz...")
print(">>> SPEAK 'HEY BEEMO' NOW <<<")
data = sd.rec(int(DURATION * HW_RATE), samplerate=HW_RATE, channels=1, dtype="int16", device=MIC_DEVICE)
sd.wait()
samples = data[:, 0]

rms = int(np.sqrt(np.mean(samples.astype(np.float64)**2)))
peak = int(np.abs(samples).max())
print(f"\nMic stats: RMS={rms}  Peak={peak}")
if rms < 50:
    print("WARNING: mic appears SILENT (RMS < 50). Check hardware/levels.")
elif rms < 500:
    print("WARNING: mic level is LOW. Try speaking louder or adjusting gain.")
else:
    print("Mic level OK.")

# ── 3. Feed chunks through model, track per-key max scores ──────────────────
CHUNK_HW = 3840    # 48kHz input chunk (decimates to 1280 @ 16kHz)
CHUNK_16K = 1280

max_scores = {}
chunk_count = 0
for i in range(0, len(samples) - CHUNK_HW, CHUNK_HW):
    chunk = samples[i:i + CHUNK_HW][::3]  # decimate 48k->16k
    if len(chunk) < CHUNK_16K:
        continue
    pred = m.predict(chunk[:CHUNK_16K])
    chunk_count += 1
    for k, v in pred.items():
        fv = float(v)
        if fv > max_scores.get(k, 0.0):
            max_scores[k] = fv

print(f"\nProcessed {chunk_count} chunks.")
print("Max scores per key:")
for k, v in sorted(max_scores.items(), key=lambda x: -x[1]):
    bar = "#" * int(v * 40)
    print(f"  {k:40s}  {v:.4f}  {bar}")

print("\nDone. Threshold=0.3 — any key above 0.3 would trigger.")
