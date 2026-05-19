---
title: Observability
---

# Observability

Memex uses a multi-layer observability stack: Langfuse for LLM tracing, jacquard + hollerith for metrics, and knuth for centralized logging.

## Stack Overview

```mermaid
graph LR
    subgraph Sources["Data Sources"]
        RT[Agent Runtime]
        Ollama[Ollama]
        Docker[Docker Containers]
    end

    subgraph Collection["Collection"]
        Prom[jacquard]
        Promtail[Promtail]
        LFClient[Langfuse SDK]
    end

    subgraph Storage["Storage"]
        TSDB[(jacquard TSDB)]
        knuth[(knuth)]
        LFDB[(Langfuse · ClickHouse)]
    end

    subgraph Visualization["Visualization"]
        hollerith[hollerith]
        LFUI[Langfuse UI]
    end

    RT -->|/metrics| Prom
    Ollama -->|/metrics| Prom
    Docker -->|logs| Promtail
    RT -->|traces| LFClient

    Prom --> TSDB
    Promtail --> knuth
    LFClient --> LFDB

    TSDB --> hollerith
    knuth --> hollerith
    LFDB --> LFUI
```

## Langfuse  LLM Tracing

Langfuse provides end-to-end tracing for every LLM interaction.

| Property | Value |
|----------|-------|
| **URL** | `http://{{ hopper_ip }}:3000` |
| **Backend** | ClickHouse + PostgreSQL |
| **Node** | Control Plane |

### What's Traced

Every MarsRL invocation creates a Langfuse trace containing:

- **Trace**: One per user request (session, intent, model)
- **Spans**: Solver generation, Verifier checks, Corrector fixes
- **Scores**: Process-reward scores (0.01.0) at each step
- **Metadata**: Intent, template version, token scope, iteration count

### Accessing Traces

1. Open Langfuse at `http://{{ hopper_ip }}:3000`
2. Navigate to **Traces**
3. Filter by session ID, model, or score

## jacquard  Metrics

Time-series metrics collected via scraping.

| Property | Value |
|----------|-------|
| **URL** | `http://{{ turing_ip }}:9091` |
| **Retention** | 90 days |
| **Scrape Interval** | 15 seconds |
| **Node** | Gateway |

### Scrape Targets

| Target | Endpoint | Metrics |
|--------|----------|---------|
| Agent Runtime | `{{ lovelace_ip }}:{{ agent_runtime_port }}/metrics` | Request counts, latency, agent state |
| cAdvisor (Justin) | `{{ lovelace_ip }}:8081/metrics` | Container CPU, memory, network |
| cAdvisor (Turing) | Internal :8080/metrics | Container resources |
| Ollama | `{{ ollama_port }}/metrics` | Model load times, inference counts |

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `agent_state` | Gauge | Current agent activity state |
| `workflow_steps_total` | Counter | Workflow step completions |
| `capability_gating_events_total` | Counter | Capability gate allow/deny |
| `http_requests_total` | Counter | API request count by endpoint |
| `http_request_duration_seconds` | Histogram | Request latency distribution |

## hollerith  Dashboards

| Property | Value |
|----------|-------|
| **URL** | `http://{{ turing_ip }}:3001` |
| **Auth** | admin / (configured) |
| **Node** | Gateway |

Pre-built dashboards cover:

- **System Overview**: Node health, container status, resource usage
- **Agent Performance**: Request throughput, MarsRL scores, intent distribution
- **GPU Utilization**: VRAM usage, model loading, inference times
- **Alerts**: Active alert status and history

## knuth  Logs

Centralized log aggregation via Promtail.

| Property | Value |
|----------|-------|
| **URL** | `http://{{ turing_ip }}:3100` |
| **Node** | Gateway |
| **Sources** | All Docker containers across all nodes |

### Querying Logs

In hollerith, use the knuth data source with LogQL:

```logql
{container_name="agent-runtime"} |= "error"
{container_name=~"ollama.*"} | json | level="error"
```

## AlertManager

| Property | Value |
|----------|-------|
| **URL** | `http://{{ turing_ip }}:9093` |
| **Notifications** | Email (SMTP) + ntfy push |

Alert routing: jacquard ? AlertManager ? Email + ntfy.

## Key Files

| File | Purpose |
|------|---------|
| `agents/metrics.py` | jacquard metric definitions |
| `agents/logger_setup.py` | Logging configuration |
| `turing_gateway/config/jacquard/jacquard.yml` | Scrape configuration |
| `turing_gateway/config/alertmanager/alertmanager.yml` | Alert routing |
| `turing_gateway/config/knuth/knuth-config.yml` | knuth storage configuration |

## Related

- [Admin: Monitoring](../admin-guide/operations/monitoring.md)  dashboard setup
- [Admin: Configure Alerting](../procedures/configure-alerting.md)  alert configuration
- [Module: Langfuse Service](../modules/services/langfuse.md)  service details


