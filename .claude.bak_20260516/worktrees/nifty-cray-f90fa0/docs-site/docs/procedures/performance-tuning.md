---
title: "Procedure: Performance Tuning"
---

# Performance Tuning

Optimize inference speed and system throughput.

## Ollama Optimization

### Flash Attention

Ensure Flash Attention is enabled:

```bash
OLLAMA_FLASH_ATTENTION=1
```

### Concurrent Requests

Balance parallelism with VRAM:

| Setting | Low VRAM (8 GB) | Medium (16 GB) | High (24 GB+) |
|---------|-----------------|----------------|----------------|
| `OLLAMA_NUM_PARALLEL` | 1 | 2 | 4 |
| `OLLAMA_MAX_LOADED_MODELS` | 1 | 3 | 5 |

### Context Window

Smaller context windows reduce VRAM and improve speed:

```bash
# In Modelfile
PARAMETER num_ctx 4096   # instead of 32768
```

## Agent Runtime

### Stream Timeout

Increase for large responses:

```python
STREAM_TIMEOUT = 120.0  # seconds
```

### MarsRL Tuning

For faster responses at the cost of quality verification:

| Setting | Faster | Safer |
|---------|--------|-------|
| `max_iter` | 1 | 2 |
| `pass_threshold` | 0.50 | 0.70 |

## System Level

### Docker Resource Limits

```yaml
services:
  agent-runtime:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: "4.0"
```

### Network Latency

- Verify LAN latency: `ping {{ lovelace_ip }}` should be < 1ms
- Use wired connections for GPU nodes (not WiFi)

## Benchmarking

```bash
# Simple latency test
time curl -s -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages": [{"role": "user", "content": "Hello"}], "stream": false}'
```

Target: < 5 seconds for simple chat responses.


