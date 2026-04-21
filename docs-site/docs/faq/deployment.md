---
title: "FAQ: Deployment"
---

# Deployment FAQ

## Can I run everything on a single machine?

Yes. Merge all Docker Compose files and run all services on one machine. You'll need at least 32 GB RAM and an NVIDIA GPU.

## Do I need Docker?

Yes. All services run as Docker containers managed by Docker Compose.

## What Linux distribution should I use?

Ubuntu 22.04+ or Debian 12+ recommended. Any distribution with Docker Engine and NVIDIA Container Toolkit support will work.

## Can I run it on Windows or macOS?

The Execution Node requires NVIDIA GPU passthrough, which works best on Linux. The Control and Gateway nodes can theoretically run on any Docker-capable OS, but Linux is recommended for all nodes.

## How do I update?

```bash
git pull origin main
docker compose build
docker compose up -d
```

See [Updates](../admin-guide/operations/updates.md).

## What ports need to be open?

Only between your internal nodes. See [Port Map](../admin-guide/port-map.md) for the full list. No ports need to be exposed to the internet.

## Can I use Kubernetes instead of Docker Compose?

Not currently. The deployment is designed around Docker Compose. A Kubernetes migration is possible but not officially supported.

## How do I back up everything?

See [Backup & Restore](../admin-guide/operations/backup-restore.md). Key items:

- PostgreSQL database dump
- `workspace/` directory
- `network.env` configuration
- SPIRE configuration files

## What happens if a node goes down?

- **Control Node down**: Langfuse tracing and PostgreSQL are unavailable, but agents can still respond (with degraded observability)
- **Execution Node down**: All inference stops — this is the critical node
- **Gateway Node down**: External access is lost, but services still run internally


