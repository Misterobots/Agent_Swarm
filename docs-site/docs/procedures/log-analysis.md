---
title: "Procedure: Log Analysis"
---

# Log Analysis

Query and analyze logs using Loki and Grafana.

## Accessing Logs

Open Grafana at `http://{{ gateway_node_ip }}:3001`, select the **Loki** data source, and use the **Explore** tab.

## Common LogQL Queries

### All Errors

```logql
{container_name="agent-runtime"} |= "ERROR"
```

### Intent Classification

```logql
{container_name="agent-runtime"} |= "Intent classified"
```

### MarsRL Failures

```logql
{container_name="agent-runtime"} |= "Verifier" |= "FAIL"
```

### Ollama Errors

```logql
{container_name=~"ollama.*"} | json | level="error"
```

### Specific Session

```logql
{container_name="agent-runtime"} |= "session=abc123"
```

## Tips

- Use time range filters to narrow results
- Pipe through `| json` for structured log parsing
- Use `| line_format` for custom output formatting
- Export results for offline analysis
