# Langfuse Observability Deployment Specification

**Version**: 1.0
**Date**: 2026-02-09
**Status**: Deployed ✅

## 1. Overview

Langfuse is deployed on the Control Plane (<control-node-ip>) to provide LLM observability, tracing, and debugging capabilities for the Agentic Hive.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Control Plane (<control-node-ip>)                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Langfuse Web │  │  ClickHouse  │  │    MinIO     │          │
│  │   (UI/API)   │  │  (Traces)    │  │  (S3 Blob)   │          │
│  │   :3000      │  │   :8123      │  │   :9190      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│  ┌──────────────┐  ┌──────┴───────┐                             │
│  │    Redis     │  │  PostgreSQL  │                             │
│  │   (Cache)    │  │  (Metadata)  │                             │
│  │   :6379      │  │   :5432      │                             │
│  └──────────────┘  └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ LANGFUSE_HOST
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                 Execution Plane (Local GPU Node)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐                                               │
│  │Agent Runtime │ ──── @observe decorators ────────────────────►│
│  │  (Phidata)   │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Services

| Service      | Image                        | Port | Purpose                    |
| :----------- | :--------------------------- | :--- | :------------------------- |
| langfuse-web | langfuse/langfuse:3          | 3000 | UI and API                 |
| clickhouse   | clickhouse/clickhouse-server | 8123 | Trace storage (OLAP)       |
| minio        | minio/minio:latest           | 9190 | S3-compatible blob storage |
| redis        | redis:7.2-alpine             | 6379 | Cache and queue            |
| postgres     | postgres:15-alpine           | 5432 | Metadata storage           |

## 4. Configuration

### Environment Variables

| Variable                             | Value                              | Required |
| :----------------------------------- | :--------------------------------- | :------- |
| DATABASE_URL                         | postgresql://langfuse:...@postgres | ✅       |
| CLICKHOUSE_URL                       | http://clickhouse:8123             | ✅       |
| CLICKHOUSE_MIGRATION_URL             | clickhouse://...@clickhouse:9000   | ✅       |
| CLICKHOUSE_CLUSTER_ENABLED           | false                              | ✅       |
| NEXTAUTH_SECRET                      | (from env)                         | ✅       |
| NEXTAUTH_URL                         | http://<control-node-ip>:3000          | ✅       |
| ENCRYPTION_KEY                       | (64-char hex)                      | ✅       |
| REDIS_HOST / REDIS_PORT / REDIS_AUTH | redis / 6379 / (password)          | ✅       |
| LANGFUSE*S3_EVENT_UPLOAD*\*          | MinIO configuration                | ✅       |

### Access URLs

| Service       | URL                       | Credentials          |
| :------------ | :------------------------ | :------------------- |
| Langfuse UI   | http://<control-node-ip>:3000 | User signup required |
| MinIO Console | http://<control-node-ip>:9191 | minio / miniosecret  |

## 5. Health Checks

All services include health checks with proper startup dependencies:

```yaml
depends_on:
  clickhouse:
    condition: service_healthy
  db:
    condition: service_healthy
  redis:
    condition: service_started
  minio:
    condition: service_healthy
```

## 7. MarsRL Process Rewards

| :------------------- | :--------- | :---------------------------------------------------------- |
| `solver_score`       | Categorical| 1.0 = Pass, 0.7 = Corrected, 0.0 = Failed.                  |
| `verifier_round_N`   | Numeric    | The raw score (0.0-1.0) awarded by the verifier in round N. |
| `final_quality`      | Numeric    | Final score of the code presented to the user.              |
| `safety_infraction`  | Boolean    | Logged if Llama-Guard triggers a block.                     |

### Tagging
Traces are tagged with `session_id` and `origin_agent` to enable filtering by workload type (Coding, Creative, IoT).

## 6. Security Considerations

- **Redis**: Password authentication enabled (`--requirepass`)
- **MinIO**: Access key authentication (not exposed externally)
- **Langfuse**: User account required for UI access
- **ClickHouse**: Internal network only, cluster mode disabled
- **Encryption**: Data-at-rest encryption via ENCRYPTION_KEY

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `control_plane/docker-compose.yml` | Infrastructure | Langfuse, ClickHouse, PostgreSQL, Redis, MinIO service definitions |
| `agents/governance.py` | Implementation | @observe decorators, trace generation |
| `agents/mars_loop.py` | Implementation | MarsRL scoring and process reward logging |
| [Langfuse Docs](https://langfuse.com/docs) | External | Official Langfuse documentation |
| [ClickHouse](https://clickhouse.com/docs) | External | OLAP database for trace storage |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-02-09 | AI-Copilot | v1.0 — Initial Langfuse deployment specification |

</details>

---

## Maintenance & Update Guide

### Upgrading Langfuse

1. Update the Langfuse image tag in `control_plane/docker-compose.yml`.
2. Check the [Langfuse changelog](https://langfuse.com/changelog) for breaking changes.
3. Run `docker compose pull langfuse-web && docker compose up -d langfuse-web`.

### Managing ClickHouse Storage

1. ClickHouse stores all trace data. Monitor disk usage on the Control Node.
2. For cleanup, use ClickHouse TTL policies or manual data deletion for old traces.

### Adding New MarsRL Metrics

1. Define the metric in `agents/mars_loop.py` where rewards are logged.
2. Add the metric to the MarsRL Process Rewards table in Section 7.
3. Update Grafana dashboards if visualization is needed.

---

## Functionality Testing

### Manual Verification

1. **Health check**: `curl http://<control-node-ip>:3000/api/public/health` → should return 200.
2. **Trace ingestion**: Send a chat request → verify a new trace appears in the Langfuse UI within 5 seconds.
3. **MarsRL scores**: Check that `solver_score`, `verifier_round_N`, and `final_quality` appear in the trace metadata.
4. **Security**: Verify Redis requires password authentication and ClickHouse is not exposed externally.
