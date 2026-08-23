---
title: "Troubleshooting: System Offline"
---

# System Offline / Cross-Service Triage

Use this page when the failure isn't obviously scoped to one component — the UI shows a global "System Offline" state, dashboards go blank across the board, or you're not yet sure which service is at fault. It walks through the quick diagnostic commands first, then the general triage flow, then the monitoring stack (Grafana/Prometheus/Loki), which cuts across every other service page.

!!! tip
    Once you've narrowed the problem to a specific component, switch to its dedicated page: [Agent Runtime](agent-runtime.md), [Ollama](ollama.md), [SPIRE](spire.md), [Network](network.md), [GPU](gpu.md), [Docker](docker.md), [ComfyUI](comfyui.md), [Langfuse](langfuse.md), [Voice](voice.md).

## Quick Diagnostic Commands

Run these first — they cover the majority of "is it even up" questions in one pass.

```bash
# Check running containers on each node
docker compose ps                              # from each node's compose directory

# Check a remote node's containers (if SSH configured)
ssh <user>@<node-ip> "cd ~/Agent_Swarm/execution_plane && docker compose ps"

# Check Prometheus scrape targets (all should be UP)
curl http://{{ turing_ip }}:9091/api/v1/targets | python -m json.tool

# Check agent runtime health
curl http://{{ lovelace_ip }}:8008/api/v1/health/nodes

# Check Ollama models loaded
curl http://{{ lovelace_ip }}:{{ ollama_port }}/api/ps
curl http://{{ turing_ip }}:{{ ollama_port }}/api/ps
```

---

## "System Offline" in the UI

**Symptoms**: Sidebar shows red "System Offline". Chat requests hang or return errors.

**Diagnose**:

```bash
docker compose ps agent-runtime
docker compose logs agent-runtime --tail 50

# From any machine
curl http://{{ lovelace_ip }}:8008/  # Should return 200 or JSON
```

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| `agent-runtime` container crashed | `docker compose restart agent-runtime` |
| Missing `.env` variables (startup fail) | Check `docker compose logs agent-runtime` for missing var errors; update `.env` |
| Port 8008 not reachable from the gateway node | Check firewall/network bridging; verify the Traefik route to `<lovelace-ip>:8008` — see [Network](network.md) |
| Ollama not responding (`OLLAMA_HOST` unreachable) | Restart Ollama — see [Ollama](ollama.md) |
| SPIRE agent down (SVID fetch fail at startup) | `docker compose restart spire-agent`, then `agent-runtime` — see [SPIRE](spire.md) |

!!! note
    If the root cause turns out to be scoped to one subsystem (Ollama, SPIRE, networking, etc.), the deep-dive steps live on that subsystem's own page — this section is only the first-pass triage across all of them.

---

## Monitoring Stack (Grafana / Prometheus / Loki)

### Grafana Panels Show "No Data"

**Step 1**: Identify the panel's datasource — `Prometheus`, `Loki`, or `PostgreSQL-Swarm` — each is diagnosed differently.

**Step 2 — Prometheus panels**:

```bash
# Check target status
curl http://{{ turing_ip }}:9091/api/v1/targets 2>/dev/null | python -m json.tool | grep -A2 '"health"'

# Manually check a metric
curl 'http://{{ turing_ip }}:9091/api/v1/query?query=agent_state' | python -m json.tool
```

If a target is `DOWN`, restart the affected container and verify its metrics port is reachable.

**Step 3 — Loki panels**:

The most common cause is a **wrong label name**. Promtail labels containers as `container`, NOT `container_name`.

```
WRONG:  {container_name="agent_runtime"}
RIGHT:  {container="agent_runtime"}
```

Test a query directly:

```bash
curl -s 'http://{{ turing_ip }}:3100/loki/api/v1/query?query=%7Bcontainer%3D%22agent_runtime%22%7D' | python -m json.tool
```

If Loki returns no streams, check that Promtail is running and can reach the Docker socket:

```bash
docker compose ps promtail
docker compose logs promtail --tail 30
```

**Step 4 — PostgreSQL-Swarm panels**:

```bash
# Test connection from the Grafana container
docker exec grafana-turing psql postgresql://langfuse:langfuse@{{ hopper_ip }}:5432/langfuse \
  -c "SELECT COUNT(*) FROM swarm.performance_history"
```

If the table is empty, no data has been written yet — the `swarm.*` tables are populated by the agent runtime during normal usage. Run a few chat requests and check again.

---

### Prometheus "agent-runtime" Target Always DOWN

**Cause**: The agent runtime metrics path is `/metrics/` (trailing slash), not `/metrics`.

Verify the scrape config:

```yaml
- job_name: 'agent-runtime'
  metrics_path: /metrics/   # must have the trailing slash
  static_configs:
    - targets: ['{{ lovelace_ip }}:8008']
```

Test: `curl http://{{ lovelace_ip }}:8008/metrics/` — should return Prometheus text format.

---

### cAdvisor Target Shows No Container Name Labels

**Cause**: The cAdvisor proxy container isn't running.

```bash
docker compose ps cadvisor-proxy
docker compose logs cadvisor-proxy --tail 20
```

The proxy enriches raw cAdvisor metrics with container `name` labels by reading the Docker socket. Without it, container panels in Grafana show hash IDs instead of readable names and won't match name-based filters.

---

## Useful Log Queries (Grafana Loki)

```logql
# All agent errors in the last hour
{container="agent_runtime"} |~ "(?i)(error|exception|failed)" | json

# MarsRL quality issues
{container="agent_runtime"} |~ "(?i)(score|verifier|corrector|mars)"

# SPIRE authentication events
{container="agent_runtime"} |~ "(?i)(spiffe|svid|spire)"

# JWT-ACE events
{container="agent_runtime"} |~ "(?i)(jwt|capability|token|denied)"

# Training pipeline progress
{container="agent_runtime"} |~ "(?i)(training|grpo|qlora|export)"

# All container errors, any service
{container=~".+"} |~ "(?i)(error|fatal|panic)" | json
```
