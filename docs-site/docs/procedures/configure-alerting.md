---
title: "Procedure: Configure Alerting"
---

# Configure Alerting

Set up Prometheus alerts and AlertManager notifications.

## Steps

### 1. Define Alert Rules

Edit `r730_gateway/config/prometheus/alert_rules.yml`:

```yaml
groups:
  - name: agent-swarm
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: OllamaDown
        expr: up{job="ollama"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Ollama is unreachable"
```

### 2. Configure AlertManager

Edit `r730_gateway/config/alertmanager/alertmanager.yml`:

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@example.com'

route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'email'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://ntfy-server/alerts'
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
```

### 3. Restart Services

```bash
docker compose restart prometheus alertmanager
```

### 4. Test Alerts

```bash
# Manually fire a test alert
curl -X POST http://{{ gateway_node_ip }}:9093/api/v1/alerts \
    -H "Content-Type: application/json" \
    -d '[{"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test alert"}}]'
```

Check that the notification arrives.
