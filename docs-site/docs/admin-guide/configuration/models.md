---
title: Models Configuration
---

# Models Configuration

Model selection, Ollama settings, and custom Modelfiles.

## Active Models

| Role | Model | Parameters | VRAM | Node |
|------|-------|------------|------|------|
| Solver | {{ solver_model }} | 9B | ~6 GB | Execution |
| Router | {{ router_model }} | 8B | ~5 GB | Execution |
| Safety Verifier | {{ verifier_model }} | 8B | ~5 GB | Execution |
| Vision | moondream:latest | 1.6B | ~2 GB | Execution |
| TTS | Qwen3-TTS | — | ~3 GB | Execution |

## Pulling Models

```bash
docker exec ollama ollama pull {{ solver_model }}
docker exec ollama ollama pull {{ router_model }}
docker exec ollama ollama pull {{ verifier_model }}
docker exec ollama ollama pull moondream:latest
```

## Ollama Configuration

### Memory Management

| Variable | Value | Description |
|----------|-------|-------------|
| `OLLAMA_MAX_LOADED_MODELS` | 3 | Max models in VRAM simultaneously |
| `OLLAMA_NUM_PARALLEL` | 2 | Max concurrent inference requests |
| `OLLAMA_KEEP_ALIVE` | 10m | Unload idle models after this time |
| `OLLAMA_FLASH_ATTENTION` | 1 | Enable Flash Attention for faster inference |

### VRAM Budget

With RTX 5060 Ti (16 GB VRAM):

```
Solver (6 GB) + Router (5 GB) + Safety (5 GB) = 16 GB → tight fit
```

Ollama will auto-unload the least-recently-used model when VRAM is full.

## Custom Modelfiles

Create specializations of base models:

### Example: Optimized Solver

```dockerfile
FROM {{ solver_model }}
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
PARAMETER repeat_penalty 1.1
SYSTEM """You are a precise coding assistant. Always:
- Use type hints in Python
- Include error handling
- Add brief inline comments for complex logic"""
```

```bash
docker exec ollama ollama create solver-optimized -f /models/Solver.Modelfile
```

### Example: Router with Structured Output

```dockerfile
FROM {{ router_model }}
PARAMETER temperature 0.3
PARAMETER num_ctx 4096
SYSTEM """You are an intent classifier. Respond ONLY with valid JSON:
{"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}"""
```

## Changing Models

1. Update `network.env`:

    ```bash
    SOLVER_MODEL=qwen3.5:14b
    ```

2. Pull the new model:

    ```bash
    docker exec ollama ollama pull qwen3.5:14b
    ```

3. Restart Agent Runtime:

    ```bash
    docker compose restart agent-runtime
    ```

## Model Performance

### Benchmark Reference

| Model | Tokens/sec (RTX 5060 Ti) | Context Window |
|-------|--------------------------|----------------|
| {{ solver_model }} | ~45 t/s | 32K |
| {{ router_model }} | ~55 t/s | 8K |
| {{ verifier_model }} | ~60 t/s | 8K |
| moondream:latest | ~80 t/s | 2K |

### A/B Testing

The ExpertiseTemplate system supports A/B testing between models:

```python
# In template registry
"CODE": {
    "model": "{{ solver_model }}",
    "ab_variant": {
        "model": "qwen3.5:14b",
        "traffic_pct": 10  # 10% of requests
    }
}
```

## Related

- [Admin: Scaling](../operations/scaling.md) — adding GPU capacity
- [Architecture: Agent System](../../architecture/agent-system.md) — how models are used
- [Procedures: Switch Models](../../procedures/switch-models.md) — model migration guide
