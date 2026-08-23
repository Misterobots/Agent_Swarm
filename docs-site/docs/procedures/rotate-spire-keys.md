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
    -spiffeID spiffe://home-ai-lab/Turing-gateway \
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
# Same process on Turing
docker compose stop spire-agent
nano turing_gateway/config/spire/agent.conf
docker compose up -d spire-agent
```

### 4. Verify

```bash
# Check both agents
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck
```

Both agents should report healthy.

## Emergency Revocation (Compromised Node)

If a node's agent identity is suspected compromised, do not wait for the
regular rotation cadence — revoke it immediately:

### 1. Evict the Compromised Agent

On the Control Node:

```bash
docker compose exec spire-server \
    /opt/spire/bin/spire-server agent evict \
    -spiffeID spiffe://home-ai-lab/<compromised-node>
```

This immediately invalidates the agent's SVID; it can no longer fetch or
renew workload identities.

### 2. Re-attest with a Fresh Token

Generate a new join token for the node (Step 1 above) and repeat the
update procedure for that node only (Step 2 or 3 above, as applicable).
Do not reuse the evicted node's old join token or key material.

### 3. Confirm Containment

```bash
docker compose exec spire-server \
    /opt/spire/bin/spire-server agent list
```

Verify the evicted node is absent, then confirm it reappears only after
successful re-attestation with the new token.

## Notes

- Join tokens are single-use — each agent needs its own token
- Tokens expire after TTL — use them promptly
- Existing SVIDs remain valid until their TTL expires
- Evicting an agent revokes its SVID immediately, independent of TTL —
  use this for suspected compromise rather than waiting on expiry


