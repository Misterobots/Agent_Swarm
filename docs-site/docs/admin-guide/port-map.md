---
title: Port Map
---

# Port Map

Complete port registry across all Agent Swarm nodes.

## Execution Node — {{ execution_node_ip }}

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| {{ agent_runtime_port }} | Agent Runtime (FastAPI) | HTTP | LAN |
| {{ ollama_port }} | Ollama API | HTTP | LAN |
| 8188 | ComfyUI | HTTP | LAN |
| 5050 | Voice Engine (TTS) | HTTP | LAN |
| 5060 | BMO Voice Assistant | HTTP | LAN |
| 3300 | OpenHands | HTTP | LAN |
| 8081 | cAdvisor | HTTP | Internal |

## Control Node — {{ control_node_ip }}

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

## Gateway Node — {{ gateway_node_ip }}

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

## Home Assistant — 192.168.2.100

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| 8123 | Home Assistant | HTTP | LAN |

## Access Legend

| Level | Description |
|-------|-------------|
| **LAN** | Accessible from any device on 192.168.2.0/24 |
| **LAN + Tailscale** | Accessible from LAN and via Tailscale VPN |
| **Internal** | Only accessible within Docker network on the same node |
