---
title: "Troubleshooting: ComfyUI"
---

# ComfyUI Troubleshooting

## Workflow Execution Fails

**Symptom**: Image generation returns an error.

**Diagnose**:

```bash
# Check ComfyUI health
curl http://{{ lovelace_ip }}:8188/system_stats

# Check logs
docker logs comfyui --tail 50
```

**Fix**:

- Verify the workflow JSON is valid
- Check that all required custom nodes are installed
- Restart ComfyUI: `docker compose restart comfyui`

---

## VRAM Conflict with Ollama

**Symptom**: ComfyUI fails with OOM when Ollama models are loaded.

**Fix**:

1. Set `OLLAMA_KEEP_ALIVE=5m` for faster model unloading
2. Wait for Ollama models to unload before generating images
3. Reduce `OLLAMA_MAX_LOADED_MODELS=1` to free VRAM faster

---

## Missing Custom Nodes

**Symptom**: Workflow references nodes that don't exist.

**Diagnose**:

Check the ComfyUI log for "Node type not found" errors.

**Fix**:

```bash
# Install missing nodes
docker exec comfyui pip install <package>
# Or clone into custom_nodes/
docker exec comfyui git clone <repo> /comfyui/custom_nodes/<name>
docker compose restart comfyui
```

---

## Slow Image Generation

**Symptom**: Images take much longer than expected.

**Check**:

1. GPU utilization during generation: `nvidia-smi`
2. Image resolution — larger = slower
3. Number of sampling steps — more = slower
4. Is Ollama competing for VRAM?

---

## ComfyUI Web Interface Not Loading

**Symptom**: `http://{{ lovelace_ip }}:8188` doesn't respond.

**Fix**:

```bash
docker compose ps comfyui  # Check status
docker compose restart comfyui
docker logs comfyui --tail 20
```


