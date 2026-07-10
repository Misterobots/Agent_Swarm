#!/bin/sh
# Runs the full pipeline end-to-end, unattended: generate samples -> download negatives
# -> train (which itself runs feature extraction first) -> build the ESPHome manifest.
# This is the container's default CMD — `docker run --gpus '"device=1"' -v ...:/data
# wakeword-training` runs this automatically. Every step is independently idempotent
# (see each script's own header), so re-running run_all.sh after an interruption picks
# up wherever it left off instead of redoing finished work.
#
# Expect this to take well over an hour end-to-end (see README.md for a stage-by-stage
# estimate) — it's designed to be started and left running, not babysat.
set -e

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

PIPELINE_START=$(date +%s)

log_stage() {
    echo ""
    echo "=================================================================="
    echo "[run_all] $(date '+%Y-%m-%d %H:%M:%S') — $1"
    echo "=================================================================="
}

log_stage "Stage 1/4: generate_samples.sh (positive 'Hey Friday' samples)"
/opt/wakeword/generate_samples.sh

log_stage "Stage 2/4: download_negatives.sh (negative feature sets + background audio)"
/opt/wakeword/download_negatives.sh

log_stage "Stage 3/4: train.sh (feature extraction + microwakeword training + TFLite export)"
/opt/wakeword/train.sh

log_stage "Stage 4/4: build_manifest.py (package .tflite + manifest.json for ESPHome)"
python3 /opt/wakeword/build_manifest.py --wake-word "Hey Friday" --model-id hey_friday

PIPELINE_END=$(date +%s)
ELAPSED=$((PIPELINE_END - PIPELINE_START))
echo ""
echo "=================================================================="
printf '[run_all] Pipeline complete. Total elapsed: %02d:%02d:%02d (%ss)\n' \
    $((ELAPSED / 3600)) $(((ELAPSED / 60) % 60)) $((ELAPSED % 60)) "$ELAPSED"
echo "[run_all] Final artifacts: $DATA_DIR/models/hey_friday/ — copy into"
echo "  agents/bmo_voice/wakeword_training/models/hey_friday/ and commit (see README.md)."
echo "=================================================================="
