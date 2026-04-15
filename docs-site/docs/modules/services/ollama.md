---
title: "Service: Ollama"
---

# Ollama

Local LLM inference engine.

## Deployment

| Instance | Node | Port | GPU |
|----------|------|------|-----|
| Primary | Execution ({{ execution_node_ip }}) | {{ ollama_port }} | RTX 5060 Ti 16 GB |
| Secondary | Gateway ({{ gateway_node_ip }}) | 11435 | RTX 3070 Ti 8 GB |

## Purpose

Ollama serves all LLM inference for Agent Swarm — chat, routing, verification, and safety checks.

## API

OpenAI-compatible API:

```bash
# Chat completion
curl http://{{ execution_node_ip }}:{{ ollama_port }}/v1/chat/completions \
    -d '{"model": "{{ solver_model }}", "messages": [{"role": "user", "content": "Hello"}]}'

# List models
curl http://{{ execution_node_ip }}:{{ ollama_port }}/api/tags

# Pull model
curl -X POST http://{{ execution_node_ip }}:{{ ollama_port }}/api/pull \
    -d '{"name": "{{ solver_model }}"}'
```

## Configuration

| Variable | Value | Description |
|----------|-------|-------------|
| `OLLAMA_NUM_PARALLEL` | 2 | Concurrent requests |
| `OLLAMA_MAX_LOADED_MODELS` | 3 | Models in VRAM |
| `OLLAMA_KEEP_ALIVE` | 10m | Idle unload time |
| `OLLAMA_FLASH_ATTENTION` | 1 | Flash Attention |

## Related

- [Admin: Models](../../admin-guide/configuration/models.md)
- [Admin: Scaling](../../admin-guide/operations/scaling.md)
