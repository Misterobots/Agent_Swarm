---
title: "ADR-002: Local Hook Execution Model"
---

# ADR-002: Local Hook Execution Model

**Status**: Accepted  
**Date**: 2025-12

## Context

Agent Swarm runs across three physical nodes. Code execution (sandboxed environments, ComfyUI workflows, voice synthesis) must run on nodes with GPUs. The system needs a model for how and where tasks execute.

Two approaches were considered:

1. **Cloud-like orchestrator**: A centralized scheduler dispatches work to any node (like Kubernetes)
2. **Local hook model**: Each node runs its own services; routing is handled by the reverse proxy

## Decision

Adopt a **local hook execution model** where each node is responsible for its own workloads, and Traefik handles routing.

- **Execution Node** (Lovelace): All GPU compute — Ollama, ComfyUI, Voice Engine, Agent Runtime
- **Control Node** (Hopper): All coordination — SPIRE, databases, Langfuse, MemPalace
- **Gateway Node** (Turing): All ingress — Traefik, monitoring stack, secondary Ollama

Services are started via Docker Compose on each node. Inter-node communication uses direct HTTP over the LAN.

## Consequences

### Positive

- **Simplicity**: No orchestrator to manage (no Kubernetes, Nomad, or Swarm)
- **Predictable placement**: GPU workloads always run where the GPU is
- **Low overhead**: No scheduling delay, no container migration
- **Easy debugging**: Services are always on the same node; logs are in one place
- **Offline capable**: Each node can function independently if others are down

### Negative

- **No auto-failover**: If the Execution Node goes down, GPU workloads stop
- **Manual scaling**: Adding capacity requires manual docker-compose changes
- **No load balancing**: Single node bottleneck for GPU work (mitigated by queue limits)
- **Tight coupling**: Services know their node's IP addresses

## Related

- [Architecture: Topology](../topology.md) — physical node layout
- [Admin: Deployment](../../admin-guide/index.md) — per-node setup


