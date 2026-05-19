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

# Install PyTorch Nightly FIRST (CUDA 12.8 for RTX 5060 Ti) so ABI is set
RUN pip3 install "numpy<2.0" --index-url https://pypi.org/simple && \
    pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Install Qwen-TTS AFTER PyTorch nightly (--no-deps to keep nightly torchaudio)
RUN pip3 install --no-deps qwen-tts && \
    pip3 install modelscope funasr

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt



COPY . .

# Expose port 8020
EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
