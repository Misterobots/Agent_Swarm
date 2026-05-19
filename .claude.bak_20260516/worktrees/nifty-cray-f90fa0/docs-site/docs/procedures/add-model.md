---
title: "Procedure: Add a New Model"
---

# Add a New Model

Pull a new model from the Ollama registry and make it available.

## Steps

### 1. Check Available VRAM

```bash
docker exec ollama nvidia-smi
```

Verify there's enough VRAM for the new model.

### 2. Pull the Model

```bash
docker exec ollama ollama pull <model-name>:<tag>
```

Example:

```bash
docker exec ollama ollama pull gemma3:12b
```

### 3. Test the Model

```bash
curl -X POST http://{{ lovelace_ip }}:{{ ollama_port }}/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gemma3:12b",
        "messages": [{"role": "user", "content": "Hello, how are you?"}]
    }'
```

### 4. (Optional) Create a Modelfile

For custom system prompts or parameters:

```bash
cat > /tmp/Modelfile << 'EOF'
FROM gemma3:12b
PARAMETER temperature 0.7
SYSTEM "You are a helpful assistant."
EOF

docker cp /tmp/Modelfile ollama:/tmp/Modelfile
docker exec ollama ollama create gemma3-custom -f /tmp/Modelfile
```

### 5. Verify

```bash
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags | python -m json.tool
```

The model should appear in the list.

## Notes

- Model downloads can be large (2–20 GB). Ensure sufficient disk space.
- The Gateway's secondary Ollama (port 11435) can also host models.


