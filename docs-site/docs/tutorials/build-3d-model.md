---
title: "Tutorial: Build a 3D Model"
---

# Build a 3D Model

Generate 3D assets from text descriptions.

## What You'll Learn

- How to trigger 3D generation
- The multi-stage 3D pipeline
- How to iterate on results

## Prerequisites

- ComfyUI running with 3D-capable models
- Sufficient GPU VRAM (16 GB+ recommended)

## Step 1: Describe Your Object

In the Hive UI:

> Generate a 3D model of a medieval sword

The Router classifies this as `3d_generation` and routes to the 3D Pipeline agent.

## Step 2: Understand the Pipeline

The 3D generation pipeline follows multiple stages:

1. **Prompt Enhancement** — the solver enriches your description
2. **Reference Image** — ComfyUI generates a reference image
3. **Multi-View Generation** — creates views from multiple angles
4. **Mesh Reconstruction** — builds 3D geometry from the views
5. **Texture Mapping** — applies textures to the mesh

## Step 3: Review the Output

The agent returns:

- A preview render of the 3D model
- Download link for the mesh file (`.obj` or `.glb`)
- The enhanced prompt used

## Step 4: Iterate

Refine your model:

> Make the sword blade more curved and add runes on the blade

The pipeline re-runs with the adjusted description.

## Step 5: Action Figure Mode

For character models, use the Action Figure pipeline:

> Create an action figure of a robot samurai

This uses a specialized workflow optimized for character models with proper proportions and articulation.

## Tips

- Start simple: basic shapes before complex scenes
- Specify material: "metallic", "wooden", "glass"
- Specify style: "realistic", "low-poly", "cartoon"
- Single objects work better than full scenes

## Next Steps

- [User Guide: 3D Generation](../user-guide/3d-generation.md) — full reference
- [Modules: 3D Pipeline](../modules/3d-pipeline.md) — technical details
