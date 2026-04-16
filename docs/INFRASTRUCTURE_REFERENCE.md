# Home AI Lab Infrastructure Reference
**Last Updated**: March 15, 2026  
**Current Architecture Version**: 3.1 (Post-Phase 4 Distributed)  
**Maintenance Owner**: Engineering Team

---

## Executive Summary

The Home AI Lab operates a **three-tier distributed architecture** optimized for AI inference workloads with centralized observability:

| Tier | Host | Role | Hardware | Services |
|------|------|------|----------|----------|
| **Control** | Wyse 5070 (192.168.2.102) | Orchestration & Observability Backend | 16GB RAM, 512GB SSD | SPIRE, Langfuse, PostgreSQL, ClickHouse, MinIO |
| **Ops/Gateway** | Dell R730 (192.168.2.103) | Reverse Proxy & Monitoring | 384GB RAM, 24 CPU, 450GB SSD | Traefik, Prometheus, Grafana, Loki, cAdvisor, Redis |
| **Compute** | Justin-PC (192.168.2.101) | GPU Inference & Agent Runtime | 32GB RAM, RTX 5060 Ti (16GB), 500GB SSD | Ollama, ComfyUI, Agent Runtime, Voice Services |

---

## Detailed Component Inventory

### TIER 1: CONTROL PLANE (192.168.2.102)

#### SPIRE (Service and Workload Identity Runtime Environment)
- **Role**: Zero-trust workload identity provider
- **Port**: 8081 (API), Unix socket for agents
- **Function**: Issues X.509 SVIDs to processes on Justin-PC and R730
- **Data Store**: PostgreSQL (workload entries, policy cache)
- **Health Check**: `spire-server healthcheck`
- **Integration**: Agent runtime uses SPIFFE_ENDPOINT_SOCKET for mTLS

#### Langfuse (LLM Operations & Analytics)
- **Role**: Process reward tracking for MarsRL loop
- **Port**: 3210 (HTTP API)
- **Function**: Traces agent execution, collects training data
- **Data Store**: PostgreSQL (traces, scores, metadata)
- **Integration**: Agent Runtime sends @observe decorators

#### PostgreSQL (Primary Data Store)
- **Version**: 12.4
- **Port**: 5432
- **Databases**: langfuse, authentik, spire, agno
- **Backup**: Daily snapshots to MinIO

#### ClickHouse (Time-Series Analytics)
- **Port**: 8123 (HTTP), 9000 (Native)
- **Retention**: 1 year
- **Use**: Long-term performance analysis

#### MinIO (Object Storage)
- **Port**: 9000 (S3 API), 9001 (Console)
- **Buckets**: models, comfyui-outputs, backups, training-data
- **Quota**: 1TB allocated

---

### TIER 2: OPS & GATEWAY (192.168.2.103 - R730)

#### Traefik v3.6 (Reverse Proxy)
- **Ports**: 80 (HTTP), 443 (HTTPS), 8082 (API)
- **Routing**: Routes /ai, /comfy, /ops, /code, /devops, etc.
- **Authentication**: Authentik middleware (forward auth)
- **TLS**: Auto-generated or externally provided

#### Prometheus (Metrics Collection)
- **Port**: 9091 (mapped from 9090)
- **Scrape Interval**: 15 seconds
- **Retention**: 15 days
- **Storage**: ~15-20GB
- **Targets**: cadvisor, ollama, comfyui, agent_runtime

#### Grafana (Dashboards)
- **Port**: 3002
- **Admin**: admin / admin (⚠️ CHANGE IMMEDIATELY)
- **Datasources**: Prometheus, Loki
- **Data**: PostgreSQL storage for config

#### Loki (Log Aggregation)
- **Port**: 3101 (mapped from 3100)
- **Backend**: Filesystem + boltdb-shipper
- **Storage**: 25-35GB allocated
- **Retention**: 720 hours (~30 days)
- **Ingestion**: 50MB/s limit

#### Promtail (Log Shipper)
- **Port**: 9081 (mapped from 9080)
- **Scrapes**: Docker logs, syslog
- **Delivery**: At-least-once to Loki

#### cAdvisor (Container Metrics)
- **Port**: 8889
- **Metrics**: CPU, memory, network, disk I/O per container
- **Scrape**: 1s interval (aggregated by Prometheus)

#### Redis (Cache & Queue)
- **Port**: 6379
- **Persistence**: RDB + AOF
- **Purpose**: Task queue, session cache

---

