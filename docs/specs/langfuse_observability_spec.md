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
