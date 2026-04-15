---
title: "Procedure: GPU Troubleshooting"
---

# GPU Troubleshooting

Diagnose and resolve GPU-related issues.

## Quick Diagnostic

```bash
# Check GPU visibility
nvidia-smi

# Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Check Ollama GPU usage
docker exec ollama nvidia-smi
```

## Common Issues

### GPU Not Visible in Container

**Symptom**: `nvidia-smi` works on host but not in container.

**Fix**:

```bash
# Install nvidia-container-toolkit
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

### OOM (Out of Memory)

**Symptom**: Model inference crashes with CUDA OOM error.

**Fix**:

1. Reduce loaded models:
   ```bash
   # In docker-compose.yml
   OLLAMA_MAX_LOADED_MODELS=2
   ```

2. Use smaller quantization:
   ```bash
   docker exec ollama ollama pull {{ solver_model }}:q4_K_M
   ```

3. Restart Ollama to clear VRAM:
   ```bash
   docker compose restart ollama
   ```

### Slow Inference

**Symptom**: Token generation much slower than expected.

**Check**:

1. Verify Flash Attention: `OLLAMA_FLASH_ATTENTION=1`
2. Check VRAM pressure: `nvidia-smi` — VRAM near 100%?
3. Check thermal throttling: `nvidia-smi -q -d TEMPERATURE`
4. Ensure no background GPU tasks: close other GPU apps

### ComfyUI VRAM Conflict

**Symptom**: Image generation fails while Ollama models are loaded.

**Fix**: ComfyUI and Ollama share the GPU. When ComfyUI needs VRAM:

1. Ollama will auto-unload idle models
2. Reduce `OLLAMA_KEEP_ALIVE=5m` for faster unloading
3. Or use queue limits in the Dispatcher to prevent concurrent access
