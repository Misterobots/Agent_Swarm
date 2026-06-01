---
title: "Tool: Vision"
---

# Vision Tool

Image analysis using a Vision Language Model (VLM). Accepts images attached to chat messages and returns a detailed description or answers a question about them.

## Attachment Pipeline

Images sent via the chat paperclip button are routed through `church.py`'s attachment bridge before reaching the vision handler. The bridge promotes image attachments to `extracted_context` as base64 data-URIs. Multiple images accumulate — they do not overwrite each other.

The vision handler reads the first image data-URI from `extracted_context` and sends it to the VLM.

## Model Fallback Chain

The handler tries models in priority order, selecting the first one available on any Ollama host:

| Priority | Model | VRAM | Notes |
|---|---|---|---|
| 1 | `minicpm-v:latest` | ~4 GB | Recommended — strong at UI/design visual analysis |
| 2 | `llava:13b` | ~9 GB | General-purpose, detailed descriptions |
| 3 | `llava:7b` | ~5 GB | Good balance of quality and speed |
| 4 | `llava:latest` | varies | Any installed llava version |
| 5 | `moondream:latest` | ~2 GB | Compact, fast — limited context |
| 6 | `gemma4:31b` | ~20 GB | Multimodal if the pulled variant supports vision |

If none are available, the handler returns a clear install message:

```
No vision model is installed. Pull one first:
  ollama pull minicpm-v
```

## Installing a Vision Model

```bash
# Recommended (compact, strong at UI/design analysis)
ollama pull minicpm-v

# Larger, more detailed
ollama pull llava:13b
```

Run on **Lovelace** (192.168.2.101) — the primary GPU node. The model will be available to all agent_runtime instances via the GPU queue.

## Use Cases

- Describe image contents
- Answer questions about images
- Extract text from screenshots
- Identify objects, people, scenes
- **Design reference analysis** — attach screenshots of a UI to get a design language description for use in Design Studio prompts

## Video / Frame Analysis

Vision models analyse still images, not video directly. For video reference material:

1. **Extract frames** using ffmpeg inside the `open-webui-turing` container on Turing:
   ```bash
   docker cp your_video.mp4 open-webui-turing:/tmp/video.mp4
   docker exec open-webui-turing ffmpeg \
     -i /tmp/video.mp4 \
     -vf "fps=1/4,scale=896:504" \
     -frames:v 12 -q:v 3 \
     /tmp/frame_%02d.jpg
   docker cp open-webui-turing:/tmp/frame_01.jpg /tmp/frame_01.jpg
   # repeat for each frame
   ```
2. Attach the frames as images in chat
3. Ask the vision model to describe the design language, colour palette, or visual style

For true video understanding (motion, temporal context, scene transitions), use **Gemini 1.5 Flash** (cloud) or pull `qwen2-vl:7b` which understands frame sequences as temporal video.

## Allowed Intents

`VISION`
