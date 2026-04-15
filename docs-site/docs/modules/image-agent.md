---
title: "Module: Image Agent"
---

# Image Agent

ComfyUI pipeline orchestration for 2D image generation.

## Files

| File | Purpose |
|------|---------|
| `agents/specialized/image_gen.py` | Image generation agent |
| `workflow_hunyuan_paint.json` | HunyuanDiT workflow |
| `workflow_hunyuan_paint-2.json` | HunyuanDiT variant |

## Pipelines

| Pipeline | Model | VRAM | Speed | Best For |
|----------|-------|------|-------|----------|
| FLUX.1-schnell | FLUX | ~10 GB | Fast (3–8s) | General purpose |
| SDXL | Stable Diffusion XL | ~8 GB | Medium (10–20s) | High detail |
| HunyuanDiT | Hunyuan | ~12 GB | Slow (20–40s) | Painting style |

## Processing Flow

1. User message classified as `IMAGE` intent
2. Image Agent extracts generation parameters from user prompt
3. Selects appropriate workflow/pipeline
4. Submits workflow to ComfyUI API (`http://{{ execution_node_ip }}:8188`)
5. Polls for completion
6. Saves output to `delivered_artifacts/images/`
7. Returns image path and metadata

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `steps` | 20 | Inference steps |
| `cfg_scale` | 7.0 | Classifier-free guidance |
| `width` | 1024 | Image width |
| `height` | 1024 | Image height |
| `seed` | random | Reproducibility seed |
| `negative_prompt` | "" | What to avoid |

## Skills Memory Integration

Visual rules from Skills Memory are applied:

```python
rules = memory.get_relevant_rules(prompt, "visual_rules")
# e.g., "cyberpunk: neon lighting, rain-slicked streets"
# → Appended to generation prompt
```

## Related

- [User Guide: Art Studio](../user-guide/art-studio.md)
- [Developer: ComfyUI Workflows](../developer-guide/comfyui-workflows.md)
- [Module: ComfyUI Service](services/comfyui.md)
