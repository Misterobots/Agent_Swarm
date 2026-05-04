---
title: Scaling
---

# Scaling

Strategies for adding capacity to Memex.

## Vertical Scaling

### Add GPU VRAM

Upgrade the GPU on the Execution Node to load more models simultaneously:

| GPU | VRAM | Concurrent Models |
|-----|------|--------------------|
| RTX 3070 Ti | 8 GB | 12 |
| RTX 5060 Ti | 16 GB | 23 |
| RTX 4090 | 24 GB | 34 |
| A100 | 80 GB | 8+ |

After GPU upgrade:

```bash
# Increase Ollama limits
# In docker-compose.yml:
OLLAMA_MAX_LOADED_MODELS=4
OLLAMA_NUM_PARALLEL=4
```

### Add RAM

The Gateway node benefits from more RAM for jacquard TSDB and knuth retention.

## Horizontal Scaling

### Add a Second GPU Node

1. Deploy a new node following [Execution Plane](../deployment/execution-plane.md)
2. Register with SPIRE:
   ```bash
   # On Control Node
   docker compose exec spire-server \
       /opt/spire/bin/spire-server token generate \
       -spiffeID spiffe://home-ai-lab/execution-node-2
   ```
3. Add Traefik load balancing in Gateway:
   ```yaml
   # Weighted round-robin across execution nodes
   services:
     agent-runtime:
       loadBalancer:
         servers:
           - url: "http://{{ lovelace_ip }}:{{ agent_runtime_port }}"
           - url: "http://192.168.2.105:{{ agent_runtime_port }}"
   ```

### Ollama Load Balancing

For inference-heavy workloads, add a secondary Ollama on the Gateway node (already configured as `ollama-secondary` on port 11435):

```python
# In config, the router can fallback to secondary Ollama
OLLAMA_HOSTS = [
    "http://{{ lovelace_ip }}:{{ ollama_port }}",  # primary (RTX 5060 Ti)
    "http://{{ turing_ip }}:11435",                 # secondary (RTX 3070 Ti)
]
```

### Queue-Based Scaling

The Dispatcher already supports concurrent worker limits per queue:

| Queue | Current Workers | Max Practical |
|-------|----------------|---------------|
| `default` (chat) | 5 | 10 |
| `image` | 2 | 4 (VRAM limited) |
| `3d` | 1 | 2 (VRAM limited) |
| `action_figure` | 1 | 1 |

Increase workers in `agents/dispatcher.py` configuration.

## Storage Scaling

### MinIO for Artifacts

If local disk fills up, offload artifacts to MinIO (Control Node):

```
http://{{ hopper_ip }}:9000
```

### jacquard Retention

Adjust retention in `turing_gateway/docker-compose.yml`:

```yaml
command:
  - '--storage.tsdb.retention.time=90d'
  - '--storage.tsdb.retention.size=20GB'
```

## Related

- [Architecture: Topology](../../architecture/topology.md)  current node layout
- [Admin: Prerequisites](../deployment/prerequisites.md)  hardware recommendations


