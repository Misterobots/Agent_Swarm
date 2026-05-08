# Runbook: Container high memory

**Trigger alert(s):** `ContainerHighMemory`

**Why human:** A container chewing memory may need a restart, but it may also
need investigation (memory leak vs steady-state growth vs runaway agent loop).
Auto-restarting masks the underlying cause and drops in-flight work. Decide
before acting.

## Triage

1. **Identify the offender.** Alert labels include `name=<container>` and
   `instance=<host>`.
2. **Check the trend in Grafana** before deciding to restart:
   - Has memory been growing linearly for hours? → likely a leak; capture a
     heap dump if possible before restart.
   - Did it spike in the last few minutes? → check logs for a hot request
     loop or a stuck job.
   - Is it pinned at the limit? → the limit is too low for current load;
     consider raising before restarting.

## Acting

- **Restart (no investigation needed).** From the offending node:
  ```bash
  docker restart <container>
  ```
- **Capture state first (preferred for repeat offenders).**
  ```bash
  docker logs --tail=2000 <container> > /tmp/<container>-$(date +%s).log
  docker stats --no-stream <container>
  ```
  Then restart and file an issue with the captured artifacts attached.
- **Raise the limit.** Edit the relevant compose file (`turing_gateway/`,
  `hopper/`, or `lovelace/` docker-compose.yml), bump `mem_limit:`, redeploy.
  Treat as a governance change if the stack is shared.

## After

- Mark the maintenance queue item **Resolved** with a one-line note (which
  path you took).
- If this is the third+ time this container has tripped the alert in 7 days,
  open a governance request to either fix the leak or raise the limit
  permanently.
