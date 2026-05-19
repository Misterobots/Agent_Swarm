# Admin Technical Reference

> **Back to:** [Documentation Index](../INDEX.md)
> **See also:** [Design Framework](design_framework.md) · [Security](security.md) · [Troubleshooting](troubleshooting.md)

## Canonical Inventory and Governance References

- [System Component and Service Catalog](../catalog/system_component_service_catalog.md)
- [Documentation Governance Standard](../governance/documentation_governance_standard.md)
- [Documentation Gap Register](../governance/documentation_gap_register.md)

**Last Updated**: 2026-05-04 · **Architecture Version**: 4.0

---

## 1. Network Topology

All IP addresses are managed in [`network.env`](../../network.env) — edit that file when IPs change.

| Node | IP | Role | Hardware |
|------|----|------|----------|
| Home Assistant | `<home-assistant-ip>` | Smart Home Hub | Dedicated HA device |
| **Execution Node** (Lovelace) | `192.168.2.101` | GPU Compute | Dual RTX 5060 Ti (32 GB VRAM), 32 GB RAM, 500 GB SSD |
| **Control Node** (Hopper) | `192.168.2.102` | Control Plane | x86 low-power, 16 GB RAM, 512 GB SSD |
| **Gateway Node** (Turing) | `192.168.2.103` | Gateway / Ops / Agent Runtime | **No GPU** (3070 Ti removed), 384 GB RAM, 40 CPU, 450 GB SSD |
| iDRAC | `192.168.2.104` | Gateway Remote Management | — |
| BMO | `192.168.2.106` | Voice/IoT Satellite | Raspberry Pi |

**Tailscale Remote Access**: Connect to `gateway-node.tail-xxxx.ts.net:80` for all services. Run `tailscale status` on any node for the current MagicDNS hostname.

---

## 2. User Interfaces

All UIs are accessible via the Gateway Node Traefik gateway (`http://<gateway-node-ip>`).

| Interface | URL | Hosted On | Purpose |
|-----------|-----|-----------|---------|
| Traefik Gateway | `http://<gateway-node-ip>:80` | Gateway Node | Central reverse proxy, primary entry point |
| Hive Mind UI | `http://<gateway-node-ip>` (root) | Gateway Node→Execution Node | Primary Streamlit chat + all workspaces |
| Open-WebUI | `http://<gateway-node-ip>:3000` | Gateway Node | Alternative OpenAI-compatible chat UI |
| Grafana | `http://<gateway-node-ip>:3001` | Gateway Node | Monitoring dashboards (metrics + logs) |
| Prometheus | `http://<gateway-node-ip>:9091` | Gateway Node | Metrics query interface |
| Loki | `http://<gateway-node-ip>:3100` | Gateway Node | Log aggregation backend |
| Traefik Dashboard | `http://<gateway-node-ip>:8080` | Gateway Node | Live routing and load balancer metrics |
| Langfuse | `http://<control-node-ip>:3000` | Control Node | LLM trace viewer, process reward scores |
| OpenHands | `http://<gateway-node-ip>:3002` | Gateway Node | Secure code execution sandbox |
| ComfyUI | `http://<gateway-node-ip>/comfy` | Gateway Node→Execution Node | Image/3D generation node editor |
| Authentik SSO | `http://<gateway-node-ip>:9000` | Gateway Node | Single Sign-On identity provider |
| VS Code (DevOps) | `http://<gateway-node-ip>:8445` | Gateway Node | Infrastructure workspace IDE |
| VS Code (Coding) | `http://<gateway-node-ip>:8444` | Gateway Node | Coding sandbox IDE |
| MinIO Console | `http://<control-node-ip>:9001` | Control Node | Object storage browser |

### Hive UI Split Backend Routing

The Next.js Hive UI uses a shared proxy route at `/api/backend/*`, but it does **not** send every request to the same upstream.

| Env Var | Upstream | Used For |
|---------|----------|----------|
| `API_BASE_URL` | `http://<execution-node-ip>:8008` | Agent Runtime APIs such as identity, chat, training, ops, and GitHub OAuth |
| `MEMPALACE_BASE_URL` | `http://<control-node-ip>:8200` | Palace Viewer and memory APIs such as `/v1/palace/*` and `/v1/memories/*` |

