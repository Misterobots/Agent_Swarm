---
title: "Troubleshooting: Ollama"
---

# Ollama Troubleshooting

## Model Fails to Load

**Symptom**: Error like `model not found` or `failed to load model`.

**Diagnose**:

```bash
# List available models
docker exec ollama ollama list

# Check Ollama logs
docker logs ollama --tail 50
```

**Fix**:

- Pull the model: `docker exec ollama ollama pull <model>`
- Check disk space: `docker exec ollama df -h /root/.ollama`

---

## Out of Memory (OOM)

**Symptom**: `CUDA out of memory` or model loading stalls.

**Diagnose**:

```bash
docker exec ollama nvidia-smi
```

**Fix**:

1. Reduce loaded models: `OLLAMA_MAX_LOADED_MODELS=2`
2. Use smaller quantizations (q4_K_M instead of q8_0)
3. Reduce context window: `OLLAMA_NUM_CTX=4096`
4. Restart Ollama: `docker compose restart ollama`

---

## Slow Inference

**Symptom**: Tokens per second much lower than expected.

**Diagnose**:

```bash
# Check GPU utilization
docker exec ollama nvidia-smi -l 1

# Check if Flash Attention is enabled
docker inspect ollama | grep FLASH
```

**Fix**:

1. Enable Flash Attention: `OLLAMA_FLASH_ATTENTION=1`
2. Reduce `OLLAMA_NUM_PARALLEL` if VRAM is constrained
3. Check for thermal throttling: `nvidia-smi -q -d TEMPERATURE`
4. Ensure no other GPU processes are running

---

## Ollama Won't Start

**Symptom**: Container exits immediately.

**Diagnose**:

```bash
docker logs ollama
```

**Fix**:

- Check NVIDIA Container Toolkit: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
- Verify GPU runtime: ensure `runtime: nvidia` is in docker-compose
- Check port conflicts: ensure port {{ ollama_port }} is free

---

## Model Corruption

**Symptom**: Model loads but produces garbage output.

**Fix**:

```bash
docker exec ollama ollama rm <model>
docker exec ollama ollama pull <model>
```
