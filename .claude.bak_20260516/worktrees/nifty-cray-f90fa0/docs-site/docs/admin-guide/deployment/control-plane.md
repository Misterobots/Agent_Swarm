---
title: Deploy Control Plane
---

# Deploy Control Plane

The Control Plane (Hopper, {{ hopper_ip }}) runs identity, databases, tracing, and memory services.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| SPIRE Server | 8081 | Workload identity CA |
| PostgreSQL | 5432 | Primary database (pgvector) |
| Langfuse | 3000 | LLM tracing |
| ClickHouse | 8123 | Langfuse analytics backend |
| MemPalace | 8200 | Semantic memory store |
| MinIO | 9000/9001 | Object storage |
| Redis | 6379 | Cache |

## Steps

### 1. Prepare the Node

```bash
ssh user@{{ hopper_ip }}
cd /opt/Agent_Swarm
git pull origin main
```

### 2. Configure Environment

Copy and edit the environment file:

```bash
cp network.env.example network.env
nano network.env
```

Key variables for the Control Plane:

| Variable | Example | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | (generate strong password) | PostgreSQL admin password |
| `LANGFUSE_SECRET_KEY` | (generate random key) | Langfuse session secret |
| `MINIO_ROOT_USER` | `minio` | MinIO admin user |
| `MINIO_ROOT_PASSWORD` | (generate strong password) | MinIO admin password |

!!! danger "Credential Security"
    Never commit `network.env` to Git. It contains secrets. Use `.gitignore` to exclude it.

### 3. Start Services

```bash
cd control_plane
docker compose --env-file ../network.env up -d
```

### 4. Initialize SPIRE Server

```bash
# Check SPIRE server is running
docker compose exec spire-server /opt/spire/bin/spire-server healthcheck

# Generate join tokens for agents
docker compose exec spire-server \
    /opt/spire/bin/spire-server token generate \
    -spiffeID spiffe://home-ai-lab/execution-node \
    -ttl 3600
```

Save the generated token — you'll need it when deploying the Execution Node.

### 5. Verify Services

```bash
# PostgreSQL
docker compose exec postgres pg_isready

# Langfuse
curl -s http://localhost:3000/api/public/health | jq .

# MemPalace
curl -s http://localhost:8200/health

# MinIO
curl -s http://localhost:9000/minio/health/live
```

### 6. Initialize Database

```bash
# Create pgvector extension
docker compose exec postgres psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| SPIRE healthcheck fails | Check `docker compose logs spire-server` for config errors |
| PostgreSQL won't start | Check disk space, verify `POSTGRES_PASSWORD` is set |
| Langfuse 500 errors | Ensure ClickHouse is running: `docker compose logs clickhouse` |
| MemPalace can't connect to PG | Verify PostgreSQL is up and `POSTGRES_PASSWORD` matches |

## Next

→ [Deploy Execution Plane](execution-plane.md)


