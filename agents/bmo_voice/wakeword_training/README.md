# "Hey Friday" wake-word training (microWakeWord → ESPHome)

This directory trains the **on-device** "Hey Friday" wake word for the
`google-mini-voice` ESPHome satellite (a repurposed Google Home Mini — see
[`esphome/google-mini-voice.yaml`](esphome/google-mini-voice.yaml)). It produces a
**quantized streaming TensorFlow-Lite model** small enough to run always-on on the
ESP32-S3, entirely locally.

> **Two "Hey Friday" detectors exist — don't confuse them.**
> - `../hey_friday.onnx` is an **openWakeWord** model (classifier on a frozen shared
>   speech embedding) that runs on the **Pi** in host Python. Trained earlier in Colab.
> - This pipeline trains a **microWakeWord** model (a small streaming conv net, MixedNet)
>   that runs **on the ESP32 itself**. The two are structurally incompatible and share no
>   model/feature code — this pipeline only reuses the *phrase list* validated during the
>   openWakeWord work.

---

## Quick start (full pipeline)

Everything the container writes lands on the **host-bind-mounted `/data` volume**, so
generated samples and downloaded datasets survive a rebuild.

```bash
# from the repo root:
docker build -t wakeword-training agents/bmo_voice/wakeword_training

docker run --rm --gpus '"device=1"' \
  -v "$(pwd)/agents/bmo_voice/wakeword_training/data:/data" \
  wakeword-training
```

- `--gpus '"device=1"'` targets the idle 5060 Ti (GPU 0 is left for whatever's resident
  there); the pipeline also runs CPU-only if you drop `--gpus`.
- Expect **well over an hour** end to end. It's designed to be started and left running.
- Every stage is idempotent — re-running `run_all.sh` after an interruption resumes where
  it left off rather than redoing finished work.

Run a single stage instead of the whole chain (the `CMD` is overridable):

```bash
docker run --rm --gpus '"device=1"' -v "...:/data" wakeword-training /opt/wakeword/train.sh
```

---

## The `/data` volume

`/data` is a path **inside the container**, bind-mounted from
`agents/bmo_voice/wakeword_training/data/` on the host. That host folder **does not exist
until the first run** — the command above creates it. Layout once populated:

```
data/
├── models/
│   ├── en_US-libritts_r-medium.pt   # piper TTS generator (~200 MB, auto-downloaded)
│   └── hey_friday/                  # ← FINAL OUTPUT: .tflite + manifest.json for ESPHome
├── generated_samples/               # synthetic positive WAVs (one subdir per phrase variant)
├── real_samples/                    # ← YOUR recordings (optional; you create this — see below)
├── background_audio/                # mit_rirs / fma_16k / audioset_16k (augmentation sources)
├── negative_datasets/               # speech / dinner_party / no_speech (pre-built neg features)
├── generated_augmented_features/    # synthetic positives → spectrogram features
├── real_augmented_features/         # real positives → spectrogram features (if real_samples/)
├── trained_models/wakeword/         # training checkpoints + the exported .tflite
└── training_parameters.yaml         # RUNTIME config copy — edit THIS after the first run
```

---

## The four pipeline stages (`run_all.sh`)

1. **`generate_samples.sh`** — synthesizes positive "Hey Friday" examples with
   `piper-sample-generator` (LibriTTS-R speaker-mixing), ~1000 each of four phrase variants
   (`hey Friday`, `hey frie-dee`, `hey friday`, `yo friday`). No recordings needed — voice
   diversity comes from the TTS model.
2. **`download_negatives.sh`** — downloads pre-built negative spectrogram feature sets and
   background audio (music/speech/noise + room impulse responses) from
   `huggingface.co/datasets/kahrendt/microwakeword`. Negatives are what teach it *not* to
   false-fire, and they deliberately outweigh positives during training.
