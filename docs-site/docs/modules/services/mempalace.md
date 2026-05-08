---
title: "Service: MemPalace"
---

# MemPalace

Hierarchical semantic memory service. Provides vector-searchable memories,
versioned agent snapshots, and shared team scratchpads behind a single
FastAPI service. Backed by PostgreSQL/pgvector and Ollama embeddings.

> Operator-facing reference. For architecture and design rationale, see
> [Architecture Deep Dive](../../architecture/mempalace-deep-dive.md).
> For the full HTTP API, see
> [Developer Guide → MemPalace API](../../developer-guide/api/mempalace.md).

## Deployment

| Property | Value |
|----------|-------|
| **Node** | Control Plane ({{ hopper_ip }}) |
| **Container** | `mempalace` |
| **Port** | 8200 |
| **URL** | `http://{{ hopper_ip }}:8200` |
| **MCP** | `http://{{ hopper_ip }}:8200/mcp` |
| **Backend** | PostgreSQL (`mempalace` schema) with pgvector |
| **Image** | `control_plane-mempalace` |
| **Compose file** | `control_plane/docker-compose.yml` |
| **Image source** | `control_plane/mempalace/Dockerfile` |
| **Runtime user** | non-root (UID 1000) |
| **Healthcheck** | Docker `HEALTHCHECK` against `/health` |

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `MEMPALACE_DB_USER` | `langfuse` (via `LANGFUSE_DB_USER`) | Postgres user |
| `MEMPALACE_DB_PASSWORD` | (required, via `LANGFUSE_DB_PASSWORD`) | Postgres password |
| `MEMPALACE_DB_HOST` | `postgres` (compose service name) | Postgres host |
| `MEMPALACE_DB_PORT` | `5432` | Postgres port |
| `MEMPALACE_DB_NAME` | `langfuse` (via `LANGFUSE_DB_NAME`) | Database name (mempalace lives in its own schema) |
| `OLLAMA_HOST` | `http://localhost:11434` (overridden in compose to `http://{{ lovelace_ip }}:11434`) | Ollama endpoint |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `EXTRACT_MODEL` | `qwen2.5-coder:14b-instruct-q4_k_m` | LLM used for memory extraction |
| `OLLAMA_TIMEOUT` | `60` | Per-request HTTP timeout (seconds) |
| `OLLAMA_EMBED_RETRIES` | `2` | Retry count on transient embed failures |
| `LOG_LEVEL` | `INFO` | Standard Python logging level |

The Postgres credentials are deliberately shared with the Langfuse database;
MemPalace uses a separate schema (`mempalace.*`) inside the same DB so a
single Postgres instance serves both control-plane services.

## Schema

Five application tables plus the Alembic version tracker, all under the
`mempalace` schema:

| Table | Purpose |
|---|---|
| `mempalace.memories` | Semantic memories (the dominant table) |
| `mempalace.agent_snapshots` | Versioned per-agent learned state |
| `mempalace.team_memories` | Coordinator team scratchpad |
| `mempalace.memory_audit_log` | Append-only audit trail |
| `mempalace.extraction_log` | Per-attempt extraction audit |
| `mempalace.alembic_version` | Single-row migration tracker |

Schema is managed by [Alembic](https://alembic.sqlalchemy.org/) — the app
runs `alembic upgrade head` on boot. Adding a new column or constraint is a
2-step procedure documented in
[Procedures → MemPalace Migrations](../../procedures/mempalace-migration.md).

## Health & status

```bash
# Liveness
curl -fsS http://{{ hopper_ip }}:8200/health
# {"status":"ok","service":"mempalace"}

# Schema state
docker compose -f control_plane/docker-compose.yml exec mempalace alembic current
# 0002_add_unique_constraints (head)

# Counts by type/domain
curl -fsS http://{{ hopper_ip }}:8200/v1/memories/stats | jq

# Per-owner extraction success rate
curl -fsS http://{{ hopper_ip }}:8200/v1/palace/audit/extractions | jq
```

## API surface (overview)

15 REST endpoints under `/v1/...` and 4 MCP tools at `/mcp`. Quick reference:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/v1/memories` | Store a memory (writes audit `created`) |
| `POST` | `/v1/memories/search` | Semantic search |
| `PATCH` | `/v1/memories/{id}` | Update + audit |
| `DELETE` | `/v1/memories/{id}` | Delete + audit |
| `GET` | `/v1/memories/stats` | Counts by type/domain |
| `GET` | `/v1/memories/{id}/audit` | Audit trail |
| `POST` | `/v1/extract` | Run extractor + store + log (single tx) |
| `POST` / `GET` | `/v1/snapshots` | Versioned agent state (race-safe) |
| `POST` / `GET` / `DELETE` | `/v1/team/{team_id}` | Team-scoped key/value |
| `POST` | `/v1/team/{team_id}/search` | Team semantic search |
| `GET` | `/v1/palace/layout` | 3D viewer hierarchy |
| `GET` | `/v1/palace/room` | Memories at a palace coordinate |
| `GET` | `/v1/palace/audit/extractions` | Extraction audit |

Full request/response contracts:
[Developer Guide → MemPalace API](../../developer-guide/api/mempalace.md).

## Operations runbook

### Restart

```bash
ssh misterobots@{{ hopper_ip }}
cd ~/Agent_Swarm/control_plane
docker compose restart mempalace
docker compose logs --tail=50 mempalace
```

### Roll a new image

```bash
cd ~/Agent_Swarm
git pull
cd control_plane
docker compose build mempalace
docker compose up -d --force-recreate mempalace
```

If the new image introduces an Alembic migration, the app will apply it on
boot. For first-time Alembic adoption on an existing DB (one-shot only),
see the migrations procedure.

### Backup the schema

```bash
docker exec postgres pg_dump -U langfuse --schema=mempalace langfuse \
  > ~/mempalace_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
docker exec -i postgres psql -U langfuse -d langfuse \
  < ~/mempalace_backup_<timestamp>.sql
```

### Query the live DB

```bash
docker exec -it postgres psql -U langfuse -d langfuse
# \dt mempalace.*
# SELECT memory_type, domain, count(*) FROM mempalace.memories GROUP BY 1, 2;
```

## Failure modes

| Symptom | Likely cause | First check |
|---|---|---|
| Boot fails with Alembic error | Live DB hasn't been stamped at baseline | `alembic current` — if blank, see migrations procedure |
| `POST /v1/memories` returns 500 | Ollama unreachable for embedding | `curl http://{{ lovelace_ip }}:11434/api/tags` |
| Extraction returns `[]` consistently | LLM model not pulled or returning malformed JSON | Check `extraction_log` + `mempalace` container logs |
| 4xx with `owner_id is required` | Caller did not include `owner_id` in body | All writes require `owner_id`; same constraint applies to MCP tools |
| Slow `/v1/memories/search` | IVFFlat index degenerate (built on empty table) | `REINDEX INDEX mempalace.ix_mem_embedding;` once data volume is meaningful |

## Related

- [Architecture Deep Dive](../../architecture/mempalace-deep-dive.md) — design and rationale
- [Memory System](../../architecture/memory-system.md) — how MemPalace fits with the other memory subsystems
- [Memory Palace (UI)](../../user-guide/palace.md) — the 3D viewer end-users see
- [MemPalace API Reference](../../developer-guide/api/mempalace.md) — full request/response contracts
- [MemPalace Migrations](../../procedures/mempalace-migration.md) — Alembic workflow + deploy procedure
