---
title: Local Development
---

# Local Development

Set up Memex for local development and testing.

## Prerequisites

- Python 3.11+
- Docker Desktop with GPU support
- Git
- NVIDIA drivers (for GPU inference)

## Clone and Setup

```bash
git clone https://github.com/your-org/Agent_Swarm.git
cd Agent_Swarm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Start Ollama

```bash
# Pull required models
docker run -d --gpus all -p {{ ollama_port }}:{{ ollama_port }} \
    --name ollama -v ollama_data:/root/.ollama \
    ollama/ollama

docker exec ollama ollama pull {{ solver_model }}
docker exec ollama ollama pull qwen3:8b       # Router (intent classifier)
docker exec ollama ollama pull {{ verifier_model }}
```

## Configure Environment

```bash
cp network.env.example network.env
```

Edit `network.env` for local development:

```bash
LOVELACE_IP=127.0.0.1
HOPPER_IP=127.0.0.1
TURING_IP=127.0.0.1
OLLAMA_HOST=http://localhost:{{ ollama_port }}
AGENT_RUNTIME_PORT={{ agent_runtime_port }}
```

## Run Agent Runtime

```bash
cd agents
python main.py
```

The runtime starts at `http://localhost:{{ agent_runtime_port }}`.

## Test Your Changes

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_valid.py

# Quick health check
curl http://localhost:{{ agent_runtime_port }}/
```

## Project Structure

```
agents/
+-- main.py                    # FastAPI app entry point
+-- church.py                  # Thin router wrapper — intent dispatch, session init
+-- semantic_router.py         # Intent classification (qwen3:8b + 5-rule fast-path)
+-- handlers/                  # Intent handler modules (one file per intent group)
+-- routing/                   # Pending-context multi-turn gates
+-- mars_loop.py               # MarsRL verification pipeline
+-- lamport.py                 # Coordinator entry point (re-exports coordination/)
+-- coordination/              # Multi-agent orchestration modules
+-- config.py                  # Configuration loading
+-- security/                  # SPIFFE, JWT-ACE, auth middleware
+-- specialized/               # Image, voice, IoT, 3D agents
+-- expertise/                 # Template registry, A/B testing
+-- tools/                     # Agent tools (file_ops, terminal, etc.)
```

## Development Workflow

1. Create a feature branch: `git checkout -b feature/my-change`
2. Make changes to agent code in `agents/`
3. Test locally with `pytest` and manual `curl` requests
4. Check logs in `logs/` directory
5. Submit a pull request

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG python agents/main.py
```

### View Langfuse Traces Locally

If running Langfuse locally:

```bash
docker compose -f control_plane/docker-compose.yml up -d langfuse clickhouse postgres
```

Access at `http://localhost:3000`.

## Related

- [Getting Started: Developer Quickstart](../getting-started/quickstart-developer.md) — condensed setup
- [Developer: Adding Agents](adding-agents.md) — extend the agent system

