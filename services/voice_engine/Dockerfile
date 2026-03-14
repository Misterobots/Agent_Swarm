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
# Update pip first
RUN pip3 install --upgrade pip

# Install Qwen-TTS and core libraries
# Install Qwen-TTS and core libraries
RUN pip3 install qwen-tts modelscope funasr

WORKDIR /app

# Install PyTorch Nightly (CUDA 12.8 compatible) for RTX 5060 Ti support
RUN pip3 install "numpy<2.0" --pre torch torchvision torchaudio --force-reinstall --index-url https://download.pytorch.org/whl/nightly/cu128 --extra-index-url https://pypi.org/simple

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt



COPY . .

# Expose port 8020
EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
