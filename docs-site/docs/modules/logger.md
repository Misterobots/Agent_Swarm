---
title: "Module: Logger"
---

# Logger

Structured logging setup for Agent Swarm.

## Files

| File | Purpose |
|------|---------|
| `agents/logger_setup.py` | Logger configuration, formatters, handlers |

## Setup

```python
from agents.logger_setup import setup_logging

setup_logging(level="INFO")
logger = logging.getLogger(__name__)
```

## Log Levels

| Level | Use |
|-------|-----|
| `DEBUG` | Detailed diagnostic info |
| `INFO` | Normal operational events |
| `WARNING` | Unexpected but handled situations |
| `ERROR` | Failed operations (with contextual info) |
| `CRITICAL` | System-level failures |

## Outputs

| Destination | Format | Purpose |
|-------------|--------|---------|
| Console (stdout) | Human-readable | Development |
| File (`logs/`) | JSON | Persistent storage |
| Docker logs | JSON | Picked up by Promtail → Loki |

## Contextual Logging

Always include contextual information:

```python
logger.info(f"Intent classified: {intent} conf={confidence} session={session_id}")
logger.error(f"Ollama request failed: {error} model={model} session={session_id}")
```

## Log Aggregation

Docker container logs are collected by Promtail and shipped to Loki on the Gateway node. Query logs in Grafana with LogQL.

## Related

- [Architecture: Observability](../architecture/observability.md) — logging stack
- [Admin: Monitoring](../admin-guide/operations/monitoring.md) — log querying
