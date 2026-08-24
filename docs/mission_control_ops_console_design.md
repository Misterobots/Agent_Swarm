# Unified Mission Control — Ops Console (fresh design)

> **Purpose:** one surface to **observe, act on, and troubleshoot** the home-lab fleet —
> replacing the "bounce between Uptime Kuma, Grafana, and a terminal" reality we have now.
> Designed from the goal first; the reconcile section maps it onto the existing code.
> **Status:** design only. Nothing built.

---

## 1. The problem with where we landed

We built solid **observability** — Uptime Kuma (up/down + external) and Prometheus/Grafana/Loki
(metrics/logs/trends). But:
- They're **two panes watching the same containers** — redundant as *dashboards*.
- Both are **observe-only** — when something drops, you still leave the dashboard, SSH in, and
  `docker restart`. No recovery, no maintenance actions, no troubleshooting *in place*.

That's the observability layer of a three-layer system, delivered as two tools instead of feeding
one console.

## 2. Goal & principles

**One console** where an operator (or an agent) can, without leaving the page:
1. **See** what's wrong right now, across every stack and node.
2. **Act** — restart/stop/start/recreate/redeploy, open a maintenance window, silence an alert.
3. **Troubleshoot** — logs, last error, exit code/OOM, resource trend, recent restarts.
4. **Govern recovery** — see what the auto-repair kernel did, approve/deny agent-safe actions.

Principles: single pane · observe+act+troubleshoot together · safe-by-default actions
(confirm destructive, audit everything, agent-safe boundary) · data sources are *behind* the
console, never separate destinations · automated recovery is **visible and governable**, not a
black box.

## 3. Target capabilities

**A. Fleet grid (observe).** Every service across Turing / Lovelace / Hopper in one grid:
state (running/exited/**created**/restarting/dead), health, uptime, **restart-count trend**,
external reachability inline, CPU/mem sparkline. Grouped by stack (Saltbox · AI/Memex · data-plane)
and node; **down/degraded float to the top**. This is the "are we losing containers" answer at a glance.

**B. Service drawer (act + troubleshoot).** Click a service → side panel:
- **Actions:** Restart · Stop · Start · Recreate · Pull+redeploy · Open maintenance window
  (the `dev-restart` behavior as a button).
- **Logs:** live tail (Loki/docker), last-error highlighted.
- **Why it dropped:** exit code, OOM flag, last N restart timestamps.
- **Metrics:** CPU/mem/net/disk over time.
- **Context:** Traefik route, public URL + reachability, healthcheck definition.

**C. Incident feed (coordinate).** One unified alert stream (Kuma + Alertmanager de-duplicated),
each with Acknowledge / Silence / Maintenance-window, the **auto-repair actions taken**, and
approve/deny for anything gated as human-in-the-loop. A timeline per incident.

**D. Recovery & automation (the action kernel, surfaced).** What `auto_repair_daemon` watches,
what it can do, agent-safe vs human-gated; one-click **common fixes** (restart unhealthy, clear
`created`-state zombies, redeploy drifted); an **audit log** of every action — human *or* daemon.

