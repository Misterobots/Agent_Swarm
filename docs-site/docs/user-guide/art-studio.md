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

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|-----------|
| `ui/src/app/art-studio/page.tsx` | Implementation | Art Studio page component and layout |
| `ui/src/components/art-studio/GeneratePanel.tsx` | Implementation | Generation controls (Image, 3D, Action Figure) |
| `ui/src/components/art-studio/GalleryPanel.tsx` | Implementation | Gallery grid with image/3D tabs |
| `ui/src/stores/artStudioStore.ts` | Implementation | Client-side state (mode, settings, history) |
| `agents/router.py` | Implementation | Intent detection routing creative requests |
| `r730_gateway/comfyui/` | Infrastructure | ComfyUI workflows for image & 3D generation |
| [TripoSG](https://github.com/VAST-AI-Research/TripoSG) | External | Text/image-to-3D mesh pipeline |
| [Hunyuan3D](https://github.com/Tencent/Hunyuan3D-2) | External | High-quality textured 3D generation |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | External | Diffusion model workflow engine |

</details>

---

## Maintenance & Update Guide

### Adding a New Generation Mode

1. Add a new mode option in `GeneratePanel.tsx` mode selector.
2. Create a ComfyUI workflow JSON for the new pipeline.
3. Add a backend endpoint in the agent runtime to handle the new workflow type.
4. Update the router intent classification if it needs to detect the new creative sub-type.

### Updating Model Checkpoints

1. Place new checkpoint files in the ComfyUI `models/checkpoints/` directory on the Execution Node.
2. Restart ComfyUI: `docker compose restart comfyui`.
3. Update the model selector options in `GeneratePanel.tsx` if needed.

### Adjusting Action Figure Joint Parameters

1. Joint definitions are in the segmentation pipeline code. Modify joint positions, socket sizes, or clearance defaults there.
2. Test with a known character prompt and verify STL output in a slicer before deploying changes.

---

---

## Functionality Testing

### Automated Tests

| Test File | What It Covers |
|-----------|----------------|
| `tests/test_art_studio.py` | Generation API endpoints, mode switching, gallery refresh |

### Manual Verification

1. **Image generation**: Switch to Art Studio ? select Image mode ? enter a prompt ? click Generate ? verify image appears in history and Gallery tab.
2. **3D generation**: Select 3D Model mode ? choose TripoSG ? enter a prompt ? verify GLB file appears.
3. **Action figure**: Select Action Figure mode ? describe a character ? verify STL files are generated with correct joint count.
4. **Router redirect**: In Chat, type "generate an image of a sunset" ? verify the router directs you to Art Studio with the prompt pre-filled.

---

*[Back to Index](../index.md)*
