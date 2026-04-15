---
title: "Procedure: Rotate SPIRE Keys"
---

# Rotate SPIRE Keys

Regenerate SPIRE join tokens and re-attest agents.

## When to Rotate

- Regularly (quarterly recommended)
- After a security incident
- When adding/removing nodes

## Steps

### 1. Generate New Tokens

On the Control Node:

```bash
# Token for Execution Node
docker compose exec spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://home-ai-lab/execution-node \
    -ttl 3600

# Token for Gateway Node
docker compose exec spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://home-ai-lab/r730-gateway \
    -ttl 3600
```

Save both tokens.

### 2. Update Execution Node

```bash
# Stop SPIRE agent
docker compose stop spire-agent

# Update join token in agent.conf
nano execution_plane/config/spire/agent.conf
# Set: join_token = "<new-token>"

# Restart
docker compose up -d spire-agent
```

### 3. Update Gateway Node

```bash
# Same process on R730
docker compose stop spire-agent
nano r730_gateway/config/spire/agent.conf
docker compose up -d spire-agent
```

### 4. Verify

```bash
# Check both agents
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck
```

Both agents should report healthy.

## Notes

- Join tokens are single-use — each agent needs its own token
- Tokens expire after TTL — use them promptly
- Existing SVIDs remain valid until their TTL expires
