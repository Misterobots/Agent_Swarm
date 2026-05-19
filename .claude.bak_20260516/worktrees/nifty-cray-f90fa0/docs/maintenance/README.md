# Maintenance system

This is **slice 1** of a layered maintenance system for Memex/Agent_Swarm:
observability → action → coordination. Slice 1 wires Prometheus alerts to
either the autonomous repair daemon or a human queue surfaced in Mission
Control.

```
Prometheus ─▶ Alertmanager ─webhook▶ maintenance_router (FastAPI)
                                         │
                              classify by labels + manifest
                                         ▼
                        ┌──────────────┬──────────────┐
                        ▼              ▼              ▼
                 Redis queue       Postgres        audit log
                 (agent path)      queue item     (every dispatch)
                        │              │
                        ▼              ▼
              auto_repair_daemon  /mission-control
                                  Maintenance Queue tab
```

The router is **additive**. Existing email and ntfy receivers still fire — if
the router is down, the only thing missing is autonomous routing. The poll
loop inside `auto_repair_daemon.py` continues working unchanged.

## Files in this slice

| Path                                                | Role                                    |
| --------------------------------------------------- | --------------------------------------- |
| `config/maintenance/manifest.yaml`                  | Single source of truth alert → action   |
| `config/maintenance/manifest.schema.json`           | JSON Schema for the manifest            |
| `services/maintenance_router/`                      | FastAPI router service (port 9095)      |
| `agents/auto_repair_daemon.py` (subscriber thread)  | Consumes the agent path                 |
| `turing_gateway/config/alertmanager/alertmanager.yml` | Alertmanager wiring                   |
| `ui/src/app/mission-control/`                       | Unified UI surface                      |
| `ui/src/components/mission-control/`                | Maintenance Queue + audit log component |
| `scripts/maintenance_smoke_test.py`                 | End-to-end smoke test                   |
| `scripts/maintenance_provision_db.sh`               | One-shot Postgres role + DB provisioner |

## Manifest

`config/maintenance/manifest.yaml` is the sole place that decides whether an
alert is autonomous or human. Each rule:

```yaml
- alert: ServiceDown
  match: { job: postgres }
  action: restart_container
  action_args: { container: postgres-hopper, node: hopper }
  agent_safe: true
  blast_radius: low
  cooldown_seconds: 300
```

Rules:

- `agent_safe: true` is the **only** flag that lets the router publish to the
  agent path. Anything missing or `false` goes to the human queue.
- `agent_safe: true` also requires `action` (validated at load).
- `match` labels are AND-ed; the alert label set must be a superset of `match`.
- First match wins. Put specific rules above catch-alls.
- `cooldown_seconds` is keyed by `(action, sorted action_args)` and stored in
  Redis as a TTL — prevents repair storms.

Reload after editing: `POST /admin/reload-manifest` or send the router
container `SIGHUP`.

## Adding a new repair

1. Add the action function to `agents/auto_repair_daemon.py` (or reuse one of
   `repair_authentik_database` / `restart_container`).
2. Wire it into `_execute_routed_action()` in the same file.
3. Add the rule to `config/maintenance/manifest.yaml` with `agent_safe: true`.
4. Validate locally: `pytest services/maintenance_router/tests/`.
5. Reload: `curl -X POST http://192.168.2.103:9095/admin/reload-manifest`.

## Adding a non-agent-safe alert

Just add a rule with `agent_safe: false` (or omit the field). The alert lands
in the human queue at `/mission-control` → Maintenance Queue. Optional fields:

- `runbook` — relative path or URL surfaced as a link in the UI.
- `blast_radius` — `low` / `medium` / `high`, surfaced as a badge.

Drop the runbook into `docs/maintenance/runbooks/` and link it from the
manifest.

## Operations

### First-time deploy

1. Provision the Postgres role/db on Hopper:
   ```bash
   MAINTENANCE_DB_PASSWORD='<set in turing_gateway/.env>' \
     bash scripts/maintenance_provision_db.sh
   ```
2. Make sure `turing_gateway/.env` has:
   ```
   MAINTENANCE_DB_NAME=maintenance
   MAINTENANCE_DB_USER=maintenance
   MAINTENANCE_DB_PASSWORD=<your value>
   ALERT_SMTP_PASSWORD=<rotated Zoho app password>
   ```
3. Bring the gateway stack up:
   ```bash
   cd turing_gateway && docker compose up -d alertmanager maintenance-router
   ```
4. Confirm `curl http://192.168.2.103:9095/healthz` returns 200.

### End-to-end smoke test

```bash
python scripts/maintenance_smoke_test.py --router http://192.168.2.103:9095
# Add --consume to drain the Redis queue so the daemon doesn't act on it.
```

The script posts three synthetic alerts (agent path, human path, cooldown
re-fire) and asserts on the audit log + Redis queue depth.

### When the router is down

Nothing else changes. `auto_repair_daemon`'s poll loop still self-heals the
authentik DB index issue and other detected conditions; Alertmanager email +
ntfy receivers still fire (the router is on a `continue: true` route).
