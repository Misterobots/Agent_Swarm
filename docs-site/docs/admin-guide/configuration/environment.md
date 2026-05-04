---
title: Environment Variables
---

# Environment Variables

Reference for all variables in `network.env`.

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `HOPPER_IP` | `{{ hopper_ip }}` | Control Plane IP |
| `LOVELACE_IP` | `{{ lovelace_ip }}` | Execution Plane IP |
| `TURING_IP` | `{{ turing_ip }}` | Gateway Node IP |
| `AGENT_RUNTIME_PORT` | `{{ agent_runtime_port }}` | Agent Runtime FastAPI port |
| `OLLAMA_PORT` | `{{ ollama_port }}` | Ollama API port |

## Ollama

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `0.0.0.0:{{ ollama_port }}` | Listen address |
| `OLLAMA_NUM_PARALLEL` | `2` | Max concurrent requests |
| `OLLAMA_MAX_LOADED_MODELS` | `3` | Max models in VRAM |
| `OLLAMA_KEEP_ALIVE` | `10m` | Idle unload time |
| `OLLAMA_FLASH_ATTENTION` | `1` | Enable Flash Attention |
| `OLLAMA_ORIGINS` | `*` | CORS origins |

## Models

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLVER_MODEL` | `{{ solver_model }}` | Primary generation model |
| `ROUTER_MODEL` | `{{ router_model }}` | Intent classification model |
| `VERIFIER_MODEL` | `{{ verifier_model }}` | Content safety model |

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | *(secret)* | PostgreSQL password |
| `POSTGRES_DB` | `agent_swarm` | Database name |
| `DATABASE_URL` | `postgresql://...` | Full connection string |

## Langfuse

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_SECRET_KEY` | *(secret)* | Session encryption key |
| `LANGFUSE_PUBLIC_KEY` | *(generated)* | Public API key |
| `LANGFUSE_HOST` | `http://{{ hopper_ip }}:3000` | Langfuse URL |

## SPIRE

| Variable | Default | Description |
|----------|---------|-------------|
| `SPIRE_SERVER_ADDRESS` | `{{ hopper_ip }}:8081` | SPIRE server endpoint |
| `SPIRE_TRUST_DOMAIN` | `home-ai-lab` | Trust domain name |

## Home Assistant

| Variable | Default | Description |
|----------|---------|-------------|
| `HA_URL` | `http://192.168.2.100:8123` | Home Assistant URL |
| `HA_TOKEN` | *(secret)* | Long-lived access token |

## MinIO

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ROOT_USER` | `minio` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | *(secret)* | MinIO admin password |
| `MINIO_ENDPOINT` | `{{ hopper_ip }}:9000` | MinIO API endpoint |

## Training Dispatcher

Variables that activate and configure the Training Dispatcher on Lovelace.

| Variable | File | Description |
|----------|------|-------------|
| `DISPATCHER_SECRET` | `execution_plane/.env` **and** `network.env` | Shared secret — must match on **both** Lovelace and Turing. Set in `.env` so the dispatcher container reads it; set in `network.env` so `agent_runtime` reads it to populate the `X-Dispatcher-Key` header. |
| `DISPATCHER_URL` | `network.env` | Full URL of the dispatcher, e.g. `http://192.168.2.101:8001`. Read by `agent_runtime` to know where to send jobs. |
| `EXPORT_MIN_SCORE` | `network.env` (optional) | Minimum MarsRL reward score for trace export. Default: `0.85`. |
| `HF_TOKEN` | `network.env` (optional) | HuggingFace token for gated dataset access. |

!!! warning "Both files required"
    `DISPATCHER_SECRET` must be present in **both** `execution_plane/.env` (for the dispatcher container on Lovelace) and `network.env` (for `agent_runtime` on Turing). If either is missing, jobs will fail with a 401 or 503 error.

### Generating the secret

```powershell
# Windows (PowerShell)
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
# Linux
openssl rand -hex 32
```

Use the same output in both files.

### Activating after setting the secret

```bash
# Lovelace — start dispatcher
cd execution_plane && docker compose up -d training-dispatcher

# Turing — restart agent_runtime to pick up new env vars
docker compose up -d --force-recreate agent-runtime
```

Verify:

```bash
curl http://192.168.2.101:8001/health
# {"status":"online","available_archetypes":["coder","coordinator","researcher","creative"],...}
```

## Usage

All Docker Compose files load `network.env` via the `--env-file` flag:

```bash
docker compose --env-file ../network.env up -d
```

Variables are interpolated into compose files:

```yaml
services:
  agent-runtime:
    environment:
      - OLLAMA_HOST=http://${LOVELACE_IP}:${OLLAMA_PORT}
      - SOLVER_MODEL=${SOLVER_MODEL}
```

## Related

- [Admin: Secrets Management](../operations/secrets.md) — credential security
- [Admin: Docker Compose](docker-compose.md) — compose file reference


