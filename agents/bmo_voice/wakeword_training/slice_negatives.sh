#!/usr/bin/env bash
# Slice continuous ambient recordings into fixed-length 16 kHz mono WAV clips for use as
# household HARD-NEGATIVES ("Hey Friday" false-trigger material — see RECORDING_NEGATIVES.md).
#
# Why a separate slicer (not split_real_recordings.sh): that one splits on SILENCE to isolate
# spoken *utterances* for the POSITIVE set. Negatives are the opposite — we want DENSE, gap-free
# fixed-window coverage of the ambient audio so every slice of TV/conversation/music becomes a
# "this is NOT the wake word" example. So this cuts fixed CLIP_S-second windows, silence and all.
#
# Host-side; needs ffmpeg on PATH (same assumption as split_real_recordings.sh). Accepts any input
# format ffmpeg can decode (m4a, mp3, wav, ...).
#
#   ./slice_negatives.sh <raw_dir> <out_dir>
#   ./slice_negatives.sh data/household_negatives_raw data/household_negatives
#
# CLIP_S defaults to 1.5 s to match clip_duration_ms: 1500 in training_parameters.yaml.
set -euo pipefail

RAW_DIR="${1:?usage: slice_negatives.sh <raw_dir> <out_dir>}"
OUT_DIR="${2:?usage: slice_negatives.sh <raw_dir> <out_dir>}"
CLIP_S="${CLIP_S:-1.5}"

command -v ffmpeg >/dev/null 2>&1 || { echo "ERROR: ffmpeg not found on PATH" >&2; exit 1; }
[ -d "$RAW_DIR" ] || { echo "ERROR: raw dir '$RAW_DIR' not found" >&2; exit 1; }
mkdir -p "$OUT_DIR"

shopt -s nullglob
i=0
found=0
for f in "$RAW_DIR"/*; do
  [ -f "$f" ] || continue
  case "$f" in *.gitkeep|*.md|*.txt) continue;; esac
  found=1
  base="src$(printf '%03d' "$i")"
  echo "  slicing: $(basename "$f") -> ${base}_*.wav"
  ffmpeg -nostdin -loglevel error -y -i "$f" -ac 1 -ar 16000 \
    -f segment -segment_time "$CLIP_S" -reset_timestamps 1 \
    "$OUT_DIR/${base}_%04d.wav"
  i=$((i + 1))
done

if [ "$found" -eq 0 ]; then
  echo "No input recordings found in $RAW_DIR — drop your ambient recordings there first." >&2
  exit 1
fi

n=$(find "$OUT_DIR" -name '*.wav' | wc -l | tr -d ' ')
echo "Done: sliced $n clips of ${CLIP_S}s (16 kHz mono) into $OUT_DIR"
echo "Spot-check a few by ear, then (re)run training. Remember to delete"
echo "data/household_negative_features/ before re-extracting if you add more clips later."
