---
title: "Procedure: Switch Models"
---

# Switch Models

Change the solver, router, or verifier model used by Agent Swarm.

## Steps

### 1. Pull the New Model

```bash
docker exec ollama ollama pull <new-model>
```

### 2. Update Environment

Edit `network.env`:

```bash
# Change from:
SOLVER_MODEL={{ solver_model }}
# To:
SOLVER_MODEL=qwen3.5:14b
```

### 3. Restart Agent Runtime

```bash
cd execution_plane
docker compose restart agent-runtime
```

### 4. Verify

```bash
curl -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What model are you using?"}],
        "stream": false
    }'
```

Check the response metadata for the new model name.

### 5. Monitor

Watch Langfuse traces and hollerith dashboards for:

- Response quality changes
- Latency differences
- Error rate changes

## Rollback

If the new model performs poorly:

1. Revert `network.env` to the previous model
2. Restart Agent Runtime: `docker compose restart agent-runtime`
3. The previous model should still be cached in Ollama


