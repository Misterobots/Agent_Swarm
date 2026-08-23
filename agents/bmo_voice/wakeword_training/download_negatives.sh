#!/bin/sh
# Step 3 of the pipeline: fetch negative (non-wake-word) training data.
#
# Two kinds of negative data, matching microWakeWord's own training notebook exactly:
#   (a) Pre-computed spectrogram-feature datasets hosted on HuggingFace, specific to
#       microWakeWord's own feature format (NOT raw audio, NOT reusable from the
#       openWakeWord pipeline) — handled directly in this script via wget/unzip.
#   (b) Raw background/room-impulse-response audio for augmentation (RIR, AudioSet,
#       FMA), which needs the `datasets` library to decode/resample — handled by the
#       companion download_background_audio.py.
#
# LICENSING NOTE (carried over verbatim from microWakeWord's own notebook, cell 4):
# this background audio has a mixture of licenses and usage restrictions. Any model
# trained using it should be treated as appropriate for non-commercial personal use
# only — this matches how BMO/Friday's models are already used, but flagging it here
# since it's not obvious from the file names alone.
#
# Idempotent: skips any dataset whose target directory already exists and is non-empty.
set -e

DATA_DIR="${DATA_DIR:-/data}"
NEG_DIR="$DATA_DIR/negative_datasets"
mkdir -p "$NEG_DIR"

START_TS=$(date +%s)

# ── (a) microWakeWord's own pre-built negative spectrogram-feature sets ───────────
# Exact HuggingFace dataset repo, confirmed from microWakeWord's own notebook source
# (kahrendt/microwakeword on HF, not to be confused with the kahrendt/microWakeWord
# GitHub *code* repo — same author, different host, easy to conflate).
HF_ROOT="https://huggingface.co/datasets/kahrendt/microwakeword/resolve/main"
for FNAME in dinner_party.zip dinner_party_eval.zip no_speech.zip speech.zip; do
    NAME="${FNAME%.zip}"
    TARGET_DIR="$NEG_DIR/$NAME"
    if [ -d "$TARGET_DIR" ] && [ -n "$(find "$TARGET_DIR" -mindepth 1 -print -quit 2>/dev/null)" ]; then
        echo "[download_negatives] $NAME already present at $TARGET_DIR — skipping."
        continue
    fi
    ZIP_PATH="$NEG_DIR/$FNAME"
    echo "[download_negatives] Fetching $FNAME..."
    wget -q --tries=5 --timeout=300 -O "$ZIP_PATH" "$HF_ROOT/$FNAME"
    echo "[download_negatives] Extracting $FNAME -> $NEG_DIR ..."
    unzip -q -o "$ZIP_PATH" -d "$NEG_DIR"
    if [ ! -d "$TARGET_DIR" ]; then
        echo "[download_negatives] WARNING: expected $TARGET_DIR after extracting $FNAME but it wasn't created — check the zip's internal layout." >&2
    fi
done

# ── (b) Raw background audio for augmentation (RIR / AudioSet / FMA) ──────────────
python3 /opt/wakeword/download_background_audio.py

END_TS=$(date +%s)
echo "[download_negatives] Done. Elapsed: $((END_TS - START_TS))s."
