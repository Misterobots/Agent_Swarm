---
title: Backup & Restore
---

# Backup & Restore

Strategies for backing up and recovering Agent Swarm data.

## What to Back Up

| Data | Location | Method | Frequency |
|------|----------|--------|-----------|
| PostgreSQL | Control Node | `pg_dump` | Daily |
| Skills Memory | Execution Node volume | File copy | Daily |
| User Projects | Execution Node volume | tar/rsync | Daily |
| Delivered Artifacts | Execution Node volume | tar/rsync | Weekly |
| Training Data | Execution Node volume | tar/rsync | Weekly |
| Docker Compose files | Git repository | `git push` | On change |
| Config files | Git repository | `git push` | On change |
| hollerith dashboards | Gateway Node | API export | On change |

!!! warning "Not Backed Up"
    - Ollama model cache (re-pullable)
    - jacquard TSDB (retention-based, ephemeral)
    - Container images (re-pullable from registry)

## PostgreSQL Backup

```bash
# On Control Node
docker compose exec postgres pg_dump -U postgres -Fc > /backups/pg_$(date +%Y%m%d).dump

# Restore
docker compose exec -T postgres pg_restore -U postgres -d postgres --clean < /backups/pg_20260410.dump
```

### Automated Daily Backup

Add to crontab on Control Node:

```cron
0 3 * * * docker compose -f /opt/Agent_Swarm/control_plane/docker-compose.yml exec -T postgres pg_dump -U postgres -Fc > /backups/pg_$(date +\%Y\%m\%d).dump
```

## Volume Backups

### Skills Memory and Sessions

```bash
# On Execution Node
docker compose exec agent-runtime tar czf /tmp/memory-backup.tar.gz \
    /workspace/agents/skills_memory.json \
    /workspace/agents/context_sessions/

docker cp agent-runtime:/tmp/memory-backup.tar.gz /backups/
```

### User Projects and Artifacts

```bash
# Tar the workspace volumes
docker compose exec agent-runtime tar czf /tmp/workspace-backup.tar.gz \
    /workspace/user_projects/ \
    /workspace/delivered_artifacts/ \
    /workspace/training_data/
```

## Full System Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "Backing up PostgreSQL..."
ssh user@{{ hopper_ip }} \
    "docker compose -f /opt/Agent_Swarm/control_plane/docker-compose.yml exec -T postgres pg_dump -U postgres -Fc" \
    > "$BACKUP_DIR/postgres.dump"

echo "Backing up workspace volumes..."
ssh user@{{ lovelace_ip }} \
    "docker compose -f /opt/Agent_Swarm/execution_plane/docker-compose.yml exec -T agent-runtime tar czf - /workspace" \
    > "$BACKUP_DIR/workspace.tar.gz"

echo "Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
```

## Restore Procedures

### Full Restore

1. Deploy fresh nodes per the [Deployment Guide](../deployment/prerequisites.md)
2. Restore PostgreSQL: `pg_restore` as shown above
3. Restore workspace volumes: `tar xzf workspace.tar.gz`
4. Re-pull models: `ollama pull {{ solver_model }}`, etc.
5. Verify: Run [Post-Deployment Checks](../deployment/post-deploy.md)

### Partial Restore (Skills Memory Only)

```bash
docker cp memory-backup.tar.gz agent-runtime:/tmp/
docker compose exec agent-runtime tar xzf /tmp/memory-backup.tar.gz -C /
```

## Retention Policy

| Data | Retention | Storage |
|------|-----------|---------|
| PostgreSQL dumps | 30 days | Local + offsite |
| Workspace snapshots | 14 days | Local |
| Artifact backups | 90 days | Local + MinIO |

## Related

- [Procedures: Disaster Recovery](../../procedures/disaster-recovery.md) — full recovery runbook
- [Architecture: Memory System](../../architecture/memory-system.md) — what's stored where


