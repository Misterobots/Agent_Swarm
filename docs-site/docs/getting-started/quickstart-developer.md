---
title: "Quickstart: Developers"
---

# Quickstart: Developers

Get the Memex codebase running locally for development.

## Prerequisites

- Python 3.11+
- Docker Desktop (for dependent services)
- Git
- A running Ollama instance (local or remote)

## Step 1: Clone and Install

```bash
git clone https://github.com/Misterobots/Agent_Swarm.git
cd Agent_Swarm
pip install -r requirements.txt
```

## Step 2: Configure for Local Development

Create a local override in `agents/config.py` or set environment variables:

```bash
export OLLAMA_HOST=http://localhost:11434
export LLM_PROVIDER=ollama
export LANGFUSE_HOST=http://localhost:3000  # or disable tracing
```

!!! tip "Minimal Setup"
    You only need Ollama running locally to work on the agent runtime. The control plane services (SPIRE, Langfuse, PostgreSQL) are optional for development — the runtime falls back gracefully when they're unavailable.

## Step 3: Pull Required Models

```bash
ollama pull qwen3.5:9b                  # Solver / Corrector
ollama pull nemotron-orchestrator:8b     # Router
ollama pull llama-guard-3:8b             # Safety verifier
ollama pull llama3.2:3b                  # Lightweight tasks
```

## Step 4: Start the Agent Runtime

```bash
cd Agent_Swarm
uvicorn agents.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload
```

The `--reload` flag enables hot-reloading on code changes.

Verify it's running:

```bash
curl http://localhost:8000/
# {"status": "online", "system": "Home AI Lab Swarm"}

curl http://localhost:8000/v1/models
# Returns available model list
```

## Step 5: Send a Test Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a Python hello world"}],
    "model": "default",
    "stream": false
  }'
```

## Step 6: Run Tests

```bash
pytest tests/ -v
```

## Project Structure

```
Agent_Swarm/
+-- agents/                  # Core runtime (FastAPI server, agents, routing)
¦   +-- main.py              # FastAPI app, endpoints, lifecycle
¦   +-- router.py            # Intent-based request routing
¦   +-- semantic_router.py   # Intent classifier (14 categories)
¦   +-- mars_loop.py         # MarsRL: Solver ? Verifier ? Corrector
¦   +-- coordinator.py       # Multi-worker orchestration
¦   +-- config.py            # All configuration constants
¦   +-- tools/               # MCP tools (file, terminal, web, IoT)
¦   +-- specialized/         # Domain agents (image, voice, IoT, 3D)
¦   +-- security/            # SPIFFE auth, JWT-ACE, capability gates
¦   +-- training/            # GRPO trainer, A/B testing, datasets
¦   +-- mcp/                 # Model Context Protocol server
+-- control_plane/           # Control Node Docker Compose
+-- execution_plane/         # Execution Node Docker Compose
+-- turing_gateway/            # Gateway Node Docker Compose
+-- ui/                      # Next.js frontend (Hive Mind UI)
+-- services/                # Standalone services (voice_engine, saltbox)
+-- scripts/                 # Deployment and utility scripts
+-- docs-site/               # This documentation site
+-- tests/                   # Test suite
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `agents/main.py` | FastAPI app — all HTTP endpoints, startup lifecycle |
| `agents/router.py` | Request routing — intent detection ? agent dispatch |
| `agents/mars_loop.py` | MarsRL quality loop — Solver ? Verifier ? Corrector |
| `agents/config.py` | Every configuration constant — IPs, models, URLs, thresholds |
| `agents/semantic_router.py` | Intent classifier — 14 categories using {{ router_model }} |
| `agents/coordinator.py` | Multi-worker orchestration — decompose, research, synthesize, implement |

## Next Steps

- [Adding Agents](../developer-guide/adding-agents.md) — create a new specialized agent
- [Adding Tools](../developer-guide/adding-tools.md) — register an MCP tool
- [API Reference](../developer-guide/api/chat-completions.md) — full endpoint documentation
- [Architecture](../architecture/index.md) — understand the system design