### TIER 3: COMPUTE (192.168.2.101 - JUSTIN-PC)

#### 15 Compute Services

| Service | Port | GPU | Purpose |
|---------|------|-----|---------|
| SPIRE Agent | socket | - | Workload identity |
| Ollama | 11434 | ✓ | LLM inference (7B, 3B models) |
| ComfyUI | 8188 | ✓ | Image generation (shared GPU) |
| BMO Voice | 8100 | ✓ | Voice conversion (RVC) |
| Voice Engine | 8020 | ✓ | Text-to-speech (Qwen3-TTS 1.7B) |
| OpenHands | 3000 | - | Code execution sandbox |
| Agent Runtime | 8008 | - | FastAPI backend (orchestrator) |
| Agent UI | 8501 | - | Streamlit web interface |
| Ops Portal | 8502 | - | Admin dashboard |
| VS Code (DevOps) | 8443 | - | Full workspace IDE |
| VS Code (Coding) | 8444 | - | Restricted sandbox IDE |
| Authentik Server | 9000 | - | SSO & identity |
| Authentik Worker | - | - | Background tasks |
| Authentik DB | - | - | User storage (PostgreSQL) |
| Authentik Redis | - | - | Session cache |

**GPU Memory Sharing**:
- RTX 5060 Ti: 16GB total
- Ollama: 512MB overhead + model (5-10GB typical)
- ComfyUI: 4-8GB typical
- Management: OLLAMA_KEEP_ALIVE=5m (auto-unload after idle)

---

## Network Architecture

### Subnet
```
192.168.2.0/24 - Home Lab Subnet
├── 192.168.2.101 - Justin-PC (Compute)
├── 192.168.2.102 - Wyse 5070 (Control)
└── 192.168.2.103 - R730 (Gateway/Monitoring)

Latency: <1ms (L2 segment)
```

### Routing
```
External Request
    ↓
R730 Traefik:80/443
    ├─ /ai → Justin-PC:8501 (Agent UI)
    ├─ /comfy → Justin-PC:8188 (ComfyUI)
    ├─ /ops → Justin-PC:8502 (Ops Portal)
    ├─ /prometheus → R730:9090 (Prometheus)
    ├─ /grafana → R730:3000 (Grafana)
    └─ ... (30+ routes)
```

---

## Data Flow Patterns

### User Request → Agent Execution
1. Client → R730 Traefik `/ai`
2. Traefik → Justin-PC:8501 (Agent UI)
3. UI submission → Agent Runtime:8000 `/api/v1/execute`
4. Agent Runtime:
   - Route via semantic_router (intent classification)
   - Select agent from registry (8 templates)
   - MarsRL: Solver → Verifier → Corrector
   - Call services (Ollama, ComfyUI, etc.)
5. Emit @observe decorators → Langfuse on Control Plane
6. Response → UI → Client

### Monitoring & Observability
```
Services (Ollama, ComfyUI, etc.)
    ↓ (metrics + logs)
Prometheus:9090 (scrapes 15s)
Promtail:9080 (ships logs → Loki)
    ↓
R730 Monitoring Stack
├─ Prometheus (time-series)
├─ Loki (logs)
└─ Grafana (visualization)
```

### Workload Identity (SPIRE)
```
Agent Runtime Process
    ↓
Queries /var/run/spire/agent.sock
    ↓
SPIRE Agent ←→ SPIRE Server (Control Plane)
    ↓
X.509 SVID issued (mTLS ready)
```

---

## Storage Architecture

### Justin-PC (500GB SSD)
- OS: 100GB
- Docker volumes: 50GB (models, services)
- ComfyUI output: 50GB
- Workspace: 80GB
- **Free**: 120GB (+ 50-75GB freed by Phase 4)

### R730 (450GB SSD)
- Prometheus: 15-20GB
- Loki: 25-35GB
- Grafana: 500MB
- Services: 10GB
- **Free**: 365GB

### Control Plane (512GB SSD)
- SPIRE: 2GB
- Langfuse: 10GB
- PostgreSQL: 30GB
- ClickHouse: 50GB
- MinIO: 80GB
- **Free**: 340GB

---

## Security Architecture (MAESTRO)

| Layer | Component | Function |
|-------|-----------|----------|
| L7 | SPIFFE (SVID) | Network identity verification |
| L6 | Governance.py | Request policy assessment |
| L4 | Llama-Guard-3:8b | Security policy scanning |
| L3 | Agent Registry | Static capability lists |
| L2 | Authentik | User authentication |
| L1 | Traefik TLS | Transport encryption |

