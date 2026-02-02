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
    plotly \
    plotly \
    python-logging-loki \
    redis \
    apscheduler \
    numpy \
    opencv-python-headless

# Copy the agent code (This is also mounted as volume in docker-compose for dev)
COPY agents /app/agents

# Default command matches docker-compose
CMD ["python", "agents/main.py"]
