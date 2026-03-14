# SPIRE Agent Troubleshooting Guide

This document covers common issues with the SPIRE Agent in the Home AI Lab execution plane and how to resolve them.

## Architecture Overview

```
┌─────────────────────────┐     ┌─────────────────────────────────┐
│  control_plane (VPS)    │     │  execution_plane (Local)        │
│  ┌───────────────────┐  │     │  ┌─────────────────────────────┐│
│  │   spire-server    │◄─┼─────┼──│       spire-agent           ││
│  │  (port 8081)      │  │     │  │ (host.docker.internal:8081) ││
│  └───────────────────┘  │     │  └─────────────────────────────┘│
└─────────────────────────┘     │              │                  │
                                │              ▼                  │
                                │  ┌─────────────────────────────┐│
                                │  │     agent-runtime           ││
                                │  │   (SPIFFE client)           ││
                                │  └─────────────────────────────┘│
                                └─────────────────────────────────┘
```

## Common Issues

### 1. Agent Unhealthy: Unknown Authority

**Symptom:**

```
Agent is unhealthy: unable to determine health
```

Logs show:

```
level=error msg="Failed to fetch X.509 bundle" error="...unknown authority"
```

**Root Cause:** Stale trust bundle data from a previous bootstrap attempt. The agent has cached certificate information that no longer matches the server.

**Solution:**

```powershell
# 1. Stop and remove the agent
docker compose stop spire-agent
docker rm -f spire-agent

# 2. Delete stale data volume
docker volume rm execution_plane_spire_agent_data

# 3. Generate fresh join token from server
docker exec spire-server /opt/spire/bin/spire-server token generate \
  -spiffeID spiffe://home-ai-lab/agent/spire-agent
# Output: Token: <NEW_TOKEN>

# 4. Update docker-compose.yml with new token
# Edit line: command: ["-config", "...", "-joinToken", "<NEW_TOKEN>"]

# 5. Recreate agent with fresh volume
docker compose up -d spire-agent

# 6. Verify health
docker exec spire-agent /opt/spire/bin/spire-agent healthcheck \
  -socketPath /var/run/spire/agent.sock
# Expected: "Agent is healthy."
```

### 2. Agent Cannot Connect to Server

**Symptom:**

```
level=error msg="...connection refused" or "...unreachable"
```

**Possible Causes:**

1. SPIRE server not running
2. Port 8081 not exposed
3. Network misconfiguration

**Diagnostics:**

```powershell
# Check server is running
docker exec spire-server /opt/spire/bin/spire-server healthcheck
# Expected: "Server is healthy."

# Check port is listening on host
netstat -an | findstr 8081
# Expected: TCP 0.0.0.0:8081 LISTENING

# Check container network
docker inspect spire-agent --format "{{json .NetworkSettings.Networks}}"
```

### 3. Expired Join Token

**Symptom:** Agent starts but never becomes healthy, logs show attestation failures.

**Solution:** Join tokens are single-use and expire. Regenerate a fresh token and recreate the agent with a clean data volume (see Solution in Issue #1).

## Configuration Files

### Agent Config (`execution_plane/config/spire/agent.conf`)

```hcl
agent {
    data_dir = "/run/spire/agent"
    log_level = "DEBUG"
    server_address = "host.docker.internal"
    server_port = "8081"
    trust_domain = "home-ai-lab"
    socket_path = "/var/run/spire/agent.sock"
    insecure_bootstrap = true
}

plugins {
    NodeAttestor "join_token" { plugin_data {} }
    WorkloadAttestor "docker" {
        plugin_data {
            use_new_container_locator = true
            docker_socket_path = "unix:///var/run/docker.sock"
        }
    }
    KeyManager "memory" { plugin_data {} }
}
```

### Key Environment Variable

```yaml
# In docker-compose.yml for workloads (e.g., agent-runtime)
environment:
  - SPIFFE_ENDPOINT_SOCKET=unix:///var/run/spire/agent.sock
volumes:
  - spire_socket:/var/run/spire:ro
```

## Verification Commands

```powershell
# Agent health
docker exec spire-agent /opt/spire/bin/spire-agent healthcheck \
  -socketPath /var/run/spire/agent.sock

# Server health
docker exec spire-server /opt/spire/bin/spire-server healthcheck

# List registered workloads
docker exec spire-server /opt/spire/bin/spire-server entry show

# View agent logs
docker logs spire-agent --tail 50

# Test workload identity from agent-runtime
docker exec agent_runtime python -c "
from spiffe import SpiffeClient
client = SpiffeClient()
print(client.fetch_svid().spiffe_id)
"
```

## Quick Recovery Script

Save as `scripts/reset-spire-agent.ps1`:

```powershell
# Reset SPIRE Agent with fresh token
Write-Host "Stopping agent..."
docker compose -f execution_plane/docker-compose.yml stop spire-agent
docker rm -f spire-agent 2>$null

Write-Host "Clearing stale data..."
docker volume rm execution_plane_spire_agent_data 2>$null

Write-Host "Generating fresh token..."
$token = docker exec spire-server /opt/spire/bin/spire-server token generate `
  -spiffeID spiffe://home-ai-lab/agent/spire-agent | Select-String "Token:" | ForEach-Object { $_.ToString().Split(" ")[1] }

Write-Host "New token: $token"
Write-Host "Update docker-compose.yml with this token, then run:"
Write-Host "  docker compose -f execution_plane/docker-compose.yml up -d spire-agent"
```

---

_Last Updated: 2026-02-08_
