---
title: "Procedure: Disaster Recovery"
---

# Disaster Recovery

Full system recovery from backup.

## Prerequisites

- Access to backup files (see [Backup & Restore](../admin-guide/operations/backup-restore.md))
- Fresh node deployments ready

## Recovery Steps

### 1. Deploy Fresh Nodes

Follow the deployment guides in order:

1. [Control Plane](../admin-guide/deployment/control-plane.md)
2. [Execution Plane](../admin-guide/deployment/execution-plane.md)
3. [Gateway](../admin-guide/deployment/gateway.md)

### 2. Restore PostgreSQL

```bash
# On Control Node
docker compose exec -T postgres pg_restore \
    -U postgres -d postgres --clean \
    < /backups/postgres.dump
```

### 3. Restore Workspace

```bash
# On Execution Node
docker cp workspace.tar.gz agent-runtime:/tmp/
docker compose exec agent-runtime tar xzf /tmp/workspace.tar.gz -C /
```

### 4. Re-Pull Models

```bash
docker exec ollama ollama pull {{ solver_model }}
docker exec ollama ollama pull {{ router_model }}
docker exec ollama ollama pull {{ verifier_model }}
```

### 5. Re-Attest SPIRE Agents

Generate fresh join tokens and attest both agents. See [Rotate SPIRE Keys](rotate-spire-keys.md).

### 6. Verify

Run the full [Post-Deployment Verification](../admin-guide/deployment/post-deploy.md).

## Recovery Time Estimate

| Component | Time |
|-----------|------|
| Deploy nodes | 30 min |
| Restore databases | 10 min |
| Pull models | 20 min |
| SPIRE attestation | 5 min |
| Verification | 10 min |
| **Total** | **~75 min** |
