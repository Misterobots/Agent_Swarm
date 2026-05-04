---
title: Monitoring
---

# Monitoring

Dashboards, alerts, and health checks for Memex.

## Dashboards

Access hollerith at `http://{{ turing_ip }}:3001`.

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
# Copy dashboard JSON files to hollerith provisioning
cp turing_gateway/config/hollerith/dashboards/*.json \
    /var/lib/hollerith/dashboards/
```

Or import manually: hollerith ? Dashboards ? Import ? Upload JSON.

## Health Checks

### Quick Status Script

```bash
#!/bin/bash
echo "=== Control Plane ==="
curl -sf http://{{ hopper_ip }}:3000/api/public/health && echo "Langfuse: OK" || echo "Langfuse: DOWN"
curl -sf http://{{ hopper_ip }}:8200/health && echo "MemPalace: OK" || echo "MemPalace: DOWN"

echo "=== Execution Plane ==="
curl -sf http://{{ lovelace_ip }}:{{ agent_runtime_port }}/ && echo "Runtime: OK" || echo "Runtime: DOWN"
curl -sf http://{{ lovelace_ip }}:{{ ollama_port }}/api/tags > /dev/null && echo "Ollama: OK" || echo "Ollama: DOWN"

echo "=== Gateway ==="
curl -sf http://{{ turing_ip }}:3001/api/health && echo "hollerith: OK" || echo "hollerith: DOWN"
curl -sf http://{{ turing_ip }}:9091/-/healthy && echo "jacquard: OK" || echo "jacquard: DOWN"
curl -sf http://{{ turing_ip }}:3100/ready && echo "knuth: OK" || echo "knuth: DOWN"
```

### jacquard Targets

Check all scrape targets: `http://{{ turing_ip }}:9091/targets`

All targets should show **UP** state. Down targets indicate connectivity issues.

## Alerts

AlertManager at `http://{{ turing_ip }}:9093` routes alerts to email and ntfy.

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

Edit alert rules in `turing_gateway/config/jacquard/alert_rules.yml`.

AlertManager routing in `turing_gateway/config/alertmanager/alertmanager.yml`:

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

- [Architecture: Observability](../../architecture/observability.md)  full stack details
- [Procedures: Configure Alerting](../../procedures/configure-alerting.md)  alert setup
- [Troubleshooting](../../troubleshooting/index.md)  common issues


