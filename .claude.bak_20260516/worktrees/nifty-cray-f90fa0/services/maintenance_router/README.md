# Maintenance Router

Tiny FastAPI service that sits between Alertmanager and the action layer of
the maintenance system. It classifies incoming alerts using
`config/maintenance/manifest.yaml` and routes each one to either:

- **agent path** — RPUSH onto Redis `maintenance:system_alert` queue, where
  the extended `agents/auto_repair_daemon.py` consumes it and runs the
  declared repair action (only for rules with `agent_safe: true`).
- **human path** — INSERT into the Postgres `maintenance_queue` table for
  Mission Control UI pickup. Default for anything not explicitly marked
  agent-safe, or that's currently inside its action's cooldown window.

Every classification writes an audit row to `maintenance_dispatch`.

## Endpoints

| Method | Path                                     | Purpose                                     |
| ------ | ---------------------------------------- | ------------------------------------------- |
| POST   | `/webhook/alertmanager`                  | Alertmanager webhook receiver               |
| GET    | `/api/maintenance/queue`                 | Pending items for Mission Control UI        |
| POST   | `/api/maintenance/queue/{id}/ack`        | Ack/escalate/resolve a queue item           |
| GET    | `/api/maintenance/audit`                 | Recent dispatch history                     |
| POST   | `/admin/reload-manifest`                 | Re-read manifest.yaml (also responds SIGHUP) |
| GET    | `/healthz`                               | Liveness                                    |

## Configuration

Environment variables:

| Var                       | Default                          | Purpose                                  |
| ------------------------- | -------------------------------- | ---------------------------------------- |
| `MAINTENANCE_MANIFEST`    | `/etc/maintenance/manifest.yaml` | Path to manifest                         |
| `REDIS_HOST`              | `redis-turing`                   | Redis host (system_alert queue, cooldowns) |
| `REDIS_PORT`              | `6379`                           |                                          |
| `MAINTENANCE_DB_DSN`      | _(unset)_                        | Full libpq DSN; takes precedence         |
| `MAINTENANCE_DB_HOST`     | `192.168.2.102`                  | Hopper Postgres                          |
| `MAINTENANCE_DB_PORT`     | `5432`                           |                                          |
| `MAINTENANCE_DB_NAME`     | `maintenance`                    |                                          |
| `MAINTENANCE_DB_USER`     | `maintenance`                    |                                          |
| `MAINTENANCE_DB_PASSWORD` | _(empty)_                        |                                          |

## Local development

```bash
cd services/maintenance_router
python -m venv .venv && .venv/bin/pip install -r requirements.txt
MAINTENANCE_MANIFEST=../../config/maintenance/manifest.yaml \
MAINTENANCE_DB_DSN="host=localhost dbname=maintenance user=postgres" \
REDIS_HOST=localhost \
.venv/bin/uvicorn maintenance_router.app:app --reload --port 9095
```

## Tests

```bash
.venv/bin/pip install pytest fakeredis
.venv/bin/pytest tests/
```

Tests cover manifest loading, classification (agent_safe / human / cooldown
/ unmatched), and the webhook end-to-end with `fakeredis` and an in-memory
storage stand-in.
