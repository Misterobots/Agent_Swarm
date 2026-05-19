# Agentic Hive: Connection Reference Guide

> **All IP addresses are managed in [`network.env`](../network.env) — edit that single file when IPs change.**

This document serves as the living reference for all User Interfaces and backend API endpoints across the three-node Home AI Lab cluster.

---

## 🌐 Network Topology

**Architecture Overview**: Turing serves as the **Gateway/Ops layer** with centralized routing, while Lovelace focuses on **GPU-intensive inference and generation**.

| Node           | IP Address      | Role                                    |
| :------------- | :-------------- | :-------------------------------------- |
| Home Assistant | `192.168.2.100` | Smart Home Hub                          |
| Lovelace       | `192.168.2.101` | Compute Node (Inference + ComfyUI)      |
| Hopper         | `192.168.2.102` | Control Plane (SPIRE, Langfuse, DB)     |
| **Turing**     | `192.168.2.103` | **Gateway/Ops Hub** (Traefik, agent_runtime, hive_ui) |
| iDRAC          | `192.168.2.104` | Turing Remote Management                |
| BMO            | `192.168.2.106` | Raspberry Pi (Voice/IoT, wakeword)      |

> **Note**: Turing has **no dedicated GPU** (RTX 3070 Ti removed — CPU inference only for safety/embed models). All large model inference runs on Lovelace (dual RTX 5060 Ti, 32 GB VRAM total).

---

## 🖥️ User Interfaces (Web UIs)

**Primary Entry Point**: All UIs accessible via **Turing Traefik Gateway** @ `http://192.168.2.103`

| Interface                | URL                         | Hosted On       | Purpose                                                           |
| :----------------------- | :-------------------------- | :-------------- | :---------------------------------------------------------------- |
| **Traefik Gateway** ⭐   | `http://192.168.2.103:80`   | Turing          | Central reverse proxy (primary entry point for all services)      |
| **Hive UI** ⭐           | `http://192.168.2.103:3200` | Turing          | **Primary chat interface** — Next.js Hive Mind UI.                |
| **Grafana / Ops Portal** | `http://192.168.2.103:3001` | Turing          | Real-time Docker logs, metrics, agent performance.                |
| **Prometheus Metrics**   | `http://192.168.2.103:9091` | Turing          | Time-series metrics database + query interface.                   |
| **Loki Logs API**        | `http://192.168.2.103:3100` | Turing          | Log aggregation backend (data source for Grafana).                |
| **Traefik Dashboard**    | `http://192.168.2.103:8080` | Turing          | Live routing and load balancer metrics.                           |
| **Langfuse Dashboard**   | `http://192.168.2.102:3000` | Hopper          | Live tracking of LLM traces, MarsRL Process Rewards, token usage. |
| **OpenHands Sandbox**    | `http://192.168.2.103/hands` | Turing→Lovelace | Secure Docker-in-Docker (routed via Traefik).                    |
| **ComfyUI**              | `http://192.168.2.103/comfy` | Turing→Lovelace | Node-based GUI for 3D/Image Generation (routed via Traefik).     |

---

## ⚙️ API Endpoints

### 1. The Swarm Engine (via Turing Traefik Gateway)

**Primary Entrypoint**: All requests route through Turing Traefik to Lovelace backend

| Endpoint (Routed via Turing)                                 | Method | Description                                              |
| :--------------------------------------------------------- | :----- | :------------------------------------------------------- |
| `http://192.168.2.103/swarm/docs`                          | `GET`  | Swagger UI for the FastAPI Swarm backend.                |
| `http://192.168.2.103/swarm/v1/chat/completions`           | `POST` | OpenAI-compatible endpoint for Open-WebUI / Continue.    |
| `http://192.168.2.103/swarm/v1/models`                     | `GET`  | Returns the mock `Home-AI-Swarm` model for UI dropdowns. |
| `http://192.168.2.103/swarm/task`                          | `POST` | Raw task submission (`{"prompt": "string"}`).            |
| `http://192.168.2.103/swarm/voice/stream`                  | `POST` | BMO Voice Satellite endpoint (PCM → TTS).                |

**Direct Access** (if Traefik unavailable): `http://192.168.2.101:8008/...` (Lovelace bypass)

### 2. Local Inference Services

