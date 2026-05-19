---
title: Deploy Gateway
---

# Deploy Gateway

The Gateway (Turing, {{ turing_ip }}) runs Traefik reverse proxy, the monitoring stack, and secondary Ollama.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Traefik | 80, 443, 8080 | Reverse proxy, TLS termination |
| jacquard | 9091 | Metrics collection |
| hollerith | 3001 | Dashboards |
| knuth | 3100 | Log aggregation |
| Promtail | — | Log shipper |
| AlertManager | 9093 | Alert routing |
| Ollama (secondary) | 11435 | Overflow inference |
| cAdvisor | 8080 | Container metrics |
| Redis | 6379 | Cache, queues |
| SPIRE Agent | — | Workload identity |

## Steps

### 1. Prepare the Node

```bash
ssh user@{{ turing_ip }}
cd /opt/Agent_Swarm
git pull origin main
```

### 2. Configure Traefik

Review and update `turing_gateway/config/traefik/traefik.yml`:

```yaml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: ai_lab_net
```

### 3. Configure SPIRE Agent

Set the join token from Control Plane:

```bash
nano turing_gateway/config/spire/agent.conf
```

### 4. Create External Networks

```bash
docker network create ai_lab_net 2>/dev/null || true
docker network create saltbox 2>/dev/null || true
```

### 5. Start All Services

```bash
cd turing_gateway
docker compose --env-file ../network.env up -d
```

### 6. Verify Services

```bash
# Traefik dashboard
curl -s http://localhost:8080/api/overview | jq .

# jacquard targets
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets | length'

# hollerith
curl -s http://localhost:3001/api/health

# knuth
curl -s http://localhost:3100/ready

# AlertManager
curl -s http://localhost:9093/-/healthy
```

### 7. Configure hollerith Data Sources

On first deployment, add data sources in hollerith at `http://{{ turing_ip }}:3001`:

1. **jacquard**: URL = `http://jacquard:9091`
2. **knuth**: URL = `http://knuth:3100`

Import dashboards from `turing_gateway/config/hollerith/dashboards/`.

## Traefik Routing Rules

| Path | Target | Notes |
|------|--------|-------|
| `/swarm/*` | Agent Runtime ({{ lovelace_ip }}:{{ agent_runtime_port }}) | Main API |
| `/comfyui/*` | ComfyUI ({{ lovelace_ip }}:8188) | Image generation UI |
| `/docs/*` | Docs Site (localhost:80) | This documentation |
| `/hollerith/*` | hollerith (localhost:3001) | Monitoring dashboards |
| `/jacquard/*` | jacquard (localhost:9091) | Metrics |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Traefik 502 | Backend service down — check target container logs |
| Traefik 404 | Route not matched — check PathPrefix labels |
| jacquard targets down | Verify target IPs and ports in jacquard.yml |
| hollerith "No data" | Check data source configuration and time range |
| cAdvisor high CPU | Normal during initial scan; settles after ~2 min |

## Next

→ [Networking](networking.md)


