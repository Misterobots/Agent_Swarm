FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip3 install --upgrade pip

# No PyTorch needed here, unlike voice_engine's TTS Dockerfile: faster-whisper's
# transcription path runs entirely through CTranslate2 (its own C++/CUDA engine,
# independent of PyTorch) — VAD runs via onnxruntime + pysilero-vad (CPU, lightweight).
# Pin ctranslate2 explicitly past the Blackwell/sm_120 INT8 tensor-core padding fix
# (OpenNMT/CTranslate2 PR #1982, merged into v4.6.3/4.7.0) — our exact Lovelace GPU
# (RTX 5060 Ti) is named directly in the bug reports (#1865, #1981) and the fix's own
# author re-verified it on an RTX 5060 Ti. We run compute_type=float16 below, which was
# never affected by that bug on any GPU generation — this pin is defense-in-depth only,
# so a future dependency resolution never silently regresses onto the pre-fix build.
RUN pip3 install --no-cache-dir "ctranslate2>=4.7.0,<5" "wyoming-faster-whisper>=3.4.1,<4"

# CTranslate2's CUDA path needs cuBLAS + cuDNN 9 runtime .so files on LD_LIBRARY_PATH.
# The base image's own bundled cuDNN may not match the cuDNN9 CTranslate2>=4.5.0 requires —
# belt-and-suspenders on top of it, matching the exact pattern faster-whisper's own README
# and the working community image mib1185/wyoming-faster-whisper-cuda both use.
RUN pip3 install --no-cache-dir nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
ENV LD_LIBRARY_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}"

EXPOSE 10300
VOLUME ["/data"]

# compute-type float16 explicit, never "auto" or int8/int8_float16 — "auto" silently
# resolves to int8_float16 on GPU, which is exactly the mode implicated in the Blackwell
# CUBLAS_STATUS_NOT_SUPPORTED bug above; float16 sidesteps needing to rely on the fix at
# all. Model is overridable via WHISPER_MODEL env for the smoke-test A/B comparison
# (distil-large-v3 vs large-v3-turbo — research didn't converge on a single winner).
ENV WHISPER_MODEL="distil-large-v3"
ENV WHISPER_BEAM_SIZE="1"

# Synthesized tone, baked in at build time, used only to force the model's one-time CUDA
# kernel compilation at container startup (measured live: ~8s cold vs ~0.2-0.4s warm) —
# see start.sh. Content doesn't matter: CUDA kernel selection depends on tensor shapes,
# not on what's actually said, and baking it in avoids any startup-time dependency on
# another service being reachable.
RUN ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -ar 16000 -ac 1 -sample_fmt s16 -y /app/warmup.wav

COPY warmup_client.py /app/warmup_client.py
COPY start.sh /app/start.sh
# Defensive: strip any CRLF line endings the shell script may have picked up from being
# authored on Windows — a stray \r on the shebang line breaks "bad interpreter" in Linux.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]
