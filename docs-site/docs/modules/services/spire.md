---
title: "Service: SPIRE"
---

# SPIRE

Workload identity service (SPIFFE Runtime Environment).

## Deployment

| Component | Node | Port |
|-----------|------|------|
| SPIRE Server | Control ({{ control_node_ip }}) | 8081 |
| SPIRE Agent | Execution ({{ execution_node_ip }}) | Unix socket |
| SPIRE Agent | Gateway ({{ gateway_node_ip }}) | Unix socket |

## Trust Domain

```
spiffe://home-ai-lab
```

## Purpose

SPIRE provides cryptographic workload identity:

- **X.509 SVIDs**: Short-lived certificates for mutual TLS
- **Join tokens**: One-time attestation tokens for agent bootstrap
- **Workload attestation**: Verify workload identity via Unix selectors

## Key Commands

```bash
# Server health
spire-server healthcheck

# Generate join token
spire-server token generate -spiffeID spiffe://home-ai-lab/node -ttl 3600

# List entries
spire-server entry show

# Agent health
spire-agent healthcheck
```

## Related

- [Architecture: Security Model](../../architecture/security-model.md)
- [Admin: SPIRE Configuration](../../admin-guide/configuration/spire.md)
- [Troubleshooting: SPIRE](../../troubleshooting/spire.md)
