---
title: Updates
---

# Updates

How to update models, container images, and Memex code.

## Model Updates

### Pull New Model Version

```bash
# On Execution Node
docker exec ollama ollama pull {{ solver_model }}
docker exec ollama ollama pull {{ router_model }}
```

### Switch Models

Update `network.env` with new model names:

```
SOLVER_MODEL=qwen3.5:14b
ROUTER_MODEL=nemotron-orchestrator:12b
```

Then restart the Agent Runtime:

```bash
docker compose restart agent-runtime
```

### Custom Modelfiles

For fine-tuned models, create a Modelfile:

```dockerfile
FROM qwen3.5:9b
PARAMETER temperature 0.7
PARAMETER top_p 0.9
SYSTEM "You are a helpful assistant."
```

```bash
docker exec ollama ollama create custom-solver -f /models/Modelfile
```

## Container Image Updates

### Update Agent Runtime

```bash
cd execution_plane
docker compose pull agent-runtime
docker compose up -d agent-runtime
```

### Update All Services on a Node

```bash
docker compose pull
docker compose up -d
```

!!! tip "Rolling Updates"
    Update one node at a time. Verify health after each node update before proceeding to the next.

## Code Updates

```bash
git pull origin main
docker compose build --no-cache agent-runtime
docker compose up -d
```

## Rollback

### Container Rollback

```bash
# List image history
{% raw %}
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}" | head -20
{% endraw %}

# Revert to previous image
docker compose up -d --no-deps agent-runtime
```

### Code Rollback

```bash
git log --oneline -10
git checkout <previous-commit>
docker compose build agent-runtime
docker compose up -d
```

## Update Checklist

- [ ] Notify users of planned maintenance
- [ ] Back up databases ([Backup & Restore](backup-restore.md))
- [ ] Pull new images/models
- [ ] Update one node at a time
- [ ] Verify health after each update
- [ ] Check Langfuse traces for errors
- [ ] Monitor hollerith for anomalies


