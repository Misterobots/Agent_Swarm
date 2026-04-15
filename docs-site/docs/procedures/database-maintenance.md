---
title: "Procedure: Database Maintenance"
---

# Database Maintenance

PostgreSQL maintenance tasks: vacuum, indexing, backup verification.

## Routine Vacuum

```bash
# Vacuum analyze all tables
docker compose exec postgres psql -U postgres -c "VACUUM ANALYZE;"
```

## Check Database Size

```bash
docker compose exec postgres psql -U postgres -c \
    "SELECT pg_size_pretty(pg_database_size('agent_swarm'));"
```

## Verify Backup Integrity

```bash
# Test restore to a temporary database
docker compose exec postgres createdb -U postgres test_restore
docker compose exec -T postgres pg_restore -U postgres -d test_restore < backup.dump
docker compose exec postgres dropdb -U postgres test_restore
```

## pgvector Maintenance

```bash
# Reindex vector indexes
docker compose exec postgres psql -U postgres -c \
    "REINDEX INDEX CONCURRENTLY idx_embeddings_vector;"
```

## Scheduled Maintenance

Add to crontab:

```cron
# Weekly vacuum
0 4 * * 0 docker compose -f /opt/Agent_Swarm/control_plane/docker-compose.yml exec -T postgres psql -U postgres -c "VACUUM ANALYZE;"
```
