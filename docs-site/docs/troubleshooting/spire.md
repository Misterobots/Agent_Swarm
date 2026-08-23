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
2. Check network connectivity: `ping {{ hopper_ip }}`
3. Verify the port (8081) is accessible
4. Check firewall rules

Quick health probe:

```bash
curl http://{{ hopper_ip }}:8081/health
```

---

## Registration Entry Issues

**Symptom**: Agent is attested but SVIDs don't have the right SPIFFE IDs.

**Check**:

```bash
docker compose exec spire-server /opt/spire/bin/spire-server entry show
```

Verify entries exist for each service with the correct selectors.

**One-time enrollment** (if the workload entry is missing entirely):

```bash
# Run on the SPIRE server node
docker exec spire-server spire-server entry create \
  -spiffeID spiffe://home-ai-lab/agent/runtime \
  -parentID spiffe://home-ai-lab/agent/node \
  -selector docker:label:spiffe.io/spiffe-id:spiffe://home-ai-lab/agent/runtime
```

---

## Agent Runtime Logs "SPIFFE SVID fetch failed"

**Symptom**: `agent-runtime` logs an SVID fetch failure at startup.

**Impact**: Non-fatal in most configurations — the agent runtime continues with degraded mTLS.

**Fix**:

```bash
docker compose restart spire-agent
sleep 10
docker compose restart agent-runtime
```

If the issue persists after restart, the workload attestation entry may be out of date (e.g. after an image rebuild that changed the container SHA). Re-register the workload entry (see the one-time enrollment command above) on the SPIRE server.


