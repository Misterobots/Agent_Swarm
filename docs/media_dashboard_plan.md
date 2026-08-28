# Media Dashboard — Saltbox / Turing Monitoring Plan

> **Status:** Design + phased build plan. Nothing built yet.
> **Scope:** Turing (`192.168.2.103`) — the Saltbox stack behind Traefik + Cloudflare tunnel.
> **#1 job:** surface a dropped or crash-looping container *fast*, distinguish an intentional dev
> restart from an unexpected death, and catch the "externally unreachable even though the container
> is up" outage class (stale A-record / tunnel / Traefik).
> **Verified against the live host on 2026-07-26** — the findings below override CLAUDE.md where they differ.

---

## TL;DR — Recommendation

**You are not starting from zero. ~90% of a Prometheus power-tier is already deployed on Turing, and ntfy is already wired into Alertmanager.** But the piece that does the *actual* #1 job — "tell me the instant a Saltbox container drops or a public host goes unreachable" — is missing, and the display layer (Grafana) has been sitting in `created`/never-started state since 2026-06-28.

**Recommended architecture: a two-tier hybrid, Uptime-Kuma-led for the MVP.**

- **Tier 1 (MVP — the at-a-glance "are we losing containers?" board + alerts): Uptime Kuma.** One new container. Native Docker-host monitor (per-container up/down/health via the read-only socket-proxy), native HTTP(s) monitors for each `*.shivelymedia.com` public URL (catches the DNS/tunnel class directly), native ntfy push. GUI config, minutes to value, and — crucially — **independent of the Prometheus/Alertmanager chain that is currently incomplete and partly broken.** The thing whose job is "notice when other things die" should not share fate with them.
- **Tier 2 (depth — trends, crash-loop history, CPU/mem, logs): finish the Prometheus + Grafana stack that's already running.** Start Grafana (the dropped container), add the missing container-health + crash-loop + external-blackbox alert rules (they feed the already-wired ntfy receiver), and import the dashboards that already exist in the repo.

