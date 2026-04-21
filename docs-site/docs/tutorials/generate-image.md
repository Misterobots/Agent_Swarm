---
title: "Tutorial: Generate an Image"
---

# Generate an Image

Create AI-generated images using natural language prompts.

## What You'll Learn

- How to trigger the Image Agent
- How prompts are enhanced
- How to adjust style and quality

## Step 1: Open the Chat

Navigate to `http://{{ turing_ip }}/` and open a new conversation.

## Step 2: Describe Your Image

Type a natural language description:

> Create a watercolor painting of a cozy mountain cabin at sunset

The Router detects `image_generation` intent and routes to the Image Agent.

## Step 3: Understand the Pipeline

The Image Agent:

1. **Enhances your prompt** using the solver model to add artistic details
2. **Selects a ComfyUI workflow** (e.g., `workflow_hunyuan_paint.json`)
3. **Queues the job** on ComfyUI at `{{ lovelace_ip }}:8188`
4. **Returns the image** in the chat

## Step 4: Iterate

Refine your image with follow-up messages:

> Make it more vibrant with autumn colors

The agent maintains context and adjusts the prompt.

## Step 5: Advanced Prompting

For more control, specify:

- **Style**: "in the style of Studio Ghibli"
- **Medium**: "oil painting", "digital art", "photograph"
- **Composition**: "close-up", "wide angle", "bird's eye view"
- **Lighting**: "golden hour", "dramatic lighting", "soft ambient"

## Example Gallery

| Prompt | Description |
|--------|-------------|
| "A cyberpunk city at night, neon lights, rain" | Sci-fi cityscape |
| "Portrait of a cat wearing a crown, oil painting" | Stylized pet portrait |
| "Minimalist logo design for a coffee shop" | Design work |

## Next Steps

- [User Guide: Art Studio](../user-guide/art-studio.md) — full Art Studio reference
- [Build a 3D Model](build-3d-model.md) — go from 2D to 3D