| Service                      | Endpoint                                  | Hosted On | Purpose                                            |
| :--------------------------- | :---------------------------------------- | :-------- | :------------------------------------------------- |
| **Ollama (Primary)**    | `http://192.168.2.101:11434/api/generate` | Lovelace | `gemma4:31b` (20 GB), `qwen3.6:27b` (17.4 GB), `qwen2.5-coder:14b` (9 GB), `qwen3:8b` (5.2 GB), `llama3.2:3b` (2 GB), `nomic-embed-text` (274 MB). |
| **Ollama (Turing — CPU only)** | `http://192.168.2.103:11434/api/generate` | Turing | `nomic-embed-text`, `llama-guard-3:8b` — safety screening and embeddings only. No large models. |
| **RVC Voice Generation**     | `http://192.168.2.101:8100/infer`         | Lovelace | Physical BMO robot voice reconstruction.          |
| **Qwen3-TTS Module**         | `http://192.168.2.101:8020/tts`           | Lovelace | Base Text-to-Speech generation.                   |

---

## 📝 Common Connection Settings

To connect **Open-WebUI** or **external agents** to the Swarm:

### Primary Connection ⭐ (via Turing Traefik Gateway)
- **Entrypoint:** `http://192.168.2.103/swarm/v1`
- **Recommended Model:** `Home-AI-Swarm`
- **Context Window:** `128,000`
- **Max Tokens (Output):** `4,096` (Standard for coding responses)
- **API Key:** `sk-swarm` (or leave blank for local-only)

### Direct Connection (bypass gateway)
- **Agent Runtime (Turing):** `http://192.168.2.103:8008/v1`
- **Lovelace Ollama:** `http://192.168.2.101:11434/api` (Ollama direct)

To connect directly to the **Local Expert** (High Performance):
- **OLLAMA_BASE_URL:** `http://192.168.2.101:11434`
- **Primary Model:** `gemma4:31b`
- **Fallback Model:** `qwen3.6:27b`

To connect directly to the **Coder** (Efficient):
- **OLLAMA_BASE_URL:** `http://192.168.2.101:11434`
- **Target Model:** `qwen2.5-coder:14b`
- **Context Window:** `128,000`

---

## 🛡️ Remote Access (Tailscale)

For off-site access, use your Tailscale IP addresses or MagicDNS names instead of the local `192.168.2.x` addresses.

**Primary Gateway Entry Point**: All services routed through Turing Traefik

| Node        | Tailscale Address (Example)    | Common Ports               | Purpose |
| :---------- | :----------------------------- | :------------------------- | :------ |
| **Turing**  | `turing.tail-xxxx.ts.net`      | 80, 3200, 3001, 9091, 8080 | Gateway/Ops Hub (Traefik + monitoring + agent_runtime + hive_ui) |
| **Lovelace** | `lovelace.tail-xxxx.ts.net`   | 8188, 11434 (direct only)  | Compute Node (Ollama GPU inference, ComfyUI) |
| **Hopper**  | `hopper.tail-xxxx.ts.net`      | 3000                       | SPIRE, Langfuse, DB |

> [!TIP]
> Use `tailscale status` on any node to find the specific IP or hostname. Ensure **MagicDNS** is enabled in your Tailscale admin console for the shortest URLs.
>
> **Recommended**: Connect via Turing gateway (`dell-turing.tail-xxxx.ts.net:80`) for all services unless you need direct access to compute node.

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `network.env` | Configuration | All node IPs and service ports |
| `turing_gateway/docker-compose.yml` | Infrastructure | Traefik reverse proxy rules |
| Tailscale admin console | External | Remote access machine names |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-05-04 | AI-Copilot | Fixed: Traefik `hive-static-http` bypass router — HTTP (port 80) static asset requests to `/manifest.json`, `/_next/`, `/favicon.ico` etc. were intercepted by `authentik@docker` ForwardAuth before `redirect-to-https` could run, causing CORS-blocked OAuth redirects. Added priority-30 `web` entrypoint router with `redirect-to-https` only (no auth). Also fixed: `coordinate_task()` `ultraplan_mode`/`dev_mode` signature mismatch in `agents/lamport.py`; cAdvisor `/dev/kmsg` device removed from compose (AppArmor block on Ubuntu 22.04). |
| 2026-05-04 | AI-Copilot | Updated: gemma4:31b primary models, dual RTX 5060 Ti (32 GB), Turing GPU removal, Hive UI as primary (:3200), Prometheus port :9091, agent_runtime on Turing, Hopper node name, BMO node added |
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-01 | AI-Copilot | Initial connection reference |

</details>

---

## Maintenance & Update Guide

- Update whenever a service port changes or a new service is deployed.
- Update Tailscale machine names if devices are re-registered.
- Cross-reference `network.env` to ensure IPs stay in sync.

---

## Functionality Testing

| Endpoint | Quick Test |
|----------|------------|
| Hive UI | `curl -s -o /dev/null -w '%{http_code}' http://192.168.2.103:3200` → 200 |
| Agent Runtime | `curl http://192.168.2.103:8008/health` → 200 |
| Grafana | `curl http://192.168.2.103:3001` → 200 |
