---
title: "Troubleshooting: SPIRE"
---

# SPIRE Troubleshooting

## Agent Attestation Fails

**Symptom**: SPIRE agent can't connect to server. Log shows attestation errors.

**Diagnose**:

```bash
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck
docker logs spire-agent --tail 30
```

**Fix**:

1. Generate a fresh join token on the Control Node:
   ```bash
   docker compose exec spire-server /opt/spire/bin/spire-server token generate \
       -spiffeID spiffe://home-ai-lab/execution-node -ttl 3600
   ```
2. Update the agent configuration with the new token
3. Restart the agent: `docker compose restart spire-agent`

---

## Expired SVIDs

**Symptom**: Service-to-service calls fail with TLS certificate errors.

**Diagnose**:

```bash
docker compose exec spire-agent /opt/spire/bin/spire-agent api fetch x509
```

Check the expiry timestamp.

**Fix**:

- SVIDs auto-rotate. If they've stopped rotating, the agent may have lost connection to the server
- Re-attest the agent with a new join token
- Verify SPIRE server is healthy: `docker compose exec spire-server /opt/spire/bin/spire-server healthcheck`

---

## SPIRE Server Unreachable

**Symptom**: Agent logs show "connection refused" to server.

**Fix**:

1. Verify the server is running: `docker compose ps spire-server`
2. Check network connectivity: `ping {{ control_node_ip }}`
3. Verify the port (8081) is accessible
4. Check firewall rules

---

## Registration Entry Issues

**Symptom**: Agent is attested but SVIDs don't have the right SPIFFE IDs.

**Check**:

```bash
docker compose exec spire-server /opt/spire/bin/spire-server entry show
```

Verify entries exist for each service with the correct selectors.
