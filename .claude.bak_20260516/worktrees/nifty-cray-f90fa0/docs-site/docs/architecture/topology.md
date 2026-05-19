---
title: Topology
---

# Topology

Memex runs across three physical nodes on a flat LAN (192.168.2.0/24).

## Physical Layout

```mermaid
graph LR
    subgraph LAN["Local Network · 192.168.2.0/24"]
        HA["Home Assistant<br/>192.168.2.100"]
        Exec["Lovelace<br/>192.168.2.101<br/>RTX 5060 Ti 16GB"]
        Ctrl["Hopper<br/>192.168.2.102<br/>Low-power x86"]
        GW["Turing<br/>192.168.2.103<br/>RTX 3070 Ti 8GB"]
        iDRAC["iDRAC<br/>192.168.2.104"]
    end
```

## Node Specifications

### Execution Node  Lovelace ({{ lovelace_ip }})

| Spec | Value |
|------|-------|
| **Role** | GPU compute, primary inference, agent runtime |
| **OS** | Windows 11 (Docker Desktop) |
| **GPU** | NVIDIA RTX 5060 Ti 16GB VRAM |
| **RAM** | 32GB |
| **Services** | Ollama, Agent Runtime, ComfyUI, Voice Engine, BMO Voice, OpenHands |

### Control Node  Hopper ({{ hopper_ip }})

| Spec | Value |
|------|-------|
| **Role** | Identity, databases, observability, memory |
| **OS** | Ubuntu 22.04 |
| **GPU** | None |
| **RAM** | 8GB |
| **Services** | SPIRE Server, PostgreSQL (pgvector), Langfuse, ClickHouse, MemPalace, Redis, MinIO |

### Gateway Node  Dell PowerEdge Turing ({{ turing_ip }})

| Spec | Value |
|------|-------|
| **Role** | Reverse proxy, monitoring, secondary inference |
| **OS** | Ubuntu 22.04 |
| **GPU** | NVIDIA RTX 3070 Ti 8GB VRAM |
| **RAM** | 64GB |
| **Services** | Traefik, jacquard, hollerith, knuth, AlertManager, Ollama (secondary), Redis |

## Service Distribution

```mermaid
graph TB
    subgraph Execution["Execution Plane"]
        direction TB
        E1[SPIRE Agent]
        E2[Ollama · GPU]
        E3[Agent Runtime · FastAPI]
        E4[ComfyUI · GPU]
        E5[Voice Engine · GPU]
        E6[BMO Voice · GPU]
        E7[OpenHands · DinD]
        E8[Dev Sandbox]
    end

    subgraph Control["Control Plane"]
        direction TB
        C1[SPIRE Server]
        C2[PostgreSQL · pgvector]
        C3[Langfuse]
        C4[ClickHouse]
        C5[MemPalace]
        C6[MinIO]
        C7[Redis]
    end

    subgraph Gateway["Gateway"]
        direction TB
        G1[SPIRE Agent]
        G2[Traefik]
        G3[jacquard]
        G4[hollerith]
        G5[knuth + Promtail]
        G6[AlertManager]
        G7[Ollama Secondary]
        G8[Redis]
    end
```

## Network Communication

All inter-node traffic flows over the LAN. Key communication paths:

| Source | Destination | Protocol | Purpose |
|--------|-------------|----------|---------|
| Gateway ? Execution | HTTP :{{ agent_runtime_port }} | Agent Runtime API |
| Execution ? Control | TCP :8081 | SPIRE identity attestation |
| Execution ? Control | HTTP :3000 | Langfuse trace submission |
| Execution ? Control | TCP :5432 | PostgreSQL queries |
| Execution ? Control | HTTP :8200 | MemPalace memory API |
| Gateway ? Execution | HTTP :{{ ollama_port }} | Ollama inference (if cross-node) |
| jacquard ? Execution | HTTP :{{ agent_runtime_port }} | Metrics scraping |
| Promtail ? knuth | HTTP :3100 | Log shipping |

## Related

- [Data Flow](data-flow.md)  how a request travels through the topology
- [Admin: Networking](../admin-guide/deployment/networking.md)  firewall rules and DNS
- [Reference: Port Map](../admin-guide/port-map.md)  complete port registry


