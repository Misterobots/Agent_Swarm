---
title: Naming Scheme
---

# Pioneer Naming Scheme

All infrastructure components use names from Computing Pioneers. Named projects (MemPalace, ComfyUI, etc.) retain their original names; the Pioneer container name is used as the operational handle.

> **Adopted:** April 20, 2026

---

## Overview Map

```mermaid
graph TB
    subgraph NODES["🖥️ Physical Nodes"]
        T["<b>Turing</b><br/>192.168.2.103<br/><i>Gateway · Monitoring · Proxy</i><br/><small>formerly: R730</small>"]
        L["<b>Lovelace</b><br/>192.168.2.101<br/><i>Compute · GPU · AI Inference</i><br/><small>formerly: Justin-PC</small>"]
        H["<b>Hopper</b><br/>192.168.2.102<br/><i>Control Plane · Orchestration</i><br/><small>formerly: Wyse 5070</small>"]
        B["<b>BMO</b><br/>192.168.2.106<br/><i>Voice · IoT · Edge</i><br/><small>name retained</small>"]
    end

    subgraph TURING_SERVICES["Turing — Containers"]
        babbage["babbage<br/><small>Traefik</small>"]
        jacquard["jacquard<br/><small>Prometheus</small>"]
        hollerith["hollerith<br/><small>Grafana</small>"]
        knuth["knuth<br/><small>Loki</small>"]
        mccarthy["mccarthy<br/><small>Ollama gateway</small>"]
        diffie_t["diffie<br/><small>SPIRE agent</small>"]
    end

    subgraph LOVELACE_SERVICES["Lovelace — Containers"]
        minsky["minsky<br/><small>Ollama compute</small>"]
        wozniak["wozniak<br/><small>ComfyUI</small>"]
        engelbart["engelbart<br/><small>OpenHands</small>"]
    end

    subgraph HOPPER_SERVICES["Hopper — Containers"]
        diffie_h["diffie<br/><small>SPIRE server</small>"]
        floyd["floyd<br/><small>Langfuse</small>"]
        bush["bush<br/><small>MemPalace</small>"]
        codd["codd<br/><small>PostgreSQL</small>"]
        backus["backus<br/><small>MinIO</small>"]
        ritchie["ritchie<br/><small>Redis</small>"]
    end

    subgraph AGENTS["🤖 Agent Modules"]
        church["church.py<br/><small>Router · Alonzo Church</small>"]
        leibniz["leibniz_agent.py<br/><small>Architect · Leibniz</small>"]
        lamport["lamport.py<br/><small>Coordinator · Leslie Lamport</small>"]
        dijkstra["dijkstra_agent.py<br/><small>Corrector · Dijkstra</small>"]
        liskov["liskov.py<br/><small>Governance · Barbara Liskov</small>"]
        brooks["brooks.py<br/><small>Context Mgr · Fred Brooks</small>"]
        kay["kay_service.py<br/><small>Voice Bridge · Alan Kay</small>"]
    end

    T --> babbage & jacquard & hollerith & knuth & mccarthy & diffie_t
    L --> minsky & wozniak & engelbart
    H --> diffie_h & floyd & bush & codd & backus & ritchie

    style T fill:#4a2080,color:#fff,stroke:#8855cc
    style L fill:#1a5080,color:#fff,stroke:#3388cc
    style H fill:#1a6040,color:#fff,stroke:#33aa66
    style B fill:#804020,color:#fff,stroke:#cc7733
    style NODES fill:#1a1a2e,stroke:#444,color:#ccc
    style TURING_SERVICES fill:#2a1040,stroke:#6633aa,color:#ccc
    style LOVELACE_SERVICES fill:#0a2840,stroke:#2266aa,color:#ccc
    style HOPPER_SERVICES fill:#0a3020,stroke:#226644,color:#ccc
    style AGENTS fill:#2a1a0a,stroke:#aa6622,color:#ccc
```

---

## Nodes

| Pioneer | Former Name | Role | IP | Env Var |
|---------|-------------|------|-----|---------|
| **Turing** | R730 | Gateway · Monitoring · Reverse Proxy | `192.168.2.103` | `TURING_IP` |
| **Lovelace** | Justin-PC | Compute · GPU · AI Inference | `192.168.2.101` | `LOVELACE_IP` |
| **Hopper** | Wyse 5070 | Control Plane · Orchestration | `192.168.2.102` | `HOPPER_IP` |
| **BMO** | Pi / BMO | Voice · IoT · Edge | `192.168.2.106` | `BMO_IP` |

---

## Containers by Node