**E. Edge/tunnel health.** CF tunnel up, Traefik routers/entrypoints, wildcard cert expiry, public
reachability — the DNS/stale-A-record/tunnel outage class as its own tile (it's a distinct failure mode).

## 4. Architecture

```
memex_ui  →  /mission-control  (ONE React surface: grid + drawer + incident feed)
                    │  reads                         │  acts
                    ▼                                ▼
        Ops API (in agent_runtime)  ───────────────────────────
          status  ← aggregates: Kuma API · Prometheus/cAdvisor · Loki
          logs    ← Loki / docker logs
          alerts  ← Alertmanager + Kuma  (unified, de-duped feed)
          actions → auto_repair_daemon  (host-side, real docker access, agent-safe boundary)
                    │
        auto_repair_daemon = automated recovery + the ONLY thing that mutates containers
```

- The console talks to **one backend** (an Ops API in `agent_runtime`) that *aggregates* the data
  sources and *dispatches* actions to `auto_repair_daemon`.
- **Kuma, Prometheus/cAdvisor, and Loki become data sources** feeding that API — not user destinations.
  Kuma stays the best up/down + external-check + alerting engine; Prometheus/Loki stay for
  metrics/logs/trends. The redundancy dissolves because **neither is "the dashboard" anymore.**
- These external systems (Kuma, `auto_repair_daemon`, `maintenance_router`, the whole watch/recover
  stack) live in a **separate repo** (`fleet-sentinel`) and consume Memex/Agent_Swarm purely as a
  service — the shared Redis `maintenance:system_alert` queue, the Hopper `maintenance` Postgres DB,
  and `agent_runtime`'s HTTP API — never by importing Agent_Swarm's internal code. `agent_runtime`'s
  own `agents/ops/{routes,actions}.py` (the governed restart-dispatch API this console calls) stays
  in Agent_Swarm, since it's part of what `agent_runtime` already exposes as that service surface.

## 5. Action & safety model

- **Nothing mutates through the read-only socket-proxy.** Actions go through `auto_repair_daemon`
  (already host-privileged, behind the agent-safe boundary) — this is why the socket-proxy can stay
  read-only. *(Final action path is confirmed in the reconcile/audit — see §7.)*
- **Destructive actions confirm** (stop/recreate/redeploy). Restart and maintenance-window are low-risk.
- **Every action is audited** (actor = human user or daemon, target, time, result) and shown in the feed.
- **Agent-safe vs human-gated:** the daemon auto-executes only the class of fixes marked agent-safe;
  everything else lands in the console's approve/deny queue (this is your existing coordination layer).

## 6. What happens to the two dashboards

| Tool | New role |
|---|---|
| Uptime Kuma | Up/down + external-reachability **engine** + alert source behind the Ops API; keep its status page for a lightweight public/kiosk view. Not a primary operator destination. |
| Prometheus + cAdvisor | Metrics/trend + crash-loop **data source**; alert rules stay. |
| Loki | Log **source** for the drawer's live tail. |
| Grafana | Deep-dive / historical analysis for when you *want* raw dashboards — not the daily driver. |

Net: **one operator console, several sources.** No more two-panes-same-containers.

## 7. Reconcile results (audited against the code, 2026-07)

**Headline: ~70% of this already exists in `/mission-control` — it's disconnected and incomplete, not absent.** A Fleet grid, a service drawer (restart + logs), a full alert-classification + human-queue service with audit UI, and the auto-repair kernel are all in the repo. The redundancy you felt is real, but the fix is *wire the observability we built into the console that already exists* — not build a third thing.

**Three findings that explain why it didn't feel unified or actionable:**
1. **The existing Fleet grid is blind to dropped containers.** The Ops API's `normalize_containers` hardcodes `status:"running"` and lists only *running* containers (`agents/main.py`) — a container that exits/crashes/sticks in `created` **vanishes from the grid** instead of showing red. The one thing you needed most, the current console literally cannot show. (That's a big reason standing up Kuma felt necessary — Kuma *does* show down.) **FIXED 2026-08-20** — see commit `5ca429d`: added `?all=true` to the Docker API queries and read the real `State` field; verified live by stopping/restoring `docs-site` and watching the grid report it.
2. **The action path is split-brain, and the half wired to the UI is the broken half.** The UI restart button POSTs to the read-only socket-proxy → almost certainly **403 in prod** (no `ALLOW_RESTARTS`). Meanwhile `auto_repair_daemon` restarts via **SSH → `docker` CLI**, which works — but isn't wired to any button. **FIXED** — see commit `0889033` (`feat(ops): extract governed Mission Control actions`): the restart mutation moved into `agents/ops/{routes,actions}.py`, dispatching through the same Redis queue the daemon consumes, with input validation, request-ID tracking, and actor attribution.
3. **The incident-feed engine is deployed nowhere.** `maintenance_router` (classifier + human queue + audit, with a finished UI in `maintenance-queue.tsx`) was found dead in prod (the same dead Alertmanager webhook target from the media-dashboard Phase 2 cleanup) — so that whole surface was empty. **Confirmed live and healthy 2026-08-20** (7 queued items, 15 audited dispatches) — it had been redeployed since; tracked its compose (`turing_gateway/docker-compose.maintenance-router.yml`).

