---
title: Architecture
---

# Architecture

Technical design documentation for the Memex system.

```mermaid
graph TB
    subgraph Gateway["Gateway Node · Turing · {{ turing_ip }}"]
        Traefik[Traefik]
        jacquard[jacquard]
        hollerith[hollerith]
        knuth[knuth]
        OllamaGW[Ollama Secondary]
    end

    subgraph Execution["Execution Node · Lovelace · {{ lovelace_ip }}"]
        Runtime[Agent Runtime]
        Ollama[Ollama Primary]
        ComfyUI[ComfyUI]
        VoiceEng[Voice Engine]
        OpenHands[OpenHands]
    end

    subgraph Control["Control Node · Hopper · {{ hopper_ip }}"]
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
    jacquard -->|scrape| Runtime
    jacquard -->|scrape| OllamaGW
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
| [Observability](observability.md) | jacquard, hollerith, Langfuse, knuth |
| [Architecture Decisions](decisions/index.md) | ADR index and records |

## System Philosophy

Memex's architecture is built around three principles:

1. **Specialization over generalization** - different tasks use purpose-built agents with the right model for the job. A routing model is fast and cheap; a coding model is deep and large. Neither substitutes for the other.
2. **Inference-time verification** - output quality is enforced at runtime, not post-hoc. The [MarsRL Loop](marsrl.md) prevents bad output from ever reaching the user.
3. **Locality and privacy** - all inference runs on-premises across the Lovelace/Hopper/Turing nodes (see [Topology](topology.md)). No external API calls for inference; training improves local models continuously from real usage data.


