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
    && rm -rf /var/lib/apt/lists/*

# Install Common Python Dependencies for AI Agents
RUN pip install --no-cache-dir \
    phidata \
    ollama \
    openai \
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
    opencv-python-headless \
    streamlit-monaco \
    redis

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
