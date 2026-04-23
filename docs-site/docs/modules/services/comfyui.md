---
title: "Service: ComfyUI"
---

# ComfyUI

Node-based image generation engine.

## Deployment

| Property | Value |
|----------|-------|
| **Node** | Execution ({{ lovelace_ip }}) |
| **Port** | 8188 |
| **URL** | `http://{{ lovelace_ip }}:8188` |
| **GPU** | Required (CUDA) |
| **Compose** | `execution_plane/docker-compose.yml` |

## Purpose

ComfyUI runs image generation workflows as directed acyclic graphs (DAGs) of processing nodes. Memex submits workflows via the ComfyUI API.

## API Usage

```python
import requests

# Queue a workflow
response = requests.post(
    f"http://{{ lovelace_ip }}:8188/prompt",
    json={"prompt": workflow_json, "client_id": "agent-swarm"},
)
prompt_id = response.json()["prompt_id"]

# Check status
status = requests.get(f"http://{{ lovelace_ip }}:8188/history/{prompt_id}")
```

## Installed Models

| Model | Type | Size |
|-------|------|------|
| FLUX.1-schnell | Checkpoint | ~12 GB |
| SDXL | Checkpoint | ~6.5 GB |
| HunyuanDiT | Checkpoint | ~6 GB |

## Related

- [User Guide: Art Studio](../../user-guide/art-studio.md)
- [Developer: ComfyUI Workflows](../../developer-guide/comfyui-workflows.md)
- [Module: Image Agent](../image-agent.md)


