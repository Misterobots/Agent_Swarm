# Use a slim Python base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for psycopg2 compilation if using source)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Common Python Dependencies for AI Agents
RUN pip install --no-cache-dir \
    phidata \
    ollama \
    openai \
    anthropic \
    packaging \
    duckduckgo-search \
    fastapi \
    uvicorn \
    prometheus_client \
    sqlalchemy \
    pgvector \
    psycopg \
    psycopg2-binary \
    aiohttp \
    requests \
    streamlit \
    watchdog \
    plotly \
    python-logging-loki \
    numpy \
    scipy \
    soundfile \
    opencv-python-headless \
    streamlit-monaco \
    redis \
    mempalace

# Install SPIFFE SDK, Langfuse, and JWT-ACE dependencies
RUN pip install --no-cache-dir \
    spiffe \
    nvidia-ml-py \
    cachetools \
    langfuse \
    PyJWT

# Training pipeline dependencies (curated dataset downloads, security scanning)
RUN pip install --no-cache-dir \
    datasets \
    huggingface_hub

# Training runtime dependencies (Unsloth GRPO fine-tuning, RTX 5060 Ti / sm_120)
# NOTE: unsloth pins torch<2.11.0, so we let it install the correct torch version.
# Installing torch nightly here would just get downgraded by unsloth's dependency resolver.
RUN pip install --no-cache-dir \
    unsloth \
    trl \
    transformers \
    accelerate \
    sentencepiece \
    protobuf \
    tensorboard

# NOTE: flash-attn requires nvcc (CUDA compiler) to build from source, which is not
# present in python:3.11-slim. Without flash-attn, Unsloth uses PyTorch SDPA, which
# still leverages fused attention kernels on sm_120 via torch.backends.cuda.
# To enable flash-attn, switch to a CUDA devel base image (e.g. nvidia/cuda:12.8-devel).

# Image LoRA training dependencies
RUN pip install --no-cache-dir \
    diffusers \
    peft \
    safetensors

# 3D pipeline dependencies (action figure segmentation, mesh processing)
RUN pip install --no-cache-dir \
    trimesh \
    manifold3d

# Fix for NVML: Create symlink for pynvml compatibility
RUN ln -sf /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 /usr/lib/x86_64-linux-gnu/libnvidia-ml.so


# --- MAESTRO L5: Least Privilege ---
# Create a non-root user 'app'
RUN useradd -m -u 1000 app

# Copy the agent code
COPY agents /app/agents

# Ensure permissions
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Fix Git "dubious ownership" for mounted volumes
RUN git config --global --add safe.directory /workspace

# Default command matches docker-compose
CMD ["python", "agents/main.py"]
