---
title: SPIRE Configuration
---

# SPIRE Configuration

SPIFFE/SPIRE provides workload identity for all Agent Swarm services.

## Server Configuration

Location: `control_plane/config/spire/server.conf`

### Key Settings

```hcl
server {
    bind_address = "0.0.0.0"
    bind_port = "8081"
    trust_domain = "home-ai-lab"
    data_dir = "/opt/spire/data/server"
    log_level = "INFO"

    ca_key_type = "ec-p256"
    default_x509_svid_ttl = "8h"
    ca_ttl = "168h"
}

plugins {
    DataStore "sql" {
        plugin_data {
            database_type = "sqlite3"
            connection_string = "/opt/spire/data/server/datastore.sqlite3"
        }
    }

    KeyManager "disk" {
        plugin_data {
            keys_path = "/opt/spire/data/server/keys.json"
        }
    }

    NodeAttestor "join_token" {
        plugin_data {}
    }
}
```

### Certificate Lifetimes

| Parameter | Value | Description |
|-----------|-------|-------------|
| `default_x509_svid_ttl` | 8h | Workload certificate lifetime |
| `ca_ttl` | 168h (7d) | CA certificate lifetime |
| `ca_key_type` | ec-p256 | Elliptic curve key type |

## Agent Configuration

Location: `execution_plane/config/spire/agent.conf` and `r730_gateway/config/spire/agent.conf`

```hcl
agent {
    data_dir = "/opt/spire/data/agent"
    log_level = "INFO"
    server_address = "{{ control_node_ip }}"
    server_port = "8081"
    trust_domain = "home-ai-lab"
    socket_path = "/var/run/spire/agent.sock"
}

plugins {
    NodeAttestor "join_token" {
        plugin_data {}
    }

    KeyManager "disk" {
        plugin_data {
            directory = "/opt/spire/data/agent"
        }
    }

    WorkloadAttestor "unix" {
        plugin_data {}
    }
}
```

## Workload Registration

Register workloads (services that need identities):

```bash
docker compose exec spire-server \
    /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://home-ai-lab/agent-runtime \
    -parentID spiffe://home-ai-lab/execution-node \
    -selector unix:uid:1000
```

### Current Registrations

| SPIFFE ID | Parent | Selector |
|-----------|--------|----------|
| `spiffe://home-ai-lab/agent-runtime` | execution-node | `unix:uid:1000` |
| `spiffe://home-ai-lab/traefik` | r730-gateway | `unix:uid:0` |

## Join Token Generation

```bash
# Generate token for Execution Node
docker compose exec spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://home-ai-lab/execution-node \
    -ttl 3600

# Generate token for Gateway Node
docker compose exec spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://home-ai-lab/r730-gateway \
    -ttl 3600
```

!!! warning "Token Expiry"
    Join tokens are single-use and expire after TTL. Generate a fresh token immediately before starting each agent.

## Health Checks

```bash
# Server health
docker compose exec spire-server /opt/spire/bin/spire-server healthcheck

# Agent health
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck

# List registered entries
docker compose exec spire-server /opt/spire/bin/spire-server entry show
```

## Related

- [Architecture: Security Model](../../architecture/security-model.md) — security design
- [Procedures: Rotate SPIRE Keys](../../procedures/rotate-spire-keys.md) — key rotation
- [Troubleshooting: SPIRE](../../troubleshooting/spire.md) — common issues
