#!/bin/sh
# Helper (host-side prep — NOT part of run_all.sh / the container CMD): turn continuous
# recordings of people saying "Hey Friday" into the one-utterance-per-file, 16 kHz mono WAV
# clips that extract_features.py's real_samples/ path expects.
#
# Why this exists: microWakeWord's Clips reads each WAV as a SINGLE clip (windowed to
# clip_duration_ms), so a continuous file with 20 utterances collapses to one usable clip.
# You have to split first. This decodes each recording to 16 kHz mono (ffmpeg), splits it on
# silence into per-utterance clips (sox), and drops fragments too short to be a real wake word.
#
# Requires ffmpeg + sox on PATH. Run it wherever those exist (WSL / Git Bash / a Linux box /
# inside the training container) — it is deliberately standalone, not wired into the pipeline.
#
# Usage:
#   ./split_real_recordings.sh <input_dir> [output_dir] [speaker_label]
#     input_dir      folder of raw recordings, any format ffmpeg reads (.m4a/.wav/.mp3/...)
#     output_dir     where split clips go (default: ./real_samples)
#     speaker_label  optional; clips land in <output_dir>/<speaker_label>/ and are prefixed
#                    with it, so each person's clips stay identifiable and easy to balance
#
# Tunables (env vars):
#   SILENCE_THRESHOLD  silence level as a sox percentage (default 2%). RAISE if a noisy room
#                      is being chopped into too many fragments; LOWER if quiet utterances get
#                      cut off mid-word.
#   SILENCE_DURATION   seconds of silence that ends an utterance (default 0.3).
#   MIN_CLIP_S         drop output clips shorter than this (default 0.4s) — filters the
#                      silence-blip fragments that aren't a real "Hey Friday".
#   MAX_CLIP_S         warn (don't drop) on clips longer than this (default 2.5s) — usually
#                      two utterances that weren't separated; review those by hand.
#
# ALWAYS spot-check the output (play a few) before training: silence-splitting is
# threshold-sensitive and no default is right for every room/mic.
set -e

INPUT_DIR="${1:?usage: split_real_recordings.sh <input_dir> [output_dir] [speaker_label]}"
OUTPUT_DIR="${2:-./real_samples}"
SPEAKER="${3:-}"

SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-2%}"
SILENCE_DURATION="${SILENCE_DURATION:-0.3}"
MIN_CLIP_S="${MIN_CLIP_S:-0.4}"
MAX_CLIP_S="${MAX_CLIP_S:-2.5}"

for bin in ffmpeg sox soxi; do
    command -v "$bin" >/dev/null 2>&1 || {
        echo "ERROR: '$bin' not found on PATH. Install ffmpeg + sox first." >&2
        exit 1
    }
done

[ -d "$INPUT_DIR" ] || { echo "ERROR: input dir '$INPUT_DIR' does not exist." >&2; exit 1; }

DEST="$OUTPUT_DIR"
PREFIX=""
if [ -n "$SPEAKER" ]; then
    DEST="$OUTPUT_DIR/$SPEAKER"
    PREFIX="${SPEAKER}_"
fi
mkdir -p "$DEST"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

kept=0
for SRC in "$INPUT_DIR"/*; do
    [ -f "$SRC" ] || continue
    base="$(basename "$SRC")"
    stem="${base%.*}"

    echo "[split] decoding '$base' -> 16 kHz mono..."
    NORM="$TMPDIR/norm.wav"
    if ! ffmpeg -hide_banner -loglevel error -y -i "$SRC" -ac 1 -ar 16000 "$NORM" 2>/dev/null; then
        echo "[split]   ffmpeg could not decode '$base' (not audio?) — skipping." >&2
        continue
    fi

    echo "[split] splitting on silence (threshold=$SILENCE_THRESHOLD, gap=${SILENCE_DURATION}s)..."
    rm -f "$TMPDIR"/part*.wav
    # silence 1 0.1 THRESH  -> trim leading silence, start a clip on 0.1s above threshold
    # 1 SILENCE_DURATION THRESH -> end the clip after that much sub-threshold audio
    # : newfile : restart   -> emit part001.wav, part002.wav, ... and repeat to end of file
    sox "$NORM" "$TMPDIR/part.wav" \
        silence 1 0.1 "$SILENCE_THRESHOLD" 1 "$SILENCE_DURATION" "$SILENCE_THRESHOLD" \
        : newfile : restart 2>/dev/null || true

    for PART in "$TMPDIR"/part*.wav; do
        [ -e "$PART" ] || continue
        dur="$(soxi -D "$PART" 2>/dev/null || echo 0)"
        keepit="$(awk -v d="$dur" -v lo="$MIN_CLIP_S" 'BEGIN{print (d+0 >= lo+0) ? 1 : 0}')"
        if [ "$keepit" != "1" ]; then
            rm -f "$PART"
            continue
        fi
        kept=$((kept + 1))
        OUT="$DEST/${PREFIX}${stem}_$(printf '%03d' "$kept").wav"
        mv "$PART" "$OUT"
        toolong="$(awk -v d="$dur" -v hi="$MAX_CLIP_S" 'BEGIN{print (d+0 > hi+0) ? 1 : 0}')"
        [ "$toolong" = "1" ] && echo "[split]   NOTE: '$(basename "$OUT")' is ${dur}s (> ${MAX_CLIP_S}s) — may hold two utterances, review it."
    done
done

echo ""
echo "[split] Done. $kept clip(s) written to $DEST"
echo "[split] Spot-check a few by ear, then uncomment the real_augmented_features block in"
echo "[split] training_parameters.yaml and re-run train.sh."
