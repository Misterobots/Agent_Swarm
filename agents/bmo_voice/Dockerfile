FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    ffmpeg \
    espeak-ng \
    espeak-ng-data \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch Nightly (CUDA 12.8 compatible) for RTX 5060 Ti (sm_120)
# Pin versions to avoid pip resolution loop with --force-reinstall on nightly index
RUN pip3 install "numpy<2.0" --index-url https://pypi.org/simple && \
    pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Force system espeak paths
ENV PHONEMIZER_ESPEAK_LIBRARY="/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"
ENV PHONEMIZER_ESPEAK_PATH="/usr/bin/espeak-ng"
ENV ESPEAK_DATA_PATH="/usr/lib/x86_64-linux-gnu/espeak-ng-data"

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
