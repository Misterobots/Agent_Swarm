---
title: Admin Guide
---

# Admin Guide

Everything needed to deploy, configure, operate, and maintain Agent Swarm.

## Sections

### Deployment

Step-by-step guides for deploying each node from scratch.

| Guide | Description |
|-------|-------------|
| [Prerequisites](deployment/prerequisites.md) | Hardware, OS, Docker, GPU drivers |
| [Control Plane](deployment/control-plane.md) | SPIRE, PostgreSQL, Langfuse, MemPalace |
| [Execution Plane](deployment/execution-plane.md) | Ollama, Agent Runtime, ComfyUI, Voice |
| [Gateway](deployment/gateway.md) | Traefik, jacquard, hollerith, knuth |
| [Networking](deployment/networking.md) | LAN layout, DNS, Tailscale, firewall |
| [Post-Deployment](deployment/post-deploy.md) | Verification, smoke tests, first request |

### Operations

Day-to-day operational runbooks.

| Guide | Description |
|-------|-------------|
| [Monitoring](operations/monitoring.md) | Dashboards, alerts, health checks |
| [Backup & Restore](operations/backup-restore.md) | Database dumps, volume backups, recovery |
| [Updates](operations/updates.md) | Model pulling, image updates, rollbacks |
| [Scaling](operations/scaling.md) | Adding GPUs, nodes, models |
| [Secrets Management](operations/secrets.md) | Credential rotation, SPIRE tokens |

### Configuration

Reference for all configuration files and environment variables.

| Guide | Description |
|-------|-------------|
| [Environment Variables](configuration/environment.md) | `network.env` reference |
| [Docker Compose](configuration/docker-compose.md) | Compose files per node |
| [Traefik](configuration/traefik.md) | Routing, TLS, middleware |
| [SPIRE](configuration/spire.md) | Server and agent configuration |
| [Models](configuration/models.md) | Model selection, Modelfile, parameters |

### Reference

| Guide | Description |
|-------|-------------|
| [Port Map](port-map.md) | All ports across all nodes |


