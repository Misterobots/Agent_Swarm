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

COPY . .

# Expose port 8020
EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
