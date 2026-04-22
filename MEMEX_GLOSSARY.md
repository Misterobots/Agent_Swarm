# Memex — Pioneer Naming Glossary

> **Naming scheme adopted:** April 20, 2026  
> All infrastructure components use names from Computing Pioneers. Named projects (MemPalace, ComfyUI, etc.) retain their original names with the Pioneer container name as a parenthetical reference.

---

## Nodes (Physical Machines)

| Pioneer | Role | IP | Env Var | Former Name |
|---|---|---|---|---|
| **Turing** | Gateway · Monitoring · Reverse Proxy | 192.168.2.103 | `TURING_IP` | R730 |
| **Lovelace** | Compute · GPU · AI Inference | 192.168.2.101 | `LOVELACE_IP` | Justin-PC |
| **Hopper** | Control Plane · Orchestration | 192.168.2.102 | `HOPPER_IP` | Wyse 5070 / Controle Node |
| **BMO** | Voice · IoT · Edge | 192.168.2.106 | `BMO_IP` | Pi / BMO (name retained) |

---

## Services (Docker Compose Names)

### Turing (Gateway/Monitoring)
| Container | Tool | Purpose |
|---|---|---|
| `babbage` | Traefik | Reverse proxy / TLS termination |
| `jacquard` | Prometheus | Metrics collection |
| `hollerith` | Grafana | Metrics visualization |
| `knuth` | Loki | Log aggregation |
| `mccarthy` | Ollama (gateway) | LLM request routing |
| `diffie` | SPIRE agent | Identity attestation |

### Lovelace (Compute/GPU)
| Container | Tool | Purpose |
|---|---|---|
| `minsky` | Ollama (compute) | GPU-backed LLM inference |
| `wozniak` | ComfyUI | Image/video generation |
| `engelbart` | OpenHands | AI coding agent |

### Hopper (Control Plane)
| Container | Tool | Purpose |
|---|---|---|
| `diffie` | SPIRE server | SPIFFE identity authority |
| `floyd` | Langfuse | LLM observability/tracing |
| `bush` | MemPalace | Vector memory store |
| `codd` | PostgreSQL | Relational database |
| `backus` | MinIO | Object storage |

### Shared
| Container | Tool | Purpose |
|---|---|---|
| `ritchie` | Redis | Message bus / cache |

---

## Agents (Python Modules)

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

## Naming Policy

| Category | Rule | Example |
|---|---|---|
| Generic infrastructure | Use Pioneer container name only | "check `jacquard` metrics" |
| Named projects / addons | Original name + Pioneer ref in parens | "MemPalace (`bush`)", "ComfyUI (`wozniak`)" |
| Physical nodes | Pioneer name only | "deploy to Turing", "SSH into Lovelace" |
| Env vars | Pioneer prefix | `TURING_IP`, `HOPPER_IP` |

---

## Quick Reference — Former Names

| Old Name | New Name | Type |
|---|---|---|
| R730 | Turing | Node |
| Justin-PC | Lovelace | Node |
| Wyse 5070 / Controle Node | Hopper | Node |
| Pi / BMO | BMO (name retained) | Node |
| r730_gateway/ | turing_gateway/ | Directory |
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
| architect_agent.py / kepler_agent.py | leibniz_agent.py | Agent |
| coordinator.py / orbital.py | lamport.py | Agent |
| corrector_agent.py / rectus_agent.py | dijkstra_agent.py | Agent |
| governance.py / aegis.py | liskov.py | Agent |
| context_manager.py / codex.py | brooks.py | Agent |
| buddy_service.py / aether_service.py | kay_service.py | Agent |