---

## Performance Budgets

### Inference Latency
| Model | Latency | Throughput |
|-------|---------|-----------|
| Ollama 7B | 2-5s | 20-40 tk/s |
| Ollama 3B | 1-2s | 40-60 tk/s |
| ComfyUI SDXL | 30-60s | - |
| Voice Engine | 2-5s/30s | Real-time |
| BMO Voice | 5-10s/60s | Real-time |

### Resource Utilization Thresholds
| Resource | Current | Alert @ |
|----------|---------|---------|
| GPU VRAM | 10GB (idle) | **15GB** |
| Justin-PC CPU | 15-20% | **80%** |
| Justin-PC Disk | 350GB | **80%** |
| R730 CPU | Low | **80%** |
| R730 Disk | 70GB | **80%** |

---

## Configuration Locations

### Justin-PC
```
~/execution_plane/
├── docker-compose.yml
├── Dockerfile (Agent Runtime)
└── config/
    ├── spire/agent.conf
    └── authentik/
```

### R730
```
~/r730_gateway/
├── docker-compose-monitoring-fixed.yml
└── config/
    ├── prometheus/prometheus.yml
    ├── loki/loki.yml
    ├── promtail/promtail.yml
    └── provisioning/ (Grafana datasources)
```

---

## Operational Commands

### Health Checks
```bash
# Network
ping -c 2 192.168.2.101
ping -c 2 192.168.2.103

# Docker services
docker-compose ps
docker-compose -f docker-compose-monitoring-fixed.yml ps

# Service endpoints
curl http://192.168.2.101:8008/health
curl http://192.168.2.103:9091/-/healthy
curl http://192.168.2.103:3002/api/health
```

### Service Restart
```bash
# Single service
docker-compose restart ollama

# Full stack restart (Justin-PC)
docker-compose down && sleep 5 && docker-compose up -d

# Monitoring stack (R730)
docker-compose -f docker-compose-monitoring-fixed.yml restart
```

---

## Disaster Recovery

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| GPU driver crash | Ollama/ComfyUI fail | Restart services (2-5 min init) |
| Prometheus crash | Grafana can't query | Restart prometheus container |
| PostgreSQL corruption | Langfuse traces fail | Restore from backup, restart |
| Network partition | Services unreachable | Check cabling, verify IPs |

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Single GPU (16GB) | Queue concurrent requests | OLLAMA_NUM_PARALLEL=1, idle timeout |
| No k8s | Manual scaling | Full compose files for migration |
| Monitoring SPOF | Observability down | Backup configs, 15min redeploy |
| No distributed tracing | Hard to debug | Langfuse traces + agent_id linking |

---

## Glossary

- **SPIFFE**: Secure Production Identity Framework for Everyone
- **SVID**: SPIFFE Verifiable Identity Document (X.509)
- **MarsRL**: Mars RL loop (Solver → Verifier → Corrector)
- **ComfyUI**: Node-based image generation engine
- **Langfuse**: LLM analytics & observability platform
- **cAdvisor**: Container metrics collector
- **Traefik**: Cloud-native API gateway
- **Prometheus**: Time-series metrics database
- **Loki**: Log aggregation engine
- **Authentik**: Open-source identity provider

---

**Version**: 1.0 | **Architecture**: 3.1 (Post-Phase 4) | **Last Updated**: March 15, 2026

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `network.env` | Configuration | Node IPs, service ports |
| `execution_plane/docker-compose.yml` | Infrastructure | Justin-PC services |
| `control_plane/docker-compose.yml` | Infrastructure | Control Node services |
| `r730_gateway/docker-compose.yml` | Infrastructure | R730 gateway services |
| `config/grafana/` | Infrastructure | Prometheus rules, Grafana dashboards |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-15 | AI-Copilot | v1.0 — Full infrastructure reference (Post-Phase 4) |

</details>

---

## Maintenance & Update Guide

- Update when hardware changes (new memory, storage, GPUs).
- Update when new Docker services are added or ports change.
- Cross-reference `network.env` for IP consistency.

---

## Functionality Testing

| Check | Command |
|-------|--------|
| All nodes reachable | `ping 192.168.2.101 && ping 192.168.2.102 && ping 192.168.2.103` |
| Docker services | `docker ps --format 'table {{.Names}}\t{{.Status}}'` on each node |
| Prometheus targets | Grafana → Explore → `up` query |
