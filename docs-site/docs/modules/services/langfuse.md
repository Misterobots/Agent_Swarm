---
title: "Service: Langfuse"
---

# Langfuse

LLM observability and tracing service.

## Deployment

| Property | Value |
|----------|-------|
| **Node** | Control Plane ({{ hopper_ip }}) |
| **Port** | 3000 |
| **URL** | `http://{{ hopper_ip }}:3000` |
| **Backend** | ClickHouse + PostgreSQL |
| **Compose** | `control_plane/docker-compose.yml` |

## Purpose

Langfuse captures end-to-end traces for every LLM interaction in Memex:

- **Traces**: One per user request
- **Spans**: Solver, Verifier, Corrector steps
- **Scores**: Process-reward scores (0.01.0)
- **Generations**: Individual LLM calls with tokens/latency
- **Metadata**: Intent, model, template version

## Integration

The Agent Runtime uses the Langfuse Python SDK:

```python
from langfuse import Langfuse

lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
)

trace = lf.trace(name="chat_request", session_id=session_id)
span = trace.span(name="solver")
# ... generation ...
span.end()
trace.score(name="verification", value=0.85)
```

## Configuration

| Variable | Description |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | API public key |
| `LANGFUSE_SECRET_KEY` | API secret key |
| `LANGFUSE_HOST` | Service URL |

## Related

- [Architecture: Observability](../../architecture/observability.md)
- [Admin: Monitoring](../../admin-guide/operations/monitoring.md)


