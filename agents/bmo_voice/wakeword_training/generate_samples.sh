#!/bin/sh
# Step 2 of the pipeline: generate positive "Hey Friday" wake-word samples via
# piper-sample-generator's LibriTTS-R speaker-mixing generator.
#
# Phrase variants below are reused as-is from the equivalent openWakeWord model this
# project already trained and validated pronunciation for (see
# "G:\My Drive\Colab Notebooks\Copy of train_wakeword.ipynb") — NOT re-derived here.
# Each variant gets its own numbered output subdirectory (piper-sample-generator always
# numbers files 0.wav, 1.wav, ... from zero on every invocation — writing two variants
# into the same directory would silently overwrite each other's samples), and
# extract_features.py globs all of them recursively.
#
# Idempotent / self-healing, same spirit as the recovered BMO notebook: re-running this
# script skips any variant that already has >= MAX_SAMPLES wav files on disk, and skips
# the ~200MB model download if it's already present and large enough to be complete.
set -e

DATA_DIR="${DATA_DIR:-/data}"
PSG_DIR="/opt/wakeword/piper-sample-generator"
MODEL_DIR="$DATA_DIR/models"
MODEL_PATH="$MODEL_DIR/en_US-libritts_r-medium.pt"
MODEL_URL="https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
OUT_ROOT="$DATA_DIR/generated_samples"

MAX_SAMPLES="${MAX_SAMPLES:-1000}"
BATCH_SIZE="${BATCH_SIZE:-100}"

# Force torch onto CPU for this step (escape hatch): stable-PyTorch support for
# Blackwell/sm_120 is unconfirmed (see Dockerfile comment). Leave unset to let torch try
# CUDA first; set PSG_FORCE_CPU=1 if a batch errors out with a CUDA kernel failure.
if [ "${PSG_FORCE_CPU:-0}" = "1" ]; then
    echo "[generate_samples] PSG_FORCE_CPU=1 — hiding GPUs from torch for this step."
    export CUDA_VISIBLE_DEVICES=""
fi

START_TS=$(date +%s)

mkdir -p "$MODEL_DIR" "$OUT_ROOT"

# ── LibriTTS-R generator weights (~200MB) — idempotent, size-checked like the
# recovered notebook's own self-healing downloads. ────────────────────────────────
if [ ! -f "$MODEL_PATH" ] || [ "$(wc -c < "$MODEL_PATH" 2>/dev/null || echo 0)" -lt 100000000 ]; then
    echo "[generate_samples] LibriTTS-R model missing/partial — downloading (~200MB)..."
    wget -q --tries=5 --timeout=300 -O "$MODEL_PATH" "$MODEL_URL"
else
    echo "[generate_samples] LibriTTS-R model already present ($(wc -c < "$MODEL_PATH") bytes) — skipping download."
fi
if [ "$(wc -c < "$MODEL_PATH")" -lt 100000000 ]; then
    echo "[generate_samples] ERROR: model file only $(wc -c < "$MODEL_PATH") bytes — download failed." >&2
    exit 1
fi

# ── Model config ─────────────────────────────────────────────────────────────────
# generate_samples.py opens "{model}.json" (espeak voice, sample_rate, num_speakers) right
# next to the .pt checkpoint. The v2.0.0 RELEASE ships only the .pt weights — the matching
# config lives in piper-sample-generator's OWN repo under models/, so copy it beside the
# downloaded weights. (Without this a first run crashes with FileNotFoundError on
# en_US-libritts_r-medium.pt.json.)
CONFIG_SRC="$PSG_DIR/models/en_US-libritts_r-medium.pt.json"
if [ ! -f "$MODEL_PATH.json" ]; then
    cp "$CONFIG_SRC" "$MODEL_PATH.json"
    echo "[generate_samples] Installed model config -> $MODEL_PATH.json"
fi

# ── Phrase variants ────────────────────────────────────────────────────────────────
# Index-prefixed directory names guarantee uniqueness even though "hey Friday" and
# "hey friday" (variants 1 and 3) differ only by case and would otherwise slugify to
# the same directory name.
i=0
for PHRASE in "hey Friday" "hey frie-dee" "hey friday" "yo friday"; do
    i=$((i + 1))
    SLUG=$(echo "$PHRASE" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-//; s/-$//')
    VARIANT_DIR="$OUT_ROOT/$(printf '%02d' "$i")_${SLUG}"
    mkdir -p "$VARIANT_DIR"

    EXISTING=$(find "$VARIANT_DIR" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)
    if [ "$EXISTING" -ge "$MAX_SAMPLES" ]; then
        echo "[generate_samples] [$i/4] \"$PHRASE\" -> $VARIANT_DIR already has $EXISTING/$MAX_SAMPLES samples — skipping."
        continue
    fi

    echo "[generate_samples] [$i/4] \"$PHRASE\" -> $VARIANT_DIR (have $EXISTING, generating up to $MAX_SAMPLES)..."
    python3 "$PSG_DIR/generate_samples.py" "$PHRASE" \
        --model "$MODEL_PATH" \
        --max-samples "$MAX_SAMPLES" \
        --batch-size "$BATCH_SIZE" \
        --output-dir "$VARIANT_DIR"
done

END_TS=$(date +%s)
TOTAL_WAVS=$(find "$OUT_ROOT" -name '*.wav' | wc -l)
echo "[generate_samples] Done. $TOTAL_WAVS total wav files under $OUT_ROOT. Elapsed: $((END_TS - START_TS))s."