3. **`train.sh`** — runs `extract_features.py` (positives → augmented spectrograms), then
   `microwakeword.model_train_eval` (MixedNet, 10k steps), and exports the **quantized
   streaming** `stream_state_internal_quant.tflite`.
4. **`build_manifest.py`** — packages the `.tflite` + a `manifest.json` into
   `data/models/hey_friday/` for ESPHome to consume.

---

## Adding your own recordings — the accuracy booster (`real_samples/`)

The synthetic positives generalize to *anyone* (guests, strangers) but have never heard
**your** voice in **your** rooms. Dropping in a modest set of real recordings closes that
domain gap and is the single highest-leverage accuracy move for your household.

**1. Record.** Phone (or the Mini's own mic) placed *where the Mini will sit* — not held to
your face; the value is real distance + room reverb. Have each household member say the wake
phrase naturally ~10–20 times, across a couple of room positions and volumes. Cover the real
range of voices (**include kids** — the synthetic set skews adult). ~30–150 total is plenty.

**2. Split into per-utterance clips.** microWakeWord reads each WAV as a *single* clip, so a
continuous recording must be split first:

```bash
# host-side; needs ffmpeg + sox on PATH
./split_real_recordings.sh <raw_recordings_dir> ./data/real_samples <speaker_label>
```

This decodes any format to 16 kHz mono, splits on silence into one-utterance clips, and
drops too-short fragments. **Spot-check the output by ear** — silence thresholds are
room-dependent (tune via `SILENCE_THRESHOLD` / `SILENCE_DURATION`, see the script header).

**3. Enable the real set.** Uncomment the `real_augmented_features` block in
`training_parameters.yaml`. It's weighted at `sampling_weight: 2.0` — **parity** with the
synthetic set, on purpose:

- `sampling_weight` sets how often a set is drawn per batch **independent of its file
  count**, so a few dozen real clips register with real influence rather than being drowned
  by the ~4000 synthetic ones.
- Keeping it at *parity* (not higher) means real clips **anchor** the model without
  **dominating** it — the synthetic set's broad speaker diversity keeps carrying
  guests/unseen voices. Drop to `1.0` if it overfits to your specific recordings.

> ⚠️ Uncomment the block **only** once `real_samples/` has clips — `model_train_eval`
> expects every listed `features_dir` to exist, so an empty enabled set crashes training.
> On a **first** run, uncomment it in this repo template (it's copied to `/data` on first
> run). **After** the first run, edit `/data/training_parameters.yaml` instead.

**4. Re-run** `train.sh` (or `run_all.sh`). ⚠️ If you *add more* clips later, delete the
cached `data/*_augmented_features/` dirs first, or `extract_features.py`'s idempotency check
short-circuits and your new audio is silently ignored.

---

## Tuning

Edit `training_parameters.yaml` (the `/data` copy after first run). Common knobs:

- **`sampling_weight` / `*_class_weight`** — the positive/negative balance. Negatives are
  weighted heavily (`negative_class_weight: 20`) because a wake word's cardinal sin is
  false-firing.
- **SpecAugment** (`time_mask_*` / `freq_mask_*`) — currently all `0`. The first thing
  upstream suggests enabling if the model under/over-fits (useful when relying on a small
  real set).
- **`maximization_metric: average_viable_recall`** — best recall subject to an acceptable
  false-accept rate.

**Runtime, no retrain:** the fastest fix for false-fires (raise) or misses (lower) is the
detection **threshold** in ESPHome's `micro_wake_word`, not this config. Retrain only when
no threshold gives an acceptable balance.

---

## Deploying the result

The final model lands in `data/models/hey_friday/`. Copy it into the repo
(`agents/bmo_voice/wakeword_training/models/hey_friday/`) and reference it from
[`esphome/google-mini-voice.yaml`](esphome/google-mini-voice.yaml), then flash the Mini.
Commit the `.tflite`/manifest; keep the raw `data/` volume (recordings, downloads,
checkpoints) **out of git**.
