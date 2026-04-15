---
title: Internal API
---

# Internal API

Health, metrics, and debugging endpoints.

## Health Check

```
GET /
```

```json
{
    "status": "ok",
    "version": "1.0.0",
    "uptime": 86400
}
```

## Metrics (Prometheus)

```
GET /metrics
```

Returns Prometheus-formatted metrics:

```
# HELP agent_state Current agent state
# TYPE agent_state gauge
agent_state{state="idle"} 1

# HELP workflow_steps_total Total workflow steps
# TYPE workflow_steps_total counter
workflow_steps_total{step="solver"} 1234

# HELP http_request_duration_seconds Request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.5"} 2000
```

## Logging

```
POST /log
```

Submit a log event:

```json
{
    "level": "info",
    "message": "Custom event",
    "metadata": {"source": "external"}
}
```

## Debug Endpoints

!!! warning "Debug Only"
    These endpoints are intended for development and should be restricted in production.

### Config Dump

```
GET /debug/config
```

Returns current runtime configuration (secrets redacted).

### Active Sessions

```
GET /debug/sessions
```

Lists active conversation sessions with metadata.

### Model Status

```
GET /debug/models
```

Returns loaded model information from Ollama, including VRAM usage.
