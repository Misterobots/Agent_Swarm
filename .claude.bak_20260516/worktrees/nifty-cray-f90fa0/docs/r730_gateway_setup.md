# MarsRL Hive Gateway Setup

This guide explains how to deploy the **AI Lab Gateway** on the Dell Turing Server. The gateway provides the OpenWebUI interface and runs its own Ollama instance for routing and safety models.

> **Note:** The AI Lab gateway runs on its own isolated Docker network (`ai_lab_net`), completely separate from any other services (e.g. Saltbox media stack) on the same host.

## 1. Prerequisites

- Docker + Docker Compose installed on the Turing
- NVIDIA Container Toolkit installed (for GPU passthrough)
- The `network.env` file from the repo root (for reference IPs)

## 2. Deploy the AI Lab Gateway

On the Dell Turing server, clone the repo (or copy the `turing_gateway/` folder) and start the stack:

```bash
cd turing_gateway
docker compose up -d
```

This starts two containers:
| Container | Port | Description |
|-----------|------|-------------|
| `ollama-turing` | `:11434` | Ollama inference (nemotron-orchestrator, llama-guard) |
| `open-webui` | `:3000` | OpenWebUI chat interface |

## 3. Pull the AI Lab Models

After the first start, pull the required models into the Turing's Ollama:

```bash
docker exec ollama-turing ollama pull qwen3.5:9b
docker exec ollama-turing ollama pull nemotron-orchestrator:8b
docker exec ollama-turing ollama pull llama-guard-3:8b
```

The gateway will be available at: **http://192.168.2.103:3000**

Create your initial admin account by clicking "Sign Up" on the login screen.

## 4. Connect the Windows PC Swarm API

To enable the full MarsRL coding loop, connect OpenWebUI to the Lovelace Swarm Engine:

1. In OpenWebUI, go to **Profile → Settings → Admin Settings → Connections**
2. Under **OpenAI API**, click `+` to add a connection:
   - **Base URL:** `http://192.168.2.101:8008/v1`
   - **API Key:** `sk-local-swarm`
   - **Name:** _Swarm Engine_
3. Click **Verify Connection** and **Save**

## 5. Coexistence with Saltbox

The AI Lab gateway and Saltbox run as **completely independent Docker stacks**:

- **AI Lab** → `ai_lab_net` network, ports `3000` + `11434`
- **Saltbox** → `saltbox` network, ports `80/8443` + media services

There are no shared containers, networks, or volumes. To avoid port conflicts:

- Ensure Saltbox's Ollama is removed if present (`sb remove ollama`)
- Both stacks can share the NVIDIA GPU (Ollama uses VRAM, Jellyfin uses Intel iGPU for transcoding)

## 6. Usage

Select the `Home-AI-Swarm` or `default` model from the dropdown at the top of the chat to route prompts through the intent classifier. 

- **Code/Technical Requests**: Automatically routed to `qwen3.5:9b` (Primary Solver/Corrector) running right here on the Turing. This ensures maximum speed by avoiding VRAM bottlenecks on the desktop.
- **Expert Tasks**: Large codebase analysis uses the Primary Solver `qwen3.5:9b` model.
- **Image/3D**: Routed to ComfyUI on Lovelace's 16GB GPU.

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `turing_gateway/docker-compose.yml` | Infrastructure | Gateway compose with OpenWebUI + Ollama |
| `network.env` | Configuration | Node IPs, ports |
| `agents/config.py` | Configuration | Intent-based routing rules |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-01 | AI-Copilot | Initial Turing gateway setup guide |

</details>

---

## Maintenance & Update Guide

- Update when new models are deployed on the gateway.
- Update routing rules when new intent types are handled.

---

## Functionality Testing

| Step | Expected Result |
|------|----------------|
| `curl http://192.168.2.103:8080` | OpenWebUI responds |
| Send text prompt via gateway | Routed to Ollama on Turing |
| Send image generation prompt | Routed to ComfyUI on Lovelace |
