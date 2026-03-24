# Agentic Hive: Connection Reference Guide

> **All IP addresses are managed in [`network.env`](../network.env) — edit that single file when IPs change.**

This document serves as the living reference for all User Interfaces and backend API endpoints across the three-node Home AI Lab cluster.

---

## 🌐 Network Topology

**Architecture Overview**: R730 serves as the **Gateway/Ops layer** with centralized routing, while Justin-PC focuses on **GPU-intensive inference and generation**.

| Node           | IP Address      | Role                                    |
| :------------- | :-------------- | :-------------------------------------- |
| Home Assistant | `192.168.2.100` | Smart Home Hub                          |
| Justin-PC      | `192.168.2.101` | Compute Node (Inference + ComfyUI + Training) |
| Control-Node   | `192.168.2.102` | Control Plane (SPIRE, Langfuse, DB)     |
| **R730**       | `192.168.2.103` | **Gateway/Ops Hub** (Traefik, Monitoring) |
| iDRAC          | `192.168.2.104` | R730 Remote Management                  |

---

## 🖥️ User Interfaces (Web UIs)

**Primary Entry Point**: All UIs accessible via **R730 Traefik Gateway** @ `http://192.168.2.103`

| Interface                | URL                         | Hosted On    | Purpose                                                           |
| :----------------------- | :-------------------------- | :----------- | :---------------------------------------------------------------- |
| **Traefik Gateway** ⭐   | `http://192.168.2.103:80`   | Dell R730    | Central reverse proxy (primary entry point for all services)       |
| **Open-WebUI Gateway**   | `http://192.168.2.103:3000` | Dell R730    | Primary chat interface to interact with the Swarm.                |
| **Grafana / Ops Portal** | `http://192.168.2.103:3001` | Dell R730    | Real-time Docker logs, GPU metrics, training pipeline, template scores. |
| **Prometheus Metrics**   | `http://192.168.2.103:9091` | Dell R730    | Time-series metrics database + query interface.                   |
| **Loki Logs API**        | `http://192.168.2.103:3100` | Dell R730    | Log aggregation backend (data source for Grafana).                |
| **Traefik Dashboard**    | `http://192.168.2.103:8080` | Dell R730    | Live routing and load balancer metrics.                           |
| **Langfuse Dashboard**   | `http://192.168.2.102:3000` | Control-Node | Live tracking of LLM traces, MarsRL Process Rewards, token usage. |
| **OpenHands Sandbox**    | `http://192.168.2.103:3002` | Dell R730    | Secure code execution sandbox (migrated from Justin-PC).          |
| **ComfyUI**              | `http://192.168.2.103/comfy` | R730→Justin-PC | Node-based GUI for 3D/Image Generation (routed via Traefik).     |
| **Authentik SSO**        | `http://192.168.2.103:9000` | Dell R730    | Single Sign-On identity provider.                                 |
| **VS Code (DevOps)**     | `http://192.168.2.103:8445` | Dell R730    | Full workspace IDE (port remapped from 8443).                     |
| **VS Code (Coding)**     | `http://192.168.2.103:8444` | Dell R730    | Restricted sandbox IDE.                                           |

---

## ⚙️ API Endpoints

### 1. The Swarm Engine (via R730 Traefik Gateway)

**Primary Entrypoint**: All requests route through R730 Traefik to Justin-PC backend

| Endpoint (Routed via R730)                                 | Method | Description                                              |
| :--------------------------------------------------------- | :----- | :------------------------------------------------------- |
| `http://192.168.2.103/swarm/docs`                          | `GET`  | Swagger UI for the FastAPI Swarm backend.                |
| `http://192.168.2.103/swarm/v1/chat/completions`           | `POST` | OpenAI-compatible endpoint for Open-WebUI / Continue.    |
| `http://192.168.2.103/swarm/v1/models`                     | `GET`  | Returns the mock `Home-AI-Swarm` model for UI dropdowns. |
| `http://192.168.2.103/swarm/task`                          | `POST` | Raw task submission (`{"prompt": "string"}`).            |
| `http://192.168.2.103/swarm/voice/stream`                  | `POST` | BMO Voice Satellite endpoint (PCM → TTS).                |

**Direct Access** (if Traefik unavailable): `http://192.168.2.101:8008/...` (Justin-PC bypass)

### 2. Local Inference Services

