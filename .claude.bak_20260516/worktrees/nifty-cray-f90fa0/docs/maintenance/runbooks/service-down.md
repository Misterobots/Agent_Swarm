# Runbook: Service down

**Trigger alert(s):** `ServiceDown` (when not handled by the agent path)

**Why human:** The agent path covers known-safe restarts (postgres, redis,
langfuse, agent_runtime). Anything else falls through to this runbook so a
human can decide whether a restart, an upstream check, or a network fix is
appropriate.

## Triage (60 seconds)

1. **Is it really down, or is the probe wrong?** Hit the service directly:
   ```bash
   curl -fsS http://<host>:<port>/healthz   # or whichever endpoint the probe uses
   ```
   If it answers, the alert is a false positive — investigate the probe in
   `turing_gateway/config/prometheus/`.
2. **Is its host reachable?** `ping`, then check `docker ps` on the affected
   node. If the host is unreachable, escalate — this is an infrastructure
   problem, not a service problem.
3. **Did it just restart?** Check `docker inspect <container> --format '{{.State.StartedAt}}'`.
   A flapping container needs investigation, not another restart.

## Acting

- **Restart, low-blast service.** Same node:
  ```bash
  docker restart <container>
  ```
  Watch for it to come back healthy in Grafana before closing the alert.
- **Restart, high-blast service.** Coordinate with whoever else might be
  using the system. For shared services (postgres, gateway, mission control
  itself), prefer to ack the alert, give a 60-second heads-up, then restart.
- **Don't know what to do.** Mark the queue item **Escalated** and ping the
  owner. The audit log captures who saw it and when.

## After

- Resolve the queue item with a note describing what you did.
- If this service has tripped ServiceDown without an obvious cause more than
  twice in a week, consider promoting it to the agent path: add a rule to
  `config/maintenance/manifest.yaml` with `agent_safe: true` and a
  conservative cooldown.
