---
title: Architecture
---

# Architecture

Technical design documentation for the Agent Swarm system.

```mermaid
graph TB
    subgraph Gateway["Gateway Node · R730 · {{ gateway_node_ip }}"]
        Traefik[Traefik]
        Prometheus[Prometheus]
        Grafana[Grafana]
        Loki[Loki]
        OllamaGW[Ollama Secondary]
    end

    subgraph Execution["Execution Node · Justin-PC · {{ execution_node_ip }}"]
        Runtime[Agent Runtime]
        Ollama[Ollama Primary]
        ComfyUI[ComfyUI]
        VoiceEng[Voice Engine]
        OpenHands[OpenHands]
    end

    subgraph Control["Control Node · Wyse 5070 · {{ control_node_ip }}"]
        SPIRE[SPIRE Server]
        PG[(PostgreSQL)]
        Langfuse[Langfuse]
        CH[(ClickHouse)]
        MemPalace[MemPalace]
    end

    Traefik -->|/swarm/*| Runtime
    Runtime --> Ollama
    Runtime --> ComfyUI
    Runtime --> VoiceEng
    Runtime -.->|identity| SPIRE
    Runtime -.->|traces| Langfuse
    Runtime -.->|memory| MemPalace
    Prometheus -->|scrape| Runtime
    Prometheus -->|scrape| OllamaGW
```

## Sections

| Section | Description |
|---------|-------------|
| [Topology](topology.md) | Physical 3-node layout, hardware, network |
| [Data Flow](data-flow.md) | Request lifecycle from user input to response |
| [MarsRL Loop](marsrl.md) | Inference-time quality verification |
| [Security Model](security-model.md) | SPIFFE/SPIRE, JWT-ACE, MAESTRO |
| [Agent System](agent-system.md) | Agent roles, routing, intent classification |
| [Memory System](memory-system.md) | Persistent knowledge, preferences, MemPalace |
| [Observability](observability.md) | Prometheus, Grafana, Langfuse, Loki |
| [Architecture Decisions](decisions/index.md) | ADR index and records |
