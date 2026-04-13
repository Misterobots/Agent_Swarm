# OpenClaude gRPC Server — R730 Gateway Deployment
# Headless inference gateway with model routing.
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    protobuf \
    requests \
    cachetools

# Copy agent code (gRPC server + model router + shared config)
COPY agents/grpc /app/agents/grpc
COPY agents/config.py /app/agents/config.py
COPY agents/__init__.py /app/agents/__init__.py
COPY network.env /app/network.env

# Generate protobuf stubs at build time
RUN cd /app/agents/grpc && \
    python -m grpc_tools.protoc \
        -I. \
        --python_out=. \
        --grpc_python_out=. \
        openclaude.proto

# Non-root user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import grpc; ch=grpc.insecure_channel('localhost:50051'); grpc.channel_ready_future(ch).result(timeout=3)" || exit 1

CMD ["python", "-m", "agents.grpc.server", "--port", "50051", "--workers", "4"]