| Capability | Status | Reuse / gap |
|---|---|---|
| A Fleet grid | DONE (state fix) | real container state now flows through; still needs health, restart-trend, CPU/mem, stack grouping, down-first sort in the UI |
| B Service drawer | PARTIAL | Restart (via the daemon queue, fixed) + (docker, not Loki) log modal exist; add stop/start/recreate/redeploy/maintenance + why-dropped + metrics + drawer UI |
| C Incident feed | PARTIAL | full Alertmanager→classify→queue+audit built w/ UI, confirmed live; add Kuma ingestion + de-dupe + per-incident timeline |
| D Recovery kernel | PARTIAL | daemon (now systemd-persistent on Turing) + manifest agent-safe boundary exist; surface watched-conditions/capabilities, add one-click fixes, unify audit (daemon repairs are in-memory only) |
| E Edge/tunnel health | BUILD | nothing today — CF tunnel / Traefik routers / cert expiry / public reachability |
| Aggregating Ops API | PARTIAL | `/api/v1/ops/*` exists, now reports real container state; still not consuming Kuma / Prometheus / cAdvisor / Loki |
| Action layer | DONE | resolved — `agents/ops/actions.py` dispatches to `auto_repair_daemon` via the shared queue; socket-proxy stays read-only |

**Action-path decision: route UI actions through `auto_repair_daemon`; do NOT open the proxy — implemented.** It's the only reliably-working, host-privileged mutator behind the agent-safe boundary. `auto_repair_daemon` itself is now a **systemd service on Turing** (`auto-repair-daemon.service`, `Restart=always`), migrated off a fragile Windows background-process host that died on sleep.

## 8. Reconciled phased plan

- **P0 — light up what's built but dead** ✅ **DONE.** `maintenance_router` confirmed live; `auto_repair_daemon` fixed (a permanent Authentik health-check false-positive that would have auto-restarted SSO every 10min once a password was set) and made persistent (systemd on Turing); the restart button now dispatches through the daemon instead of the read-only proxy. Bonus: found and fixed `docker-socket-proxy-turing` silently detached from all Docker networks — had been blinding all 22 Kuma monitors + the Ops API's Turing fleet view with no signal anything was wrong.
- **P1 — make the console see the truth** — core fix ✅ **DONE** (real container state now flows through `ops_health`). Remaining: wire Kuma + Prometheus/cAdvisor + Loki into the Ops API; upgrade the Fleet grid UI (state/health/restart-trend/CPU-mem/grouping/down-first rendering). *This is where Kuma/Grafana become sources, not destinations.*
- **P2 — full actionable drawer:** stop/start/recreate/redeploy/maintenance-window + why-it-dropped + metrics + Loki tail, all routed through the daemon (the queue-dispatch pattern is proven — extend `agents/ops/actions.py`).
- **P3 — unify + govern:** Kuma+Alertmanager de-duped feed; surface auto-repair rules/capabilities; one-click common fixes; unified audit (daemon repairs + human actions + router dispatches all currently separate).
- **P4 — edge/tunnel tile:** CF tunnel / Traefik / cert expiry / public reachability.
- **P5 — retire redundancy:** Kuma/Grafana → sources/deep-dive; Mission Control is the daily driver.

## 9. Repo split (2026-08-21)

The watch/recover stack (Uptime Kuma, `auto_repair_daemon`, `maintenance_router`, the container-health
Prometheus rules, the seeding/maintenance scripts) moved to its own repo, **`fleet-sentinel`**, since it
had diverged into a genuinely separate concern from Agent_Swarm's core purpose. It consumes Memex/
Agent_Swarm strictly as an external service (the shared Redis queue, the Hopper Postgres DB,
`agent_runtime`'s HTTP API) — no code import in either direction. This design doc, `agents/ops/*`, and
`agents/main.py`'s Ops API stay here, since they're `memex_ui`'s own Mission Control surface and what
`agent_runtime` exposes as the service boundary `fleet-sentinel` calls into.
