---
title: "FAQ: Troubleshooting"
---

# Troubleshooting FAQ

Quick answers to common issues. For detailed guides, see the [Troubleshooting](../troubleshooting/index.md) section.

## The chat doesn't respond

1. Check if the Agent Runtime is running: `docker ps | grep agent-runtime`
2. Check if Ollama is healthy: `curl http://{{ execution_node_ip }}:{{ ollama_port }}/api/tags`
3. Check logs: `docker logs agent-runtime --tail 50`

## Image generation fails

1. Verify ComfyUI is running: `curl http://{{ execution_node_ip }}:8188/system_stats`
2. Check GPU memory: `docker exec ollama nvidia-smi`
3. Ollama may need to unload models to free VRAM

## Voice doesn't work

1. Check microphone permissions in the browser
2. Verify Whisper: `curl http://{{ execution_node_ip }}:9000/health`
3. Verify Piper: `curl http://{{ execution_node_ip }}:5500/health`

## IoT commands don't work

1. Verify Home Assistant connection: check `HA_URL` and `HA_TOKEN` in `network.env`
2. Test the API directly: `curl -H "Authorization: Bearer $HA_TOKEN" http://<ha-ip>:8123/api/`

## "Model not found" errors

The requested model isn't pulled yet:

```bash
docker exec ollama ollama pull <model-name>
```

## Everything is slow

See [Performance Tuning](../procedures/performance-tuning.md). Quick checks:

- GPU VRAM usage: `nvidia-smi`
- Too many models loaded: reduce `OLLAMA_MAX_LOADED_MODELS`
- Network latency: `ping {{ execution_node_ip }}`

## How do I check if all services are running?

```bash
docker compose ps                # On each node
curl http://{{ gateway_node_ip }}/health   # Gateway health check
```

## Where are the logs?

- **Docker logs**: `docker logs <container-name> --tail 100`
- **Grafana/Loki**: `http://{{ gateway_node_ip }}:3001`
- **Langfuse traces**: `http://{{ control_node_ip }}:3000`
- **Local log files**: `logs/` directory
