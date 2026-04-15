---
title: "Module: Metrics"
---

# Metrics

Prometheus metric definitions exposed by the Agent Runtime.

## Files

| File | Purpose |
|------|---------|
| `agents/metrics.py` | Metric definitions and registration |

## Endpoint

```
GET /metrics
```

## Defined Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `agent_state` | Gauge | `state` | Current agent activity state |
| `workflow_steps_total` | Counter | `step` | Workflow step completions |
| `capability_gating_events_total` | Counter | `decision` | Capability gate allow/deny |
| `http_requests_total` | Counter | `method`, `endpoint`, `status` | API request count |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency |
| `mars_verification_score` | Histogram | `intent` | MarsRL verification scores |
| `mars_iterations_total` | Counter | `intent` | Total MarsRL correction iterations |
| `intent_classification_total` | Counter | `intent` | Classified intent counts |

## Custom Metrics

To add a new metric:

```python
from prometheus_client import Counter, Histogram, Gauge

my_counter = Counter(
    "my_custom_events_total",
    "Description of the metric",
    ["label1", "label2"],
)

# Increment
my_counter.labels(label1="value", label2="other").inc()
```

## Scraping

Prometheus on the Gateway scrapes `/metrics` every 15 seconds:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'agent-runtime'
    static_configs:
      - targets: ['{{ execution_node_ip }}:{{ agent_runtime_port }}']
```

## Related

- [Architecture: Observability](../architecture/observability.md)
- [Admin: Monitoring](../admin-guide/operations/monitoring.md)