| Service                      | Endpoint                                  | Hosted On | Purpose                                            |
| :--------------------------- | :---------------------------------------- | :-------- | :------------------------------------------------- |
| **Ollama (Primary)**         | `http://192.168.2.101:11434/api/generate` | Justin-PC | `qwen3.5:9b` (Heavy-Local) — Large-scale coding expertise. |
| **Ollama (Secondary/Gateway)** | `http://192.168.2.103:11434/api/generate` | Dell R730 | `qwen3.5:9b`, `nemotron-orchestrator`, `llama-guard3:8b`. |
| **RVC Voice Generation**     | `http://192.168.2.101:8100/infer`         | Justin-PC | Physical BMO robot voice reconstruction.          |
| **Qwen3-TTS Module**         | `http://192.168.2.101:8020/tts`           | Justin-PC | Base Text-to-Speech generation.                   |

---

## 📝 Common Connection Settings

To connect **Open-WebUI** or **external agents** to the Swarm:

### Primary Connection ⭐ (via R730 Traefik Gateway)
- **Entrypoint:** `http://192.168.2.103/swarm/v1`
- **Recommended Model:** `Home-AI-Swarm`
- **Context Window:** `128,000`
- **Max Tokens (Output):** `4,096` (Standard for coding responses)
- **API Key:** `sk-swarm` (or leave blank for local-only)

### Direct Connection (bypass gateway)
- **Justin-PC Inference:** `http://192.168.2.101:8008/v1`
- **R730 Inference:** `http://192.168.2.103:11434/api` (Ollama only)

To connect directly to the **Local Expert** (High Performance):
- **OLLAMA_BASE_URL:** `http://192.168.2.101:11434`
- **Target Model:** `qwen3.5:9b`

To connect directly to the **Offload Solver** (Efficient):
- **OLLAMA_BASE_URL:** `http://192.168.2.103:11434`
- **Target Model:** `qwen3.5:9b`
- **Context Window:** `256,000`
- **Orchestrator Model:** `nemotron-orchestrator:8b` (Context: 4,096)

### 3. Training Pipeline (Justin-PC — On-Demand)

The training runtime runs as a profile-gated Docker service. It is NOT always running — start it only when training.

```bash
# Build training runtime (first time only)
docker compose --profile training build training-runtime

# Generate synthetic training data
docker compose --profile training run --rm training-runtime \
  python -m training.synthetic_gen --target_count=50

# Run QLoRA GRPO training
docker compose --profile training run --rm training-runtime \
  python -m training.grpo_trainer --dataset /workspace/training_data/traces.jsonl

# Convert LoRA → GGUF → Ollama
docker compose --profile training run --rm training-runtime \
  python -m training.convert_gguf --adapter /workspace/training_output/grpo_*/adapter
```

### 4. Grafana Dashboards

| Dashboard | UID | Datasource | Purpose |
|-----------|-----|------------|---------|
| Training Pipeline | `training-pipeline` | PostgreSQL-Swarm | Training runs, dataset growth, model versions, A/B tests |
| Template Scores | `template-performance` | PostgreSQL-Swarm + Prometheus | Score trends, invocation volume, corrector rate |

---

## 🛡️ Remote Access (Tailscale)

For off-site access, use your Tailscale IP addresses or MagicDNS names instead of the local `192.168.2.x` addresses.

**Primary Gateway Entry Point**: All services routed through R730 Traefik

| Node           | Tailscale Address (Example) | Common Ports          | Purpose |
| :------------- | :-------------------------- | :-------------------- | :------ |
| **Dell R730**  | `dell-r730.tail-xxxx.ts.net` | 80, 3000, 3001, 9091, 8080 | Gateway/Ops Hub (Traefik + all monitoring) |
| **Justin-PC**  | `justin-pc.tail-xxxx.ts.net` | 8008, 8188, 11434 (direct access only) | Compute Node (direct access if needed) |
| **Control-Node**| `control-node.tail-xxxx.ts.net`| 3000 | SPIRE, Langfuse, DB |

> [!TIP]
> Use `tailscale status` on any node to find the specific IP or hostname. Ensure **MagicDNS** is enabled in your Tailscale admin console for the shortest URLs.
>
> **Recommended**: Connect via R730 gateway (`dell-r730.tail-xxxx.ts.net:80`) for all services unless you need direct access to compute node.
