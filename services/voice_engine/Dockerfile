FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    sox \
    libsox-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install --upgrade pip

WORKDIR /app

# Install PyTorch FIRST (stable CUDA 12.8 wheels; Blackwell/sm_120 supported) so ABI is set.
# Switched off the nightly index: --pre pulled mismatched torch/torchvision nightlies
# (ResolutionImpossible). torchvision is unused by the TTS/STT path, so it is dropped.
RUN pip3 install "numpy<2.0" --index-url https://pypi.org/simple && \
    pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

# Install Qwen-TTS AFTER PyTorch (--no-deps to keep our torchaudio)
RUN pip3 install --no-deps qwen-tts && \
    pip3 install modelscope funasr

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Pin qwen-tts 0.1.1's exact deps LAST so they win over what requirements.txt / modelscope /
# funasr pulled. Those install transformers 5.x, whose check_model_inputs() API change makes
# the qwen3_tts architecture fail to load (falls back to bare transformers -> "unrecognized
# architecture"). qwen-tts also needs pysox/einops/onnxruntime/librosa, which its --no-deps
# install above skipped.
RUN pip3 install --no-cache-dir \
        sox einops onnxruntime librosa \
        "transformers==4.57.3" "accelerate==1.12.0"

# faster-qwen3-tts wraps the SAME qwen-tts model class pinned above with CUDA-graph capture
# around the decode loop — it depends on qwen-tts>=0.1.1 (already satisfied by the pin above,
# so it doesn't get a chance to touch the transformers/accelerate pins). Fixes /speak's real
# bottleneck: measured live on this exact GPU, RTF dropped from ~1.6 (current baseline) to
# ~0.4 after a one-time CUDA-graph warm-up at model load — the reference-audio encoding
# (whisper_encoder's missing flash-attn) and GPU contention were both ruled out first;
# per-autoregressive-step CPU-GPU dispatch overhead was the actual cost, and this is the
# fix that targets it directly. Installed last, after the version pins, purely as a safety
# margin — its own resolver shouldn't need to touch transformers/accelerate since qwen-tts
# is already satisfied, but this ordering means it can't win a conflict if it tried.
RUN pip3 install --no-cache-dir faster-qwen3-tts

COPY . .

# Expose port 8020
EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
