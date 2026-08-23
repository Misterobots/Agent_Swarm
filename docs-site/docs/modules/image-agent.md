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
4. Submits workflow to ComfyUI API (`http://{{ lovelace_ip }}:8188`)
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

## Model Registry

Clients request a curated profile ID rather than a raw ComfyUI checkpoint filename. The registry resolves the profile to the best available checkpoint at request time and records the resolved checkpoint on the artifact's metadata.

| Profile | Role | Trainable | Notes |
|---------|------|-----------|-------|
| `auto` | Adaptive selector, normal default | No | Picks best available curated profile |
| `flux-dev-quality` | Quality-first | Yes | Highest fidelity when available |
| `flux-schnell-preview` | Fast ideation | Yes | Lower latency than the quality path |
| `sdxl-general` | Balanced quality | Yes | Practical modern default |
| `sdxl-turbo-preview` | Fast preview | Yes | Cheap UI-side iteration |
| `sd15-fast-legacy` | Compatibility | Yes | 3D bootstrap / emergency fallback only |

Direct checkpoint selection is still supported for compatibility, but the registry is the intended product contract — ComfyUI remains the execution engine underneath.

## Job Persistence

Image generation jobs are Redis-backed (with an in-memory fallback) so job status survives `agent_runtime` restarts and is queryable via `GET /v1/art/jobs/{job_id}`. Implemented in `agents/media_job_store.py`.

## LoRA Training Worker

A dedicated worker (`agents/training/image_lora_worker.py`) supports adapter training on top of a stable base checkpoint instead of swapping base models:

1. Prepares a dataset manifest from curated/kept generations
2. Resolves the selected base profile to its checkpoint
3. Writes a training plan
4. Executes a trainer command when `IMAGE_LORA_TRAINER_COMMAND` is configured — otherwise runs plan-only

Trained adapters are versioned and registered back into the model registry.

## API Routes

| Route | Purpose |
|-------|---------|
| `GET /v1/art/models` | List curated profiles/registry |
| `GET /api/v1/media/comfyui/checkpoints` | List raw ComfyUI checkpoints |
| `POST /v1/art/generate/image` | Submit a generation request |
| `GET /v1/art/jobs/{job_id}` | Poll job status |
| `POST /api/v1/media/training/image-lora` | Queue a LoRA training run |
| `GET /api/v1/media/training/image-lora/{run_id}` | Poll training run status |

## Related

- [User Guide: Art Studio](../user-guide/art-studio.md)
- [Developer: ComfyUI Workflows](../developer-guide/comfyui-workflows.md)
- [Module: ComfyUI Service](services/comfyui.md)