For Turing gateway deployment, `turing_gateway/docker-compose.yml` must set **both** environment variables on the `hive-ui` service. Without `MEMPALACE_BASE_URL`, the Palace Viewer loads the shell but cannot reach Palace layout or memory CRUD endpoints through the normal UI proxy.

---

## 3. API Endpoints

### Swarm Engine (via Gateway Node Traefik)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `http://<gateway-node-ip>/swarm/docs` | GET | Swagger UI — all FastAPI endpoints |
| `http://<gateway-node-ip>/swarm/v1/chat/completions` | POST | OpenAI-compatible endpoint (used by Open-WebUI, Continue) |
| `http://<gateway-node-ip>/swarm/v1/models` | GET | Returns `Home-AI-Swarm` model for UI dropdowns |
| `http://<gateway-node-ip>/swarm/task` | POST | Raw task submission: `{"prompt": "..."}` |
| `http://<gateway-node-ip>/swarm/voice/stream` | POST | BMO Voice PCM → TTS stream |
| `http://<gateway-node-ip>/swarm/api/v1/health/nodes` | GET | Node health status + loaded models |
| `http://<gateway-node-ip>/swarm/metrics/` | GET | Prometheus metrics endpoint |

**Direct access (bypass gateway)**: `http://<execution-node-ip>:8008/...`

### Local Inference Services

| Service | Endpoint | Node | Models |
|---------|----------|------|--------|
| Ollama (Primary) | `http://192.168.2.101:11434` | Execution Node (Lovelace) | `gemma4:31b` (20 GB), `qwen3.6:27b` (17.4 GB), `qwen2.5-coder:14b` (9 GB), `qwen3:8b` (5.2 GB), `llama3.2:3b` (2 GB), `nomic-embed-text` (274 MB) |
| Ollama (Gateway — CPU only) | `http://192.168.2.103:11434` | Gateway Node (Turing) | `nomic-embed-text`, `llama-guard-3:8b` — safety and embeddings only. No large models. |
| RVC Voice | `http://<execution-node-ip>:8100/infer` | Execution Node | BMO voice model |
| Qwen-TTS | `http://<execution-node-ip>:8020/tts` | Execution Node | Text-to-speech |
| ComfyUI API | `http://<execution-node-ip>:8188` | Execution Node | Image/3D generation (internal) |

### Open-WebUI / External Agent Connection Settings

```
Primary (via Gateway):
  API Base URL:   http://192.168.2.103/swarm/v1
  Model:          Home-AI-Swarm
  API Key:        sk-swarm
  Context Window: 128,000
  Max Tokens:     4,096

Direct (Execution Node bypass):
  API Base URL:   http://192.168.2.103:8008/v1

Raw Ollama (Execution Node):
  OLLAMA_BASE_URL: http://192.168.2.101:11434
  Primary Model:   gemma4:31b
  Fallback Model:  qwen3.6:27b
```

---

## 4. Service Inventory by Node

### Control Plane — Control Node (<control-node-ip>)

| Service | Port | Purpose | Compose File |
|---------|------|---------|--------------|
| SPIRE Server | 8081 (API) | Zero-trust workload identity | `control_plane/docker-compose.yml` |
| Langfuse | 3000 (UI), 3210 (API) | LLM tracing + process rewards | `control_plane/docker-compose.yml` |
| PostgreSQL | 5432 | Primary data store (langfuse, agno, spire, authentik) | `control_plane/docker-compose.yml` |
| ClickHouse | 8123, 9000 | Time-series analytics, long-term performance data | `control_plane/docker-compose.yml` |
| MinIO | 9000 (S3), 9001 (Console) | Object storage (models, outputs, backups, training data) | `control_plane/docker-compose.yml` |
| Redis | 6379 | GPU mutex (langfuse_redis_password), session cache | `control_plane/docker-compose.yml` |

### Ops/Gateway — Gateway Node (<gateway-node-ip>)

