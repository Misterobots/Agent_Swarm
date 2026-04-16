# Art Studio Guide

> **Back to:** [Documentation Index](../INDEX.md)

---

## Overview

The Art Studio is a dedicated workspace for all creative generation — images, 3D models, and 3D-printable posable action figures. It replaces the old "Media" workspace and is accessible from the sidebar workspace switcher.

Inspired by tools like Meshy and Hunyuan3D, the Art Studio brings image-to-3D and text-to-3D pipelines into a single unified interface running entirely on local hardware.

---

## How It's Triggered

When you type a creative request in Chat (image, 3D model, or action figure), the router detects the creative intent and responds with a message directing you to switch to the Art Studio workspace. Your prompt is automatically saved and pre-filled when you open Art Studio — no need to retype anything.

You can also navigate to Art Studio directly from the sidebar at any time.

---

## Generation Modes

The Art Studio supports three modes, selectable from the left panel on the Generate tab.

### 1. Image Generation

Uses the ComfyUI backend with Flux, SDXL, and SD1.5 model checkpoints.

**Controls:**

| Setting | Description |
|---------|-------------|
| Model Checkpoint | Which diffusion model to use (Flux, SDXL, SD1.5) |
| CFG Scale | How closely the output follows the prompt — higher = more literal |
| Steps | Number of denoising steps — more steps = higher quality but slower |
| Aspect Ratio | Output dimensions (square, portrait, landscape presets) |
| Sampler | Sampling algorithm (Euler, DPM++, etc.) |
| Scheduler | Noise schedule (normal, karras, exponential) |
| Seed | Fixed seed for reproducible results, or random |

Additional settings are available in the sidebar expander under "Advanced."

---

### 2. 3D Model Generation

Two pipelines are available, each with different speed/quality tradeoffs:

| Pipeline | Output | Time | Notes |
|----------|--------|------|-------|
| **TripoSG** | Untextured GLB mesh | ~2 min | Fast iteration, good for shape exploration |
| **Hunyuan 3D** | Textured GLB mesh | ~8 min | Full color/texture, higher detail |

Both pipelines run through ComfyUI for mesh generation. You can either:

- **Describe what you want** — the system auto-generates concept art first, then converts it to 3D
- **Upload an image directly** — skip concept art and go straight to mesh generation

---

### 3. Action Figure Generation

A full image-to-3D-printable posable action figure pipeline. This takes a character description, generates a print-ready set of segmented body parts with ball-and-socket joints.

**Pipeline flow:**

```
Text prompt
  → T-pose concept art generation
    → Base 3D mesh
      → Body part segmentation
        → Ball-and-socket joint insertion
          → Individual STL files + assembly manifest
```

**Joint locations (12 total):** neck, shoulders (2), elbows (2), wrists (2), waist, hips (2), knees (2)

**Configuration:**

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Figure Height | 50–300 mm | — | Total height of the assembled figure |
| Joint Clearance | 0.1–0.5 mm | 0.3 mm | Gap between ball and socket for print tolerance |
| Per-Joint Toggles | on/off | all on | Enable or disable specific joints individually |

**Clearance recommendations:**
- **FDM printers:** 0.3 mm (default)
- **Resin printers:** 0.15 mm

**Output:**
- Individual STL files for each body part
- Assembly manifest JSON describing how parts connect

---

## Workspace Layout

The Art Studio uses a tabbed layout with three top-level tabs: **Generate**, **Gallery**, and **Exports**.

### Generate Tab

The main workspace, split into two panels:

**Left Panel (Controls):**
- **Mode selector** — switch between Image, 3D Model, and Action Figure
- **Generation controls** — mode-specific settings that change based on selected mode (see Generation Modes above)

**Right Panel (Prompt + History):**
- **Prompt bar** — text input with a Generate button. Pre-filled automatically when redirected from Chat
- **Generation history** — live feed of all generation attempts with status indicators (generating/complete/error), progress bars, and result output

### Gallery Tab

Browse all generated assets across two sub-tabs:

| Sub-Tab | What It Shows |
|---------|---------------|
| **Images** | Grid of generated images with thumbnails, filenames, prompt metadata, file sizes, and download links |
| **3D Files** | Cards for GLB/STL/OBJ files from output directories, categorized by type (models vs action figures) with file sizes |

A refresh button reloads both galleries from the backend.

### Exports Tab

A chronological generation log listing all completed generations with mode icons, prompts, timestamps, and result details.

---

## Tips

- **Describe characters in detail** for action figures — armor, clothing, proportions, and accessories all affect the quality of body part segmentation.
- **T-pose concept art works best:** arms extended, symmetrical stance, clean silhouette. The segmentation pipeline relies on clear limb separation.
- **FDM printers:** use the default 0.3 mm joint clearance. **Resin:** reduce to 0.15 mm for tighter fits.
- **Ball joints should press-fit into sockets** after printing. If joints are too loose, reduce clearance by 0.05 mm increments. If too tight, increase.
- **For fast iteration on 3D shapes**, use TripoSG first to validate the form, then switch to Hunyuan 3D for the final textured version.

---

## Source References

<details markdown>
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

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|---------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-28 | AI-Copilot | Initial Art Studio guide created |

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

## Functionality Testing

### Automated Tests

| Test File | What It Covers |
|-----------|----------------|
| `tests/test_art_studio.py` | Generation API endpoints, mode switching, gallery refresh |

### Manual Verification

1. **Image generation**: Switch to Art Studio → select Image mode → enter a prompt → click Generate → verify image appears in history and Gallery tab.
2. **3D generation**: Select 3D Model mode → choose TripoSG → enter a prompt → verify GLB file appears.
3. **Action figure**: Select Action Figure mode → describe a character → verify STL files are generated with correct joint count.
4. **Router redirect**: In Chat, type "generate an image of a sunset" → verify the router directs you to Art Studio with the prompt pre-filled.

---

*[Back to Index](../INDEX.md)*
