---
title: Environment Variables
---

# Environment Variables Reference

Complete reference for all environment variables used in `network.env`.

## Model Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SOLVER_MODEL` | Primary response generation model | `{{ solver_model }}` |
| `ROUTER_MODEL` | Intent classification model | `{{ router_model }}` |
| `VERIFIER_MODEL` | Safety/quality verification model | `{{ verifier_model }}` |

## Ollama

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama server address | `{{ lovelace_ip }}` |
| `OLLAMA_PORT` | Ollama API port | `{{ ollama_port }}` |
| `OLLAMA_FLASH_ATTENTION` | Enable Flash Attention | `1` |
| `OLLAMA_NUM_PARALLEL` | Max concurrent requests | `4` |
| `OLLAMA_MAX_LOADED_MODELS` | Max models in VRAM | `3` |
| `OLLAMA_KEEP_ALIVE` | Idle model unload timeout | `10m` |

## Node Addresses

| Variable | Description | Default |
|----------|-------------|---------|
| `HOPPER_IP` | Control Plane address | `{{ hopper_ip }}` |
| `LOVELACE_IP` | Execution Plane address | `{{ lovelace_ip }}` |
| `TURING_IP` | Gateway / Turing address | `{{ turing_ip }}` |

## Langfuse

| Variable | Description |
|----------|-------------|
| `LANGFUSE_HOST` | Langfuse server URL |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public API key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |

## PostgreSQL

| Variable | Description |
|----------|-------------|
| `POSTGRES_HOST` | PostgreSQL server address |
| `POSTGRES_PORT` | PostgreSQL port (default: 5432) |
| `POSTGRES_USER` | Database username |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |

## Home Assistant

| Variable | Description |
|----------|-------------|
| `HA_URL` | Home Assistant API URL |
| `HA_TOKEN` | Long-lived access token |

## SPIRE

| Variable | Description |
|----------|-------------|
| `SPIRE_SERVER_ADDRESS` | SPIRE server endpoint |
| `SPIRE_TRUST_DOMAIN` | Trust domain (e.g., `home-ai-lab`) |

## ComfyUI

| Variable | Description | Default |
|----------|-------------|---------|
| `COMFYUI_HOST` | ComfyUI server address | `{{ lovelace_ip }}` |
| `COMFYUI_PORT` | ComfyUI API port | `8188` |

## Agent Runtime

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_RUNTIME_PORT` | API listen port | `{{ agent_runtime_port }}` |
| `STREAM_TIMEOUT` | SSE stream timeout (seconds) | `120` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Swarm Planning & Solving Limits

Control how long the swarm spends on planning and solving phases:

| Variable | Description | Default |
|----------|-------------|---------|
| `PLANNING_MAX_ITER` | Maximum number of planning output chunks (`0` = unlimited) | `0` |
| `PLANNING_MAX_TIME` | Maximum planning time in seconds (`0` = unlimited) | `0` |
| `SOLVING_MAX_ITER` | Maximum number of solving/verification/correction iterations | `2` |
| `SOLVING_MAX_TIME` | Maximum solving time in seconds (`0` = unlimited) | `0` |

If both a time and iteration limit are set, the phase stops at whichever comes first. If 100% confidence is reached before the limit, the swarm proceeds to final steps immediately.

!!! warning "Security"
    Never commit `network.env` to version control. It contains secrets. See [Secrets Management](../admin-guide/operations/secrets.md).


