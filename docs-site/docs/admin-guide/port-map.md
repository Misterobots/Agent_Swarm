---
title: Port Map
---

# Port Map

Complete port registry across all Agent Swarm nodes.

## Execution Node â€” {{ execution_node_ip }}

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| {{ agent_runtime_port }} | Agent Runtime (FastAPI) | HTTP | LAN |
| {{ ollama_port }} | Ollama API | HTTP | LAN |
| 8188 | ComfyUI | HTTP | LAN |
| 5050 | Voice Engine (TTS) | HTTP | LAN |
| 5060 | BMO Voice Assistant | HTTP | LAN |
| 3300 | OpenHands | HTTP | LAN |
| 8081 | cAdvisor | HTTP | Internal |

## Control Node â€” {{ control_node_ip }}

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| 8081 | SPIRE Server | gRPC | LAN |
| 5432 | PostgreSQL | TCP | LAN |
| 3000 | Langfuse | HTTP | LAN |
| 8123 | ClickHouse (HTTP) | HTTP | Internal |
| 9000 | ClickHouse (native) | TCP | Internal |
| 8200 | MemPalace | HTTP | LAN |
| 9000 | MinIO API | HTTP | LAN |
| 9001 | MinIO Console | HTTP | LAN |
| 6379 | Redis | TCP | LAN |

## Gateway Node â€” {{ gateway_node_ip }}

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| 80 | Traefik HTTP | HTTP | LAN + Tailscale |
| 443 | Traefik HTTPS | HTTPS | LAN + Tailscale |
| 8080 | Traefik Dashboard | HTTP | LAN |
| 9091 | Prometheus | HTTP | LAN |
| 3001 | Grafana | HTTP | LAN |
| 3100 | Loki | HTTP | Internal |
| 9093 | AlertManager | HTTP | LAN |
| 11435 | Ollama (secondary) | HTTP | LAN |
| 6379 | Redis | TCP | Internal |
| 8080 | cAdvisor | HTTP | Internal |

## Home Assistant â€” 192.168.2.100

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| 8123 | Home Assistant | HTTP | LAN |

## Access Legend

| Level | Description |
|-------|-------------|
| **LAN** | Accessible from any device on 192.168.2.0/24 |
| **LAN + Tailscale** | Accessible from LAN and via Tailscale VPN |
| **Internal** | Only accessible within Docker network on the same node |

---

## Source References

<details markdown>
<summary><strong>Source of Truth â€” Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `network.env` | Configuration | All IP addresses and node roles |
| `r730_gateway/docker-compose.yml` | Infrastructure | Gateway Node services and port mappings |
| `execution_plane/docker-compose.yml` | Infrastructure | Execution Node services |
| `control_plane/docker-compose.yml` | Infrastructure | Control Node services |
| `config/prometheus/prometheus.yml` | Configuration | Scrape targets and intervals |
| `config/grafana/provisioning/dashboards/` | Configuration | Dashboard JSON definitions |
| `agents/main.py` | Implementation | API endpoint definitions |
| `agents/metrics.py` | Implementation | Custom Prometheus metrics |

</details>

---

## Maintenance & Update Guide

### When IPs or Ports Change

1. Update `network.env` with new IP addresses.
2. Update the Network Topology table in Section 1.
3. Update `docker-compose.yml` files if port mappings change.
4. Update Prometheus scrape targets in `config/prometheus/prometheus.yml`.

### When Services Are Added

1. Add the service to the appropriate node's Service Inventory table.
2. Add its port to the UI URLs table if it has a web interface.
3. Add a Prometheus scrape target if it exposes metrics.
4. Add Loki log labels if it produces structured logs.

### Keeping Environment Variables Current

- After adding new env vars, add them to the Environment Variables table in Section 10.
- Never commit `.env` files â€” document the variable names and purposes only.

---

---

## Functionality Testing

### Manual Verification

1. **Network connectivity**: Ping each node IP from the Gateway Node.
2. **Service health**: `curl` each API endpoint listed in Section 3 ? verify 200 responses.
3. **Prometheus targets**: Check `http://<gateway-node-ip>:9091/targets` ? all should show UP.
4. **Grafana dashboards**: Open each dashboard listed in Section 6 ? verify data is flowing.
5. **PostgreSQL schema**: Connect to the swarm database ? verify all tables listed in Section 7 exist.

---

*See also: Design Framework · Security · [Back to Index](../index.md)*