**Why Kuma-led rather than "just finish Prometheus"** (the honest fork — see [§8](#8-recommendation-rationale--the-one-real-fork)): the specific pain — *"is this exact container up right now, alert me the moment it isn't, and don't cry wolf when I restart it on purpose"* — is what Kuma is purpose-built for, expressed in a GUI instead of PromQL absence-rules, and it survives the Prometheus chain itself breaking. The Prometheus tier is the right place for *why it broke* and *what the trend is*, not for the frontline up/down watch.

If you would rather run a single system and are willing to invest in PromQL, **finishing Prometheus+Grafana alone is a defensible alternative** — covered in [§8](#8-recommendation-rationale--the-one-real-fork).

---

## 1. Ground truth — what's actually on Turing right now

Verified live via SSH + the socket-proxy on 2026-07-26. **This section corrects several stale assumptions in the task brief and CLAUDE.md.**

### 1a. Containers (35 total)

**Saltbox network (`saltbox`) — the media stack (12):**
`traefik`, `authentik`, `authentik-worker`, `authentik-postgres`, `cloudflared`, `jellyfin`, `radarr`, `sonarr`, `sabnzbd`, `seerr`, **`overseerr`** (a *second* Seerr-family container, `sctx/overseerr`, recreated ~3h ago), `aha-site`.

**Other networks (`ai_lab_net`) — platform + the monitoring stack:**
`agent_runtime`, `memex_ui` (healthy), `ollama-turing`, `redis-turing` (healthy), `docker-socket-proxy-turing`, `spire-agent-turing` (healthy), `docs-site`, `openclaude_grpc` (healthy), `openhands_sandbox`, `agent_ide_coding`, `agent_ide_devops`, `dev_sandbox`, `mxmobile`, `bush-http`.

**Monitoring / observability stack — ALREADY DEPLOYED (this is the big surprise):**

| Container | Image | State | Host port |
|---|---|---|---|
| `prometheus-turing` | prom/prometheus | running | `9091` → 9090 |
| `alertmanager-turing` | prom/alertmanager | running | `9093` |
| `cadvisor-turing` | gcr.io/cadvisor | running (healthy) | `8888` → 8080 |
| `blackbox-exporter-turing` | prom/blackbox-exporter | running | `9115` |
| `loki-turing` | grafana/loki | running | — |
| `promtail-turing` | grafana/promtail | running | — |
| `ntfy-Turing` | binwiederhier/ntfy | running (healthy) | `8086` → 80 |
| **`hollerith-turing`** | **grafana/grafana** | **`created` — NEVER STARTED** | — |
| `open-webui-turing` | open-webui | `created` — never started | — |

All monitoring containers run from **`/home/misterobots/docker-compose.yml`** (not the repo's `turing_gateway/`), all with `restart: unless-stopped`, all with restart-count `0`.

### 1b. Key facts that drive the design

- **The display layer is dark.** `hollerith-turing` (Grafana) has been in `created` state since 2026-06-28 — created but never started, exit 0, no logs. `restart: unless-stopped` does **not** rescue a `created` container (it only restarts ones that have *run* and exited). `open-webui-turing` is in the same state. **This is the "we keep losing containers" symptom captured in the act.**
- **ntfy is already integrated.** Alertmanager's `default-receiver` already POSTs to `https://notify.shivelymedia.com/home-ai-alerts` with a bearer token (plus a Zoho SMTP email fallback). We reuse this, we don't build it.
- **The socket-proxy is read-only for lifecycle.** Env: `CONTAINERS=1`, `INFO=1`, `VERSION=1`, `PING=1`, `POST=1` — **but** `ALLOW_RESTARTS=0`, `ALLOW_STOP=0`, `ALLOW_START=0`, `EXEC=0`, **`EVENTS=0`**, `NETWORKS=0`. So: we can *read* container state/health/restart-count, but (a) we **cannot** take remediation actions through it, and (b) there is **no real-time Docker events stream** — polling only, unless we flip `EVENTS=1`.
- **Two Docker access paths exist.** On-host tools (cAdvisor, Promtail) read the raw `/var/run/docker.sock` directly (full access, local only). Off-host/Windows management uses the restricted proxy on `:2375` via SSH tunnel. A dashboard *on Turing* can use either; a dashboard reading remotely is limited to the proxy's read-only surface.

### 1c. What the existing Prometheus stack monitors — and doesn't

**`prometheus.yml` scrapes:** `cadvisor-Turing:8080` (Turing container metrics), `192.168.2.101:8081` (Lovelace cAdvisor), `agent_runtime` custom metrics on both nodes, and a blackbox `http_2xx` probe of the **two internal** `agent_runtime` health endpoints only.

**`auth_alert_rules.yml` (the only rule file) covers:** agent-runtime down, Redis disconnect, 401/403 spikes, request-volume drop, IoT action anomalies. **All agent-runtime / auth-focused.**

**Alertmanager receivers:**
- `maintenance-router` webhook → `http://maintenance-router:9095/webhook/alertmanager` — **DEAD** (no `maintenance-router` container is running; the agent-safe auto-repair path is inert, though `continue:true` means it doesn't block the others).
- `default-receiver` → Zoho email + **ntfy webhook** (`notify.shivelymedia.com/home-ai-alerts`, bearer token). **Live.**

**blackbox modules available:** `http_2xx`, `http_post_2xx`, `tcp_connect`, `icmp`, `ssh_banner`, `pop3s_banner`, `irc_banner`.

**Repo prior art (in `turing_gateway/`):** `dashboards/` has 8 Grafana dashboards already (`infrastructure_overview.json`, `system_overview.json`, `mission_control.json`, `agent_activity.json`, `gpu_inference.json`, `template_performance.json`, `training_live.json`, `training_pipeline.json`), plus `provisioning/{datasources,dashboards}`, `config/{prometheus,alertmanager,blackbox,loki,promtail}`, `setup_monitoring.sh`, and `docker-compose-monitoring-stack.yml`. A `services/maintenance_router/` and a Mission Control UI (`ui/src/app/mission-control`, `monitor-hub.tsx`) exist in a backup worktree — so a monitoring/ops surface has been attempted before and can be leaned on.

### 1d. External reachability spot-check (from Lovelace, 2026-07-26)

`memex`, `jellyfin`, `radarr`, `sonarr`, `seerr`, `sabnzbd` `.shivelymedia.com` → **302** (Authentik redirect = reachable & healthy). `dash.shivelymedia.com` → **500** (anomaly — Traefik dashboard; worth a look, not central to this plan). Nothing is currently *watching* these on a schedule — that's the gap.

### The gap summary (what stands between "today" and "the #1 job done")

| # | Gap | Consequence today |
|---|---|---|
| G1 | No container up/down or crash-loop alert rules | **A dropped Saltbox container is not surfaced or alerted at all** |
| G2 | Grafana never started (`created`) | No dashboard exists to look at, even though data is being collected |
| G3 | blackbox probes only 2 internal endpoints | **The stale-A-record / tunnel / Traefik outage class is not caught** |
| G4 | `maintenance-router` receiver is dead | Alerts to that route silently fail; auto-repair path inert |
| G5 | No dev-restart vs. crash distinction | Any restart would cry wolf (once G1 exists) |
| G6 | Deploy hygiene: the live stack runs from `/home/misterobots/docker-compose.yml`; keep it synchronized with tracked `turing_gateway/docker-compose.yml` and reconcile with full-project `up -d` | **Root cause of "we keep losing containers"** |

---

## 2. WHAT to monitor

Four signal classes, in priority order for the #1 job.

**Class A — Container liveness & health (the core).** Per Saltbox container:
- State: `running` / `exited` / `restarting` / `created` / `dead`. **Include `created`** — that's the exact state Grafana got stuck in.
- Health status where a `HEALTHCHECK` exists (`healthy` / `unhealthy` / `starting`).
- **Restart-count delta over a window** — a *climbing* count = crash loop (the most important derived signal; a single restart is noise, a rising count is a fire).
- Uptime / last-seen (to compute "down for > grace period").

Target set (curated, so "expected but absent" is detectable): the 12 Saltbox containers + the tunnel/edge trio `traefik`, `cloudflared`, `authentik` (their death takes *everything* down), + optionally the monitoring stack itself (`prometheus-turing`, `ntfy-Turing` — so the watchdog notices if the watchdog is blind).

**Class B — External reachability (the DNS/tunnel outage class).** For each public host, an HTTP(s) check of the **real public URL** through the full CF→Traefik→Authentik path:
`memex`, `jellyfin`, `radarr`, `sonarr`, `sabnzbd`, `seerr`/`overseerr`, `dash`, `docs`, `notify`, `aha` (enumerate from Traefik routers). A `302`→Authentik or expected `200` = up; connection failure / DNS failure / wrong-cert / `5xx` = down.
- **To isolate the DNS-hijack case specifically:** run the same check twice — once against the public hostname (DNS + tunnel path) and once against Traefik directly on the LAN (`Host:` header override to `192.168.2.103`). Public fails + LAN passes ⇒ **it's DNS/tunnel, not the service** (exactly the stale-A-record outage you hit). Both fail ⇒ the service/Traefik itself.

**Class C — Edge/tunnel health.** Cloudflared tunnel up (container + `cloudflared` metrics if exposed), Traefik up + its entrypoints responding, wildcard TLS cert not expiring. blackbox already has the modules for this.

**Class D — Resource depth (nice-to-have, Tier 2).** Per-container CPU / memory / restart history, host disk (the `/mnt/buffer` Docker volume drive), Loki logs for the last error before a crash. All already collectable via the running cAdvisor/Promtail — surfaced in Grafana, not needed for the MVP alert.

---

## 3. HOW to collect — options weighed against the live constraints

| Approach | Fit for #1 job | Effort | Notes given *this* host |
|---|---|---|---|
| **(a) Small poller vs. `:2375` socket-proxy on a timer** | OK | Medium (write + host it) | Works with `CONTAINERS=1`. But you'd be re-building up/down logic, a UI, and alert plumbing that Kuma gives free. Only worth it if you want it *inside* memex_ui. |
| **(b1) Uptime Kuma** | **Best** | **Low** | Native "Docker Host" monitor → per-container up/down/health via the socket-proxy (read-only is fine). Native HTTP monitors → Class B. Native ntfy. GUI. One container. **Independent of the Prometheus chain.** |
| **(b2) Prometheus + cAdvisor + Grafana** | Good for depth, awkward for frontline up/down | **Already ~90% deployed** | cAdvisor gives rich metrics, but "container X is DOWN" relies on `absent()` / `container_last_seen` staleness against a curated set — fiddlier than Kuma for the exact #1 job. Perfect for Class D + trends. |
| **(c) Docker healthchecks + events listener** | Great for real-time + dev-restart distinction | Medium + **needs a config change** | Requires `EVENTS=1` on the socket-proxy (currently `0`), or reading the raw socket on-host. Best source for exit-codes and clean-stop-vs-crash. Consider as a Tier-2 enrichment, not the MVP. |

**Chosen collection:** **(b1) Uptime Kuma for Class A + B (MVP)**, layered over the **already-running (b2) Prometheus/cAdvisor** for Class C + D. Keep (c) in reserve — flip `EVENTS=1` only if we later want event-accurate dev-restart detection.

**Simplicity vs. power for a home lab:** Kuma is the simplicity win for the frontline watch; the Prometheus stack (already paid for) is the power layer for depth. Running both is justified *here* specifically because they don't share failure modes and the Prometheus alert chain is currently incomplete + has a dead receiver.

---

## 4. Distinguishing an intentional dev restart from an unexpected death

This is a first-class requirement, so it gets a first-class design. **Primary mechanism is signal-based (needs no human discipline); an explicit escape hatch is available for planned longer work.**

**Primary — signal heuristics (default behavior):**
1. **Grace period.** Only alert if a container is down **> ~90–120 s**. An intentional `docker restart` / `compose up -d <svc>` is back in seconds → never alerts. This one rule kills the vast majority of dev-restart false positives.
2. **Exit code / OOM.** Clean stop = exit `0`. Crash = non-zero exit or `OOMKilled`. Available via Docker inspect (raw socket) or cAdvisor. Non-zero ⇒ alert immediately, skip grace.
3. **Restart-count climbing (crash loop).** `changes(container_start_time_seconds[15m]) > 3` (Prometheus) or Kuma's repeated-down transitions ⇒ **loud** alert regardless of grace — this is the worst case and must never be suppressed.
4. **Stuck in `created` / `exited` and staying there** (the Grafana case) ⇒ alert; `restart:` won't fix it, so a human must.

Net rule: *brief gap + returns healthy + exit 0* → info/silent (assume dev restart). *Down past grace, or non-zero exit / OOM, or restart-count climbing, or stuck created/exited* → alert, escalating with severity.

**Escape hatch — explicit maintenance mode (for planned work longer than the grace period):**
- A `dev-restart <container>` / `maint on|off <container>` wrapper script that (a) pauses the relevant Kuma monitor via Kuma's API (or sets a Kuma maintenance window) for N minutes and (b) optionally posts a low-priority "🔧 maintenance" note to ntfy, then does the restart. Auto-expires so you can't forget to turn it back on.
- Cheap to add; makes intentional multi-minute rebuilds silent without weakening the crash-loop path.

---

## 5. WHERE to display

- **Primary board = Uptime Kuma's dashboard + a status page.** Red/green grid, mobile-friendly, one glance answers "are we losing containers?". Publish behind Authentik via a Traefik router (e.g. `status.shivelymedia.com` or a `/status` path — reuse the `authentik@file` middleware pattern). A Kuma **status page** can also be scoped to the media services for a cleaner "is the media stack up" view.
- **Depth = Grafana** (`hollerith-turing`, once started) for Class C/D dashboards. The repo already has `infrastructure_overview.json` / `system_overview.json` / `mission_control.json` to import.
- **Wall display = the existing kiosk** (`turing_gateway/kiosk/`, the "Memex Brain" rack display — currently renders `memex_brain.html`). Phase 3: embed the Kuma status page or a Grafana kiosk-mode panel so the rack always shows stack health. Low effort — it's already a rendering surface with a `deploy.sh`.
- **Product surface = Mission Control in memex_ui** (later). Prior art exists (`ui/src/app/mission-control`, `monitor-hub.tsx` in the backup worktree; the "unified ops surface" direction). A compact status strip pulling Kuma's API or Prometheus fits the existing Governance + Mission Control + Ops surface. Treat as an integration phase, not MVP.

---

## 6. ALERTING

**Reuse the running ntfy — don't rebuild it.**
- **Kuma → ntfy** via Kuma's native ntfy notifier. Use a **dedicated topic** (e.g. `saltbox-down`) distinct from Alertmanager's `home-ai-alerts`, so container/reachability alerts are separable and can carry their own phone priority/sound.
- **Severity mapping:**
  - Crash-loop, or `traefik`/`cloudflared`/`authentik` down, or *all* external hosts unreachable → **high priority** (ntfy priority 5, with sound/vibration).
  - Single container down past grace, single external host unreachable → **default priority**.
  - Recovery ("✅ back up") → **low/min priority** (confirmation without noise).
- **Fix the dead `maintenance-router` receiver (G4):** either (a) stand up `services/maintenance_router` (it exists in the repo) so the agent-safe auto-repair route works, or (b) remove that route from `alertmanager.yml` so it stops silently failing. Decide as part of Tier 2.
- **Alert on the watchdog's own blindness:** a Kuma monitor for `prometheus-turing` and `ntfy-Turing` themselves, and a Prometheus "no data from Kuma" dead-man's-switch if we later cross-wire them.

---

## 7. Phased build plan

### Phase 0 — Stabilize what's already there (½ day, do first)
Root-causes G2 + G6 and gets the existing investment working before adding anything.
1. `docker start hollerith-turing` (Grafana). Confirm it comes up; check its provisioning (datasource → Prometheus `:9090` internal, dashboards from `turing_gateway/dashboards/`). Investigate *why* it was never started (compose subset? failed dependency?).
2. Decide the fate of `open-webui-turing` (start or remove — don't leave zombies).
3. **Maintain the deploy source (G6):** the live project remains `/home/misterobots/docker-compose.yml`, mirrored by tracked `turing_gateway/docker-compose.yml`. Validate and copy the tracked template to the root path, then use full-project `docker compose up -d` so nothing is left in `created`. The live `/home/misterobots/config/*` versus tracked `turing_gateway/config/*` drift still needs the same treatment.
4. Confirm the `dash.shivelymedia.com` 500 is benign or fix it.
- **Acceptance:** Grafana reachable and showing the existing infra dashboard with live cAdvisor data; no containers stuck in `created`; deploy source tracked.

### Phase 1 — MVP: Uptime Kuma frontline watch + ntfy (1 day) ← the money phase
Directly delivers the #1 job.
1. Add `uptime-kuma` to the tracked compose (single container, persistent volume, `restart: unless-stopped`, on a network that can reach the socket-proxy and the public URLs). Traefik router behind `authentik@file` at `status.shivelymedia.com`.
2. **Docker Host monitor** → the socket-proxy; add one monitor per curated Class-A container (12 Saltbox + traefik/cloudflared/authentik), with the **grace period** from §4.
3. **HTTP monitors** (Class B) → each public `*.shivelymedia.com` URL; treat `302`/expected `200` as up.
4. **ntfy notifier** on the `saltbox-down` topic with the §6 severity mapping.
5. Publish a **status page** scoped to the media services.
- **Acceptance:** stop a non-critical container (e.g. `sabnzbd`) → Kuma flips red and an ntfy push lands within ~2 min; `docker restart sabnzbd` → no alert (grace) or a recovery note only. Simulate the DNS class (temporarily point one HTTP monitor at a dead host) → external-unreachable alert fires while the container monitor stays green.

### Phase 2 — Depth: Prometheus alert rules + external blackbox + crash-loop (1–2 days)
Fills G1/G3/G5 in the power tier so it's not just Kuma.
1. New rule file (`container_health_rules.yml`): container-down (`absent`/`container_last_seen` staleness against the curated set), crash-loop (`changes(container_start_time_seconds[15m]) > 3`), `unhealthy` health status — routed to the **existing** ntfy receiver.
2. Add blackbox probe targets for the **public `*.shivelymedia.com` URLs** (+ the LAN-direct twin from §2 Class B) to `prometheus.yml`, with `ProbeFailed` rules — this is the Prometheus-side catch for the DNS/tunnel class.
3. Import the existing Grafana dashboards; add a container-health panel + an external-reachability panel.
4. Resolve G4 (`maintenance-router`: deploy it or remove the route).
- **Acceptance:** the same failure drills as Phase 1 also fire via Prometheus→Alertmanager→ntfy; crash-loop a container (repeated exits) → loud alert; Grafana shows restart-count history.

### Phase 3 — Surface & polish (optional, as time allows)
1. Kiosk: render the Kuma status page / Grafana kiosk panel on the "Memex Brain" rack display.
2. `dev-restart` / maintenance-mode wrapper (§4 escape hatch).
3. Mission Control status strip in memex_ui (§5), reusing the backup-worktree prior art.
4. Consider `EVENTS=1` on the socket-proxy for event-accurate dev-restart detection if the heuristic proves too coarse.

---

## 8. Recommendation rationale & the one real fork

**Why Kuma-led hybrid (recommended):**
- Nails the *exact* stated pain in a GUI, not PromQL absence-rules: per-container up/down + grace-period dev-restart tolerance + per-host external checks.
- **Failure-mode independence** — the current Prometheus→Alertmanager→ntfy chain has *no container-down rules* and a *dead receiver*. A self-contained watchdog that doesn't share fate with the thing it watches is the right call for the component whose entire job is "notice when things die."
- Minutes-to-value; a 3-person lab shouldn't hand-roll up/down logic + UI + alert plumbing.
- Complements (doesn't replace) the sunk Prometheus investment, which becomes the depth/trend/log tier.

**The alternative — "one system, finish Prometheus only":** skip Kuma; do Phase 0 + Phase 2, and write the container-down/crash-loop/blackbox rules on the existing stack. **Defensible if** you want a single pane of glass and are comfortable maintaining PromQL. **Downsides:** the frontline watch then depends on the same chain that's currently the weakest link; "is this container up *right now*" is clunkier via `absent()`/staleness; and the dev-restart-vs-crash distinction takes more rule engineering than Kuma's grace period. This is the single decision worth your call before Phase 1.

**Not recommended:** a bespoke poller in memex_ui as the *primary* monitor (reinvents Kuma) — but a memex_ui status strip *reading from* Kuma/Prometheus (Phase 3) is a good product-surface add.

---

## 9. Risks, gotchas & decisions for you

- **Deploy hygiene is the actual root cause (G6).** Until the live compose is tracked and brought up as a full unit, containers will keep landing in `created`. Phase 0 addresses this; it's arguably higher-value than any dashboard.
- **Socket-proxy is read-only + `EVENTS=0`.** MVP works within this (Kuma polls `CONTAINERS`). Real-time events or any auto-remediation needs a scoped config change — deliberately deferred.
- **Config source-of-truth drift.** Deployed configs live in `/home/misterobots/config/`; the repo has a parallel copy in `turing_gateway/config/`. They can still diverge even though the obsolete `-Justin-PC.yml` compose fork has been retired. Pick one as canonical in Phase 0.
- **Traefik router verification is hard behind Authentik** — every path 302s to Authentik identically, so an unauthenticated curl proves nothing. Verify new routers via valid label YAML + zero `docker logs traefik` errors + an authenticated browser test (per CLAUDE.md).
- **Two Seerr-family containers** (`seerr` + `overseerr`) — confirm which is canonical so the monitor set isn't ambiguous.

**Decisions needed from you:**
1. **Kuma-led hybrid (recommended) vs. Prometheus-only** ([§8](#8-recommendation-rationale--the-one-real-fork)).
2. ntfy topic: dedicated `saltbox-down` (recommended) vs. reuse `home-ai-alerts`.
3. `maintenance-router`: deploy it, or remove the dead route.
4. Display priority: is the rack **kiosk** a Phase-3 must-have, or is the Kuma/Grafana web board enough?
