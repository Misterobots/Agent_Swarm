---
title: Art Studio
---

# Art Studio

Generate images using ComfyUI with FLUX and Stable Diffusion XL pipelines.

## How to Access

- **UI**: Navigate to **Art Studio** in the Hive Mind sidebar
- **Chat**: Describe what you want — the router detects `IMAGE` intent automatically
- **ComfyUI Direct**: `http://{{ execution_node_ip }}:8188` for node-based workflow editing

## Quick Example

In Chat or Art Studio, type:

> *"A cyberpunk cityscape at night with neon reflections on wet streets, cinematic lighting"*

The system:

1. Router classifies intent as `IMAGE`
2. Routes to the image generation agent
3. Translates your prompt for the ComfyUI pipeline
4. Generates the image via FLUX or SD-XL
5. Returns an artifact card with preview and download

## Detailed Usage

### Supported Pipelines

| Pipeline | Description | Best For |
|----------|-------------|----------|
| **FLUX** | High-quality diffusion model | Photorealistic, detailed scenes |
| **SD-XL** | Stable Diffusion XL | Stylized art, faster generation |

### Generation Parameters

You can influence generation by including parameters in your request:

- **Style keywords**: "photorealistic", "anime", "oil painting", "pixel art"
- **Aspect ratio**: "portrait", "landscape", "square"
- **Quality hints**: "high detail", "quick sketch"

The system maps these to appropriate ComfyUI workflow parameters (CFG scale, steps, scheduler).

### Custom Workflows

Power users can access ComfyUI directly at `http://{{ execution_node_ip }}:8188` to:

- Build node-based generation workflows
- Import custom pipelines (JSON workflow files)
- Fine-tune parameters like sampler, steps, CFG, and denoise

### Output

Generated images are:

- Displayed as artifact cards in the UI with download buttons
- Stored in ComfyUI's output directory
- Available through MinIO object storage on the Control Node

## Tips & Common Patterns

!!! tip "Prompt Engineering"
    ComfyUI works best with descriptive prompts. Include: subject, style, lighting, mood, camera angle.

!!! tip "GPU Contention"
    Image generation uses significant VRAM. If an inference or training job is running, generation may queue. Check GPU status in the Monitor workspace.

!!! tip "Hunyuan Workflows"
    For image-to-3D pipeline integration, see [3D Generation](3d-generation.md).

## Related

- [3D Generation](3d-generation.md) — image-to-3D pipeline
- [Module: ComfyUI Service](../modules/services/comfyui.md) — service details
- [Procedure: Add ComfyUI Workflow](../developer-guide/comfyui-workflows.md) — import custom workflows
- [Tutorial: Generate an Image](../tutorials/generate-image.md) — step-by-step walkthrough
- [Troubleshooting: ComfyUI](../troubleshooting/comfyui.md)