| Service | Port | Purpose | Compose File |
|---------|------|---------|--------------|
| Traefik v3.6 | 80, 443, 8082 | Reverse proxy + routing | `turing_gateway/docker-compose.yml` |
| Prometheus | 9091 (→9090) | Metrics collection (15s scrape, 90d retention) | `turing_gateway/docker-compose.yml` |
| Grafana | 3001 | Dashboards (Prometheus + Loki + PostgreSQL-Swarm) | `turing_gateway/docker-compose.yml` |
| Loki | 3100 | Log aggregation | `turing_gateway/docker-compose.yml` |
| Promtail | — | Log collector (Docker socket → Loki) | `turing_gateway/docker-compose.yml` |
| cAdvisor | 8888 (→8080) | Container resource metrics for Gateway Node | `turing_gateway/docker-compose.yml` |
| Authentik | 9000, 9443 | SSO identity provider | `turing_gateway/docker-compose.yml` |
| Ollama (Gateway) | 11434 | Secondary inference (nemotron, llama-guard) | `turing_gateway/docker-compose.yml` |
| Open-WebUI | 3000 | Chat UI connected to Swarm API | `turing_gateway/docker-compose.yml` |
| OpenHands | 3002 | Code execution sandbox | `turing_gateway/docker-compose.yml` |
| VS Code (DevOps) | 8445 | Infrastructure IDE | `turing_gateway/docker-compose.yml` |
| VS Code (Coding) | 8444 | Coding sandbox IDE | `turing_gateway/docker-compose.yml` |
| Hive UI (Next.js) | 3200 -> 3000 | Unified web UI with split proxy to Agent Runtime + MemPalace | `turing_gateway/docker-compose.yml` |
| SPIRE Agent (Gateway) | — (Unix socket) | Workload identity agent (pending enrollment) | `turing_gateway/docker-compose.yml` |

### Compute Node — Execution Node (<execution-node-ip>)

| Service | Container Name | Port | Purpose | Compose File |
|---------|----------------|------|---------|--------------|
| Agent Runtime | `agent_runtime` | 8008 | FastAPI swarm engine (MarsRL loop) | `execution_plane/docker-compose.yml` |
| Ollama | `ollama_gpu` | 11434 | Primary GPU inference (`qwen3.5:9b`) | `execution_plane/docker-compose.yml` |
| ComfyUI | `comfyui_gpu` | 8188 | Image/3D generation | `execution_plane/docker-compose.yml` |
| BMO Voice | `bmo_voice_gpu` | 8100 | RVC voice reconstruction | `execution_plane/docker-compose.yml` |
| Voice Engine | `voice_engine_gpu` | 8020 | Qwen-TTS text-to-speech | `execution_plane/docker-compose.yml` |
| cAdvisor | `cadvisor_gpu_node` | 8080 | Container metrics (internal) | `execution_plane/docker-compose.yml` |
| cAdvisor Proxy | `cadvisor_proxy` | 8081 | Injects container names into metrics | `execution_plane/docker-compose.yml` |
| SPIRE Agent | `spire-agent` | Unix socket | Workload identity agent | `execution_plane/docker-compose.yml` |
| Training Runtime | `training_runtime` | — | QLoRA GRPO training (profile-gated) | `execution_plane/docker-compose.yml` |

---

## 5. Prometheus Scrape Targets

Configured in `turing_gateway/config/prometheus/prometheus.yml`:

| Job Name | Target | Metrics |
|----------|--------|---------|
| `cadvisor-turing` | `cadvisor-turing:8080` | Gateway Node container CPU/memory/net/disk |
| `cadvisor-justin` | `<execution-node-ip>:8081` | Execution Node container metrics (via proxy, with name labels) |
| `agent-runtime` | `<execution-node-ip>:8008/metrics/` | Agent state, workflow steps, latency, training metrics |
| `ollama-justin` | `<execution-node-ip>:11434/metrics` | Ollama request rate/latency (requires `OLLAMA_METRICS=1`) |

