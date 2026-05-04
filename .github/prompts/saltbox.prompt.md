---
name: saltbox
description: >
  Debug and troubleshoot Saltbox deployments, Docker containers, Traefik routing,
  and media stack services. Invokes the Saltbox Debug Agent to diagnose issues,
  check container health, analyze logs, verify security configurations, and optimize
  stack performance. Trigger phrases: /saltbox, debug saltbox, troubleshoot docker,
  fix traefik, check container health.
argument-hint: "Describe the issue or service to investigate (e.g., 'check traefik on Turing')"
---

You are invoking the **Saltbox Debug Agent** to troubleshoot infrastructure issues.

## What This Does

This prompt delegates to the Saltbox Debug Agent, which specializes in:
- **Container Health**: Checking status, resources, restart loops
- **Traefik Routing**: Debugging middleware, labels, certificates
- **Log Analysis**: Extracting errors, patterns, root causes
- **Security Validation**: Verifying Authentik middleware, port exposure
- **Performance Optimization**: Resource usage, volume mounts, limits

## Usage

Provide the issue description as the argument. Examples:

- `/saltbox check agent_runtime logs on Turing`
- `/saltbox why is hive_ui not accessible through Traefik?`
- `/saltbox verify all services have Authentik middleware`
- `/saltbox show resource usage on Turing`

## Invocation

Use the `runSubagent` tool to invoke the "Saltbox Debug Agent" with the user's input as the prompt.

```
runSubagent(
  agentName: "Saltbox Debug Agent",
  description: "Debug Saltbox infrastructure",
  prompt: "<user's issue description>"
)
```

The agent will gather context, run diagnostics, and provide structured findings with fixes.
