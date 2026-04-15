---
title: "Module: GPU Allocator"
---

# GPU Allocator

VRAM reservation and model scheduling.

## Files

| File | Purpose |
|------|---------|
| `agents/gpu_allocator.py` | GPU memory management |

## Purpose

The GPU Allocator tracks VRAM usage and prevents out-of-memory errors by:

- Tracking which models are loaded in VRAM
- Preventing concurrent operations that exceed VRAM budget
- Coordinating between Ollama, ComfyUI, and Voice Engine

## VRAM Budget

### Execution Node (RTX 5060 Ti — 16 GB)

| Consumer | VRAM | Priority |
|----------|------|----------|
| {{ solver_model }} | ~6 GB | High |
| {{ router_model }} | ~5 GB | High |
| {{ verifier_model }} | ~5 GB | Medium |
| ComfyUI (FLUX) | ~10 GB | On-demand |
| Voice (Qwen3-TTS) | ~3 GB | On-demand |

!!! note "Not All Fit Simultaneously"
    Total VRAM needed for all models exceeds 16 GB. The allocator and Ollama cooperate to load/unload models dynamically.

## Interaction with Ollama

Ollama handles its own model lifecycle:

| Ollama Setting | Effect |
|---------------|--------|
| `OLLAMA_MAX_LOADED_MODELS=3` | Maximum 3 models in VRAM |
| `OLLAMA_KEEP_ALIVE=10m` | Unload idle models after 10 min |

The GPU Allocator complements Ollama by scheduling non-Ollama GPU tasks (ComfyUI, voice synthesis) to avoid conflicts.

## Related

- [Admin: Models Configuration](../admin-guide/configuration/models.md) — VRAM settings
- [Admin: Scaling](../admin-guide/operations/scaling.md) — adding GPU capacity