### Custom Agent Runtime Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `agent_state` | Gauge | `agent_name` | 0=Offline, 1=Idle, 2=Working, 3=Error |
| `workflow_steps_total` | Counter | `status`, `agent_type` | Total workflow steps by result |
| `agent_operation_seconds` | Histogram | `agent_name`, `operation_type` | Operation latency |
| `training_runs_total` | Counter | `run_type`, `status` | Training pipeline executions |
| `training_dataset_size` | Gauge | `dataset_type` | Dataset size in trajectories |
| `model_version_active` | Gauge | `template_id`, `model_name`, `version_tag` | Active model version flag |
| `ab_test_score` | Gauge | `test_id`, `arm` | A/B test running average |
| `mars_loop_final_score` | Histogram | `intent`, `template_id` | MarsRL quality score distribution |

---

## 6. Grafana Dashboards

Access: `http://<gateway-node-ip>:3001`
Datasource UIDs: `Prometheus`, `Loki`, `PostgreSQL-Swarm`

| Dashboard | UID | Datasources | Purpose |
|-----------|-----|-------------|---------|
| Agent Activity & Conversations | `agent-activity` | Prometheus + PostgreSQL-Swarm + Loki | Live agent states, conversation quality, MarsRL thought process, training |
| GPU & Inference | `gpu-inference` | Prometheus + Loki | Ollama request rates, GPU container resources, MarsRL log stream |
| Training Pipeline | `training-pipeline` | PostgreSQL-Swarm + Prometheus + Loki | Training runs, dataset growth, model versions, A/B tests |
| Template Performance | `template-performance` | PostgreSQL-Swarm + Prometheus | Score trends, invocation volume, corrector rate, latency |
| Mission Control | `mission-control` | Prometheus + Loki | Swarm-level CPU/memory, workflow velocity, live agent stream |
| Infrastructure Overview | `infrastructure-overview` | Prometheus + Loki | Container resources across all nodes, error/warning streams |
| System Overview | `system-overview` | Prometheus + Loki | Basic container metrics and agent errors |

---

## 7. PostgreSQL — Swarm Schema

Database: `langfuse` (on Control Node:5432, user: `langfuse`)
Schema prefix: `swarm.*`

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `swarm.expertise_templates` | `id`, `intent`, `default_model`, `current_version`, `security_level` | Versioned agent persona definitions |
| `swarm.expertise_template_versions` | `template_id`, `version`, `avg_score`, `total_invocations` | Per-version performance history |
| `swarm.performance_history` | `template_id`, `trace_id`, `intent`, `solver_score`, `verifier_score`, `final_score`, `corrector_invoked`, `latency_ms`, `recorded_at` | Per-request quality tracking |
| `swarm.training_runs` | `id`, `run_type`, `status`, `dataset_size`, `metrics` (JSONB), `started_at`, `completed_at` | Training pipeline execution log |
| `swarm.model_versions` | `id`, `base_model`, `version_tag`, `adapter_path`, `gguf_path`, `status`, `avg_score` | Model lifecycle registry |
| `swarm.ab_tests` | `id`, `template_id`, `candidate_model`, `base_model`, `traffic_split`, `status`, `winner` | A/B test definitions |
| `swarm.ab_test_results` | `test_id`, `model_used`, `score`, `latency_ms`, `recorded_at` | Per-invocation A/B results |

---

## 8. Training Pipeline

The training pipeline runs as a Docker profile-gated service on Execution Node. It is NOT always running.

```bash
# Build training container (first time or after code changes)
cd execution_plane
docker compose --profile training build training-runtime

# Step 1: Export high-quality traces from Langfuse (score ≥ 0.8)
docker compose --profile training run --rm training-runtime \
  python -m agents.training.export_traces

# Step 2: Generate synthetic training data (optional, augment small datasets)
docker compose --profile training run --rm training-runtime \
  python -m agents.training.synthetic_gen --target_count=50

# Step 3: Run QLoRA GRPO fine-tuning (~12.5GB VRAM, 2–4 hours)
# WARNING: Evicts Ollama and ComfyUI from VRAM via GPU mutex
docker compose --profile training run --rm training-runtime \
  python -m agents.training.grpo_trainer \
  --dataset /workspace/training_data/traces.jsonl

# Step 4: Convert LoRA → GGUF → load into Ollama
docker compose --profile training run --rm training-runtime \
  python -m agents.training.convert_gguf \
  --adapter /workspace/training_output/grpo_<TIMESTAMP>/adapter

# A/B testing begins automatically after model import
```

