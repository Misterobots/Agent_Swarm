---
title: Research Mode
---

# Research Mode

Multi-source research synthesis for deep knowledge queries.

## How to Access

- **Chat**: Set `research_mode: true` in the API, or ask questions the router classifies as `RESEARCH`
- **Chat (implicit)**: Ask complex multi-faceted questions — *"Compare the advantages of PostgreSQL vs MongoDB for time-series data"*

## Quick Example

> *"Research the current state of SPIFFE adoption in production Kubernetes environments"*

The system engages the Coordinator to:

1. Decompose the topic into subtasks
2. Assign research workers to each subtask
3. Synthesize findings into a coherent report

## Detailed Usage

### How Research Mode Works

```mermaid
graph TD
    A[Research Query] --> B[Coordinator: Decompose]
    B --> C1[Worker 1: SPIFFE overview]
    B --> C2[Worker 2: Kubernetes adoption]
    B --> C3[Worker 3: Production case studies]
    C1 --> D[Coordinator: Synthesize]
    C2 --> D
    C3 --> D
    D --> E[Final Report]
```

### Coordination Phases

| Phase | Description |
|-------|-------------|
| **Decompose** | Break the query into 2–5 focused subtasks |
| **Research** | Parallel workers investigate each subtask |
| **Synthesize** | Merge findings, resolve contradictions, structure the report |
| **Verify** | Fresh worker validates accuracy and completeness |

### When Research Mode Activates

The router classifies these as `RESEARCH`:

- Academic or historical analysis requests
- Comparative evaluations
- Multi-faceted technical questions
- Requests explicitly asking for "research" or "deep dive"

## Tips & Common Patterns

!!! tip "Scope Your Query"
    Narrower queries produce better results. *"Compare React hooks vs Vue composition API for state management"* beats *"Compare frontend frameworks"*.

!!! note "No Internet"
    Research mode synthesizes from the model's training data and any available local documents. It does not search the internet.

## Related

- [Module: Coordinator](../modules/coordinator.md) — multi-worker orchestration details
- [Architecture: Agent System](../architecture/agent-system.md) — how agents collaborate
