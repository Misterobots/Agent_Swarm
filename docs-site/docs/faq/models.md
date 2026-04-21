---
title: "FAQ: Models"
---

# Models FAQ

## Which models are supported?

Any model available through Ollama. Popular choices:

- **Qwen** series (2.5, 3.5) — strong general performance
- **Llama** series (3.1, 3.3, Guard) — Meta's open models
- **Gemma** series — Google's efficient models
- **Mistral/Mixtral** — fast inference
- **DeepSeek** — coding-focused
- **Nemotron** — NVIDIA's optimized models

## How do I add a new model?

```bash
docker exec ollama ollama pull <model-name>
```

See [Add a New Model](../procedures/add-model.md).

## Can I use different models for different tasks?

Yes. The system uses three model roles:

- **Solver** — handles the main response generation
- **Router** — classifies user intent  
- **Verifier** — checks response quality and safety

Each can be a different model. Configure in `network.env`.

## How much VRAM do I need?

| Model Size | VRAM (q4_K_M) | VRAM (FP16) |
|-----------|---------------|-------------|
| 3B | ~2 GB | ~6 GB |
| 7–9B | ~5 GB | ~18 GB |
| 14B | ~9 GB | ~28 GB |
| 32B | ~20 GB | ~64 GB |

Agent Swarm loads up to 3 models by default. Plan VRAM accordingly.

## Can I use API-based models (OpenAI, Anthropic)?

Not out of the box. The system is designed for local Ollama models. However, because it uses the OpenAI-compatible API format, you could in theory point the solver at an external endpoint by changing the API URL configuration.

## How do I check which models are loaded?

```bash
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags | python -m json.tool
```

## Why is inference slow?

See [Performance Tuning](../procedures/performance-tuning.md). Common causes:

- VRAM pressure (too many models loaded)
- Large context windows
- Flash Attention disabled
- Thermal throttling


