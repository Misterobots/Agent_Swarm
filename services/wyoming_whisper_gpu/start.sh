#!/bin/sh
# Starts the real Wyoming Whisper server in the background, waits for it to actually be
# listening (which only happens after the model has finished loading onto the GPU — see
# wyoming_faster_whisper's own main(): load_transcriber() is awaited before the server
# starts accepting connections), fires one throwaway transcription to force the one-time
# CUDA kernel compilation cost to happen now instead of on the first real voice command,
# then hands off to the server process as the container's actual foreground process (via
# `wait`) so container lifecycle/signal handling still targets the real server.
#
# --vad-filter is a SAFETY control, not just a latency one — confirmed live: this server
# transcribed near-silent audio (a muted mic, and separately a synthesized 440Hz warm-up
# tone) as "Thank you." — Whisper's single most common hallucination on non-speech audio
# (~25% of all such hallucinations per arXiv:2501.11378), and the resulting text reached
# bmo_brain as if it were a real utterance. wyoming-faster-whisper's own transcribe() never
# forwards Whisper's native no_speech_threshold/logprob_threshold to anything downstream
# (confirmed from source), and those thresholds don't reliably catch this failure mode
# anyway — a confident hallucination has LOW no_speech_prob and HIGH avg_logprob by
# construction, evading both. --vad-filter is the one flag this package's CLI actually
# exposes that hard-gates the decoder behind Silero VAD: on true silence it structurally
# yields zero segments -> an empty transcript -> HA's existing stt-no-text-recognized path,
# instead of a fabricated one reaching the conversation agent. Do NOT rely on --vad-clip
# instead — confirmed from source it fails OPEN (falls back to the full untrimmed audio
# when it finds no speech), so it improves latency/context but provides no protection here.
# --vad-min-speech-ms raised from the 250ms default to 400ms specifically targets the
# repro case (mic toggled off almost immediately = a sub-400ms blip no real command is
# ever shorter than).
set -e

python3 -m wyoming_faster_whisper \
    --uri tcp://0.0.0.0:10300 \
    --model "$WHISPER_MODEL" \
    --device cuda \
    --compute-type float16 \
    --beam-size "$WHISPER_BEAM_SIZE" \
    --language en \
    --vad-filter \
    --vad-threshold "${WHISPER_VAD_THRESHOLD:-0.3}" \
    --vad-min-speech-ms 400 \
    --vad-min-silence-ms 2000 \
    --data-dir /data \
    --download-dir /data &
SERVER_PID=$!

echo "[start.sh] Waiting for wyoming_faster_whisper to accept connections on :10300..."
until python3 -c "import socket; socket.create_connection(('localhost', 10300), timeout=1).close()" 2>/dev/null; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[start.sh] Server process exited before becoming ready — skipping warm-up."
        wait "$SERVER_PID"
        exit $?
    fi
    sleep 1
done

echo "[start.sh] Server is listening — sending warm-up transcription (forces one-time CUDA kernel compilation)..."
if python3 /app/warmup_client.py; then
    echo "[start.sh] Warm-up complete — first real request will be fast."
else
    echo "[start.sh] Warm-up call failed (non-fatal) — first real request will pay the cold-start cost instead."
fi

wait "$SERVER_PID"
