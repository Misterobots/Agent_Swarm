# Memex — Pioneer Naming Glossary

> **Naming scheme adopted:** April 20, 2026 · **Scoped:** April 22, 2026  
> Pioneer names apply to the **4 physical nodes** and **externally-facing services** only.  
> Internal infrastructure services use their canonical tool names.

---

## Nodes (Physical Machines) — Pioneer Names

| Pioneer | Role | IP | Env Var | Former Name |
|---|---|---|---|---|
| **Turing** | Gateway · Monitoring · Reverse Proxy | 192.168.2.103 | `TURING_IP` | R730 |
| **Lovelace** | Compute · GPU · AI Inference | 192.168.2.101 | `LOVELACE_IP` | Justin-PC |
| **Hopper** | Control Plane · Orchestration | 192.168.2.102 | `HOPPER_IP` | Wyse 5070 / Controle Node |
| **BMO** | Voice · IoT · Edge | 192.168.2.106 | `BMO_IP` | Pi / Shannon |

---

## Services (Docker Compose Names)

### Turing (Gateway/Monitoring)

#### Externally-Facing — Pioneer Names
| Container | Tool | Purpose |
|---|---|---|
| `babbage` | Traefik | Reverse proxy / TLS termination (managed by Saltbox) |
| `hollerith` | Grafana | Metrics visualization |
| `hive-ui` | Hive UI (Next.js) | Memex unified interface |

#### Internal — Tool Names
| Container | Tool | Purpose |
|---|---|---|
| `prometheus` | Prometheus | Metrics collection |
| `loki` | Loki | Log aggregation |
| `ollama` | Ollama (gateway) | LLM request routing (Turing GPU) |
| `spire-agent` | SPIRE agent | Identity attestation |
| `redis` | Redis | Message bus / cache |

### Lovelace (Compute/GPU) — Tool Names
| Container | Tool | Purpose |
|---|---|---|
| `ollama` | Ollama (compute) | GPU-backed LLM inference |
| `comfyui` | ComfyUI | Image/video generation |
| `openhands` | OpenHands | AI coding agent |

### Hopper (Control Plane) — Tool Names
| Container | Tool | Purpose |
|---|---|---|
| `spire-server` | SPIRE server | SPIFFE identity authority |
| `langfuse-web` | Langfuse | LLM observability/tracing |
| `mempalace` | MemPalace | Vector memory store |
| `postgres` | PostgreSQL | Relational database |
| `minio` | MinIO | Object storage |
| `redis` | Redis | Message bus / cache |

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
| Physical nodes | Pioneer name only | "deploy to Turing", "SSH into Lovelace" |
| Externally-facing services | Pioneer name | `hollerith` (Grafana), `babbage` (Traefik) |
| Internal infrastructure | Tool / product name | `prometheus`, `loki`, `redis`, `postgres` |
| Named AI projects | Project name | MemPalace, ComfyUI, OpenHands |
| Env vars | Pioneer prefix for nodes | `TURING_IP`, `HOPPER_IP` |

---

## Quick Reference — Former Names

| Old Name | Current Name | Type |
|---|---|---|
| R730 | Turing | Node |
| Justin-PC | Lovelace | Node |
| Wyse 5070 / Controle Node | Hopper | Node |
| Pi | BMO | Node |
| r730_gateway/ | turing_gateway/ | Directory |
| babbage | babbage | Container (Traefik — kept, external) |
| hollerith | hollerith | Container (Grafana — kept, external) |
| jacquard | prometheus | Container |
| knuth | loki | Container |
| ritchie | redis | Container |
| mccarthy | ollama | Container |
| minsky | ollama | Container |
| wozniak | comfyui | Container |
| engelbart | openhands | Container |
| diffie / diffie-agent | spire-server / spire-agent | Container |
| floyd-web / floyd-worker | langfuse-web / langfuse-worker | Container |
| bush | mempalace | Container |
| codd | postgres | Container |
| backus | minio | Container |
| router.py / herald.py | church.py | Agent |
| architect_agent.py / kepler_agent.py | leibniz_agent.py | Agent |
| coordinator.py / orbital.py | lamport.py | Agent |
| corrector_agent.py / rectus_agent.py | dijkstra_agent.py | Agent |
| governance.py / aegis.py | liskov.py | Agent |
| context_manager.py / codex.py | brooks.py | Agent |
| buddy_service.py / aether_service.py | kay_service.py | Agent |