**Training schedule**: Recommended during the 02:00–06:00 idle window to avoid VRAM conflicts with active inference.

**Output directories** (Execution Node):
- Training data: `execution_plane/training_data/`
- Adapters + GGUF: `execution_plane/training_output/`

---

## 9. Loki Log Labels

Promtail labels Docker container logs with:
- `container` — container name (e.g., `agent_runtime`, `ollama_gpu`)
- `service` — Docker Compose service name
- `logstream` — `stdout` or `stderr`

**Important**: All Loki queries must use `{container="..."}` not `{container_name="..."}`.

Example queries:
```logql
# Live agent runtime (excluding metrics noise)
{container="agent_runtime"} != "/metrics"

# MarsRL thought process
{container="agent_runtime"} |~ "(?i)(mars|solver|verifier|corrector)"

# Errors across all containers
{container=~".+"} |~ "(?i)(error|fatal|exception)"

# Ollama model load/unload events
{container="ollama_gpu"} |~ "(?i)(loaded|unloaded|model)"
```

---

## 10. Environment Variables

Key `.env` files:
- `network.env` — IP addresses for all nodes (shared across all nodes)
- `execution_plane/.env` — Agent runtime secrets (DB URLs, Langfuse keys, Redis password)
- `control_plane/.env` — Control plane secrets (DB passwords, SPIRE config)
- `turing_gateway/.env` — Gateway secrets (Authentik, Traefik)

**Never commit `.env` files to git.** Secrets are injected at container start via `env_file`.

---

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `network.env` | Configuration | All IP addresses and node roles |
| `turing_gateway/docker-compose.yml` | Infrastructure | Gateway Node services and port mappings |
| `execution_plane/docker-compose.yml` | Infrastructure | Execution Node services |
| `control_plane/docker-compose.yml` | Infrastructure | Control Node services |
| `config/prometheus/prometheus.yml` | Configuration | Scrape targets and intervals |
| `config/grafana/provisioning/dashboards/` | Configuration | Dashboard JSON definitions |
| `agents/main.py` | Implementation | API endpoint definitions |
| `agents/metrics.py` | Implementation | Custom Prometheus metrics |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-23 | AI-Copilot | Updated to v3.3 with training pipeline and PostgreSQL schema |
| 2026-02-20 | AI-Copilot | Initial technical reference created |

</details>

---

## Maintenance & Update Guide

### When IPs or Ports Change

1. Update `network.env` with new IP addresses.
2. Update the Network Topology table in Section 1.
3. Update `docker-compose.yml` files if port mappings change.
4. Update Prometheus scrape targets in `config/prometheus/prometheus.yml`.

### When Services Are Added

1. Add the service to the appropriate node's Service Inventory table.
2. Add its port to the UI URLs table if it has a web interface.
3. Add a Prometheus scrape target if it exposes metrics.
4. Add Loki log labels if it produces structured logs.

### Keeping Environment Variables Current

- After adding new env vars, add them to the Environment Variables table in Section 10.
- Never commit `.env` files — document the variable names and purposes only.

---

## Functionality Testing

### Manual Verification

1. **Network connectivity**: Ping each node IP from the Gateway Node.
2. **Service health**: `curl` each API endpoint listed in Section 3 → verify 200 responses.
3. **Prometheus targets**: Check `http://<gateway-node-ip>:9091/targets` → all should show UP.
4. **Grafana dashboards**: Open each dashboard listed in Section 6 → verify data is flowing.
5. **PostgreSQL schema**: Connect to the swarm database → verify all tables listed in Section 7 exist.

---

*See also: [Design Framework](design_framework.md) · [Security](security.md) · [Back to Index](../INDEX.md)*
