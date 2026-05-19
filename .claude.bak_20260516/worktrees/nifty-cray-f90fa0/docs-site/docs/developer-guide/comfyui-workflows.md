---
title: ComfyUI Workflows
---

# ComfyUI Workflows

How to create and deploy custom image generation workflows.

## Overview

Memex uses ComfyUI for all image generation. Workflows are JSON files that define the node graph for generation pipelines.

## Workflow Location

```
workflow_hunyuan_paint.json     # HunyuanDiT painting workflow
workflow_hunyuan_paint-2.json   # HunyuanDiT variant
```

Custom workflows go in the same directory or in `agents/specialized/workflows/`.

## Workflow Structure

ComfyUI workflows are JSON documents describing a directed acyclic graph (DAG) of processing nodes:

{% raw %}
```json
{
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "flux1-schnell.safetensors"
        }
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "{{PROMPT}}",
            "clip": ["1", 1]
        }
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["2", 0],
            "seed": "{{SEED}}",
            "steps": 20,
            "cfg": 7.0
        }
    }
}
```
{% endraw %}

## Creating a Custom Workflow

### 1. Design in ComfyUI UI

1. Access ComfyUI at `http://{{ lovelace_ip }}:8188`
2. Build your node graph visually
3. Click **Save (API Format)** to export the JSON

### 2. Add Template Variables

Replace dynamic values with template variables:

| Variable | Replaced With |
|----------|---------------|
| `{% raw %}{{PROMPT}}{% endraw %}` | User's text prompt |
| `{% raw %}{{NEGATIVE}}{% endraw %}` | Negative prompt |
| `{% raw %}{{SEED}}{% endraw %}` | Random or specified seed |
| `{% raw %}{{WIDTH}}{% endraw %}` | Image width |
| `{% raw %}{{HEIGHT}}{% endraw %}` | Image height |
| `{% raw %}{{STEPS}}{% endraw %}` | Inference steps |

### 3. Register the Workflow

Add the workflow to the image generation agent:

```python
# In agents/specialized/image_gen.py
WORKFLOWS = {
    "flux-schnell": "workflows/flux_schnell.json",
    "sdxl": "workflows/sdxl.json",
    "hunyuan-paint": "workflow_hunyuan_paint.json",
    "custom": "workflows/my_custom.json",
}
```

### 4. Test

```bash
curl -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Generate an image of a mountain sunset using custom workflow"}],
        "stream": false
    }'
```

## Available Pipelines

| Pipeline | Model | Best For | VRAM |
|----------|-------|----------|------|
| FLUX.1-schnell | FLUX | Fast generation, good quality | ~10 GB |
| SDXL | Stable Diffusion XL | High resolution, detailed | ~8 GB |
| HunyuanDiT | Hunyuan | Painting style, Chinese art | ~12 GB |

## Output Storage

Generated images are saved to `delivered_artifacts/images/` with metadata:

```
delivered_artifacts/
+-- images/
    +-- img_20260410_143022_abc123.png
    +-- img_20260410_143022_abc123.json  # metadata
```

## Related

- [User Guide: Art Studio](../user-guide/art-studio.md)  user-facing guide
- [Module: Image Agent](../modules/image-agent.md)  agent implementation
- [Admin: Scaling](../admin-guide/operations/scaling.md)  GPU considerations


