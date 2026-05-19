---
title: Traefik Configuration
---

# Traefik Configuration

Traefik serves as the reverse proxy and API gateway on the Gateway node (Turing).

## Configuration File

Location: `turing_gateway/config/traefik/traefik.yml`

### Entry Points

```yaml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
```

### Dashboard

The Traefik dashboard is available at `http://{{ turing_ip }}:8080` for route inspection and debugging.

```yaml
api:
  dashboard: true
  insecure: true  # LAN-only access
```

### Docker Provider

Traefik auto-discovers services via Docker labels:

```yaml
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: ai_lab_net
```

## Routing via Labels

Services declare their routes using Docker labels in `docker-compose.yml`:

### Example: Agent Runtime

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.swarm.rule=PathPrefix(`/swarm`)"
  - "traefik.http.routers.swarm.entrypoints=web"
  - "traefik.http.services.swarm.loadbalancer.server.port={{ agent_runtime_port }}"
  - "traefik.http.middlewares.swarm-strip.stripprefix.prefixes=/swarm"
  - "traefik.http.routers.swarm.middlewares=swarm-strip"
```

### Example: Docs Site

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.docs.rule=PathPrefix(`/docs`)"
  - "traefik.http.routers.docs.entrypoints=web"
  - "traefik.http.services.docs.loadbalancer.server.port=80"
  - "traefik.http.middlewares.docs-strip.stripprefix.prefixes=/docs"
  - "traefik.http.routers.docs.middlewares=docs-strip"
```

## Current Routes

| Router | Rule | Service | Middleware |
|--------|------|---------|------------|
| swarm | `PathPrefix(/swarm)` | agent-runtime:{{ agent_runtime_port }} | strip `/swarm` |
| comfyui | `PathPrefix(/comfyui)` | comfyui:8188 | strip `/comfyui` |
| docs | `PathPrefix(/docs)` | docs-site:80 | strip `/docs` |
| hollerith | `PathPrefix(/hollerith)` | hollerith:3001 | — |
| jacquard | `PathPrefix(/jacquard)` | jacquard:9091 | — |

## Middleware

### StripPrefix

Removes the path prefix before forwarding to the backend:

```
Client: GET /swarm/v1/chat/completions
Backend: GET /v1/chat/completions
```

### Rate Limiting (Optional)

```yaml
labels:
  - "traefik.http.middlewares.rate-limit.ratelimit.average=100"
  - "traefik.http.middlewares.rate-limit.ratelimit.burst=200"
```

## TLS

For HTTPS with Let's Encrypt:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web
```

!!! note "LAN-Only"
    Currently running HTTP-only within the LAN. TLS is handled by Tailscale for remote access.

## Related

- [Admin: Networking](../deployment/networking.md) — network topology
- [Reference: Port Map](../port-map.md) — all ports
- [Troubleshooting: Network](../../troubleshooting/network.md) — routing issues


