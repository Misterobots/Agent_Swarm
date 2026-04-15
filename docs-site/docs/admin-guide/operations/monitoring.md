---
title: Monitoring
---

# Monitoring

Dashboards, alerts, and health checks for Agent Swarm.

## Dashboards

Access Grafana at `http://{{ gateway_node_ip }}:3001`.

### Pre-Built Dashboards

| Dashboard | Description |
|-----------|-------------|
| **System Overview** | Node health, container status, CPU/memory/disk |
| **Agent Performance** | Request throughput, MarsRL scores, intent distribution |
| **GPU Utilization** | VRAM usage, model loading times, inference rates |
| **Ollama Metrics** | Model stats, request queue, token generation speed |
| **Alert Status** | Active alerts and history |

### Importing Dashboards

```bash
# Copy dashboard JSON files to Grafana provisioning
cp r730_gateway/config/grafana/dashboards/*.json \
    /var/lib/grafana/dashboards/
```

Or import manually: Grafana → Dashboards → Import → Upload JSON.

## Health Checks

### Quick Status Script

```bash
#!/bin/bash
echo "=== Control Plane ==="
curl -sf http://{{ control_node_ip }}:3000/api/public/health && echo "Langfuse: OK" || echo "Langfuse: DOWN"
curl -sf http://{{ control_node_ip }}:8200/health && echo "MemPalace: OK" || echo "MemPalace: DOWN"

echo "=== Execution Plane ==="
curl -sf http://{{ execution_node_ip }}:{{ agent_runtime_port }}/ && echo "Runtime: OK" || echo "Runtime: DOWN"
curl -sf http://{{ execution_node_ip }}:{{ ollama_port }}/api/tags > /dev/null && echo "Ollama: OK" || echo "Ollama: DOWN"

echo "=== Gateway ==="
curl -sf http://{{ gateway_node_ip }}:3001/api/health && echo "Grafana: OK" || echo "Grafana: DOWN"
curl -sf http://{{ gateway_node_ip }}:9091/-/healthy && echo "Prometheus: OK" || echo "Prometheus: DOWN"
curl -sf http://{{ gateway_node_ip }}:3100/ready && echo "Loki: OK" || echo "Loki: DOWN"
```

### Prometheus Targets

Check all scrape targets: `http://{{ gateway_node_ip }}:9091/targets`

All targets should show **UP** state. Down targets indicate connectivity issues.

## Alerts

AlertManager at `http://{{ gateway_node_ip }}:9093` routes alerts to email and ntfy.

### Default Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| `NodeDown` | Node unreachable for 2 min | Critical |
| `HighCPU` | CPU > 90% for 5 min | Warning |
| `HighMemory` | Memory > 85% for 5 min | Warning |
| `OllamaOOM` | Ollama container OOM | Critical |
| `DiskFull` | Disk > 90% full | Critical |
| `HighErrorRate` | API 5xx > 5% for 5 min | Warning |
| `SlowResponse` | p95 latency > 30s for 5 min | Warning |

### Alert Configuration

Edit alert rules in `r730_gateway/config/prometheus/alert_rules.yml`.

AlertManager routing in `r730_gateway/config/alertmanager/alertmanager.yml`:

```yaml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-email'
    - match:
        severity: warning
      receiver: 'ntfy-push'
```

## Key Metrics to Watch

| Metric | Good | Investigate |
|--------|------|-------------|
| Agent Runtime response time (p95) | < 10s | > 30s |
| MarsRL pass rate (first try) | > 80% | < 60% |
| Ollama VRAM usage | < 90% | > 95% |
| Disk usage | < 80% | > 90% |
| Error rate (5xx) | < 1% | > 5% |

## Related

- [Architecture: Observability](../../architecture/observability.md) — full stack details
- [Procedures: Configure Alerting](../../procedures/configure-alerting.md) — alert setup
- [Troubleshooting](../../troubleshooting/index.md) — common issues