=== "Turing"

    | Pioneer Name | Tool | Purpose |
    |---|---|---|
    | `babbage` | Traefik | Reverse proxy / TLS termination |
    | `jacquard` | Prometheus | Metrics collection |
    | `hollerith` | Grafana | Metrics visualization |
    | `knuth` | Loki | Log aggregation |
    | `mccarthy` | Ollama (gateway) | LLM request routing |
    | `diffie` | SPIRE agent | Identity attestation |

=== "Lovelace"

    | Pioneer Name | Tool | Purpose |
    |---|---|---|
    | `minsky` | Ollama (compute) | GPU-backed LLM inference |
    | `wozniak` | ComfyUI | Image/video generation |
    | `engelbart` | OpenHands | AI coding agent |

=== "Hopper"

    | Pioneer Name | Tool | Purpose |
    |---|---|---|
    | `diffie` | SPIRE server | SPIFFE identity authority |
    | `floyd` | Langfuse | LLM observability/tracing |
    | `bush` | MemPalace | Vector memory store |
    | `codd` | PostgreSQL | Relational database |
    | `backus` | MinIO | Object storage |
    | `ritchie` | Redis | Message bus / cache |

---

## Agent Modules

```mermaid
graph LR
    subgraph PIPELINE["Request Pipeline"]
        church["⚡ church.py<br/><small>Router</small>"]
        leibniz["🗺️ leibniz_agent.py<br/><small>Architect</small>"]
        lamport["🔄 lamport.py<br/><small>Coordinator</small>"]
        dijkstra["✅ dijkstra_agent.py<br/><small>Corrector</small>"]
    end

    subgraph SUPPORT["Support Agents"]
        liskov["🛡️ liskov.py<br/><small>Governance</small>"]
        brooks["📚 brooks.py<br/><small>Context Mgr</small>"]
        kay["🎤 kay_service.py<br/><small>Voice Bridge</small>"]
    end

    church -->|plan| leibniz
    leibniz -->|coordinate| lamport
    lamport -->|verify| dijkstra
    church -.->|policy check| liskov
    church -.->|memory| brooks
    kay -.->|voice input| church

    style PIPELINE fill:#1a1a2e,stroke:#6644aa,color:#ccc
    style SUPPORT fill:#1a2a1a,stroke:#446644,color:#ccc
```

| File | Pioneer | Role |
|---|---|---|
| `agents/church.py` | Alonzo Church | Router — intent dispatch |
| `agents/leibniz_agent.py` | Gottfried Leibniz | Architect — task planning |
| `agents/lamport.py` | Leslie Lamport | Coordinator — multi-agent sync |
| `agents/dijkstra_agent.py` | Edsger Dijkstra | Corrector — output validation |
| `agents/liskov.py` | Barbara Liskov | Governance — policy enforcement |
| `agents/brooks.py` | Fred Brooks | Context Manager — memory window |
| `agents/kay_service.py` | Alan Kay | Kay Service — voice/UI bridge |

---

## Naming Rules

| Category | Rule | Example |
|---|---|---|
| Physical nodes | Pioneer name only | `deploy to Turing`, `SSH into Hopper` |
| Containers | Pioneer name only | `check jacquard metrics`, `restart bush` |
| Named projects | Original name + Pioneer ref | `MemPalace (bush)`, `ComfyUI (wozniak)` |
| Env vars | Pioneer prefix + `_IP` / `_HOST` | `HOPPER_IP`, `TURING_HOST` |
| Agent files | Pioneer last name | `church.py`, `liskov.py` |

---

## Former → Current Quick Reference

| Old Name | Pioneer Name | Type |
|---|---|---|
| R730 | Turing | Node |
| Justin-PC | Lovelace | Node |
| Wyse 5070 / Controle Node | Hopper | Node |
| Pi / BMO | BMO *(retained)* | Node |
| `r730_gateway/` | `turing_gateway/` | Directory |
| traefik | babbage | Container |
| prometheus | jacquard | Container |
| grafana | hollerith | Container |
| loki | knuth | Container |
| redis | ritchie | Container |
| ollama (gateway) | mccarthy | Container |
| ollama (compute) | minsky | Container |
| ComfyUI container | wozniak | Container |
| OpenHands container | engelbart | Container |
| SPIRE | diffie | Container |
| Langfuse | floyd | Container |
| MemPalace container | bush | Container |
| postgres container | codd | Container |
| minio container | backus | Container |
| router.py / herald.py | church.py | Agent |
| architect_agent.py | leibniz_agent.py | Agent |
| coordinator.py | lamport.py | Agent |
| corrector_agent.py | dijkstra_agent.py | Agent |
| governance.py / aegis.py | liskov.py | Agent |
| context_manager.py / codex.py | brooks.py | Agent |
| buddy_service.py | kay_service.py | Agent |
