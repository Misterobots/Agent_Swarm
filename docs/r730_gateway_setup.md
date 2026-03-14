# MarsRL Hive Gateway Setup

This guide explains how to deploy the **AI Lab Gateway** on the Dell R730 Server. The gateway provides the OpenWebUI interface and runs its own Ollama instance for routing and safety models.

> **Note:** The AI Lab gateway runs on its own isolated Docker network (`ai_lab_net`), completely separate from any other services (e.g. Saltbox media stack) on the same host.

## 1. Prerequisites

- Docker + Docker Compose installed on the R730
- NVIDIA Container Toolkit installed (for GPU passthrough)
- The `network.env` file from the repo root (for reference IPs)

## 2. Deploy the AI Lab Gateway

On the Dell R730 server, clone the repo (or copy the `r730_gateway/` folder) and start the stack:

```bash
cd r730_gateway
docker compose up -d
```

This starts two containers:
| Container | Port | Description |
|-----------|------|-------------|
| `ollama-r730` | `:11434` | Ollama inference (nemotron-orchestrator, llama-guard) |
| `open-webui` | `:3000` | OpenWebUI chat interface |

## 3. Pull the AI Lab Models

After the first start, pull the required models into the R730's Ollama:

```bash
docker exec ollama-r730 ollama pull qwen3.5:9b
docker exec ollama-r730 ollama pull nemotron-orchestrator:8b
docker exec ollama-r730 ollama pull llama-guard-3:8b
```

The gateway will be available at: **http://192.168.2.103:3000**

Create your initial admin account by clicking "Sign Up" on the login screen.

## 4. Connect the Windows PC Swarm API

To enable the full MarsRL coding loop, connect OpenWebUI to the Justin-PC Swarm Engine:

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

- **Code/Technical Requests**: Automatically routed to `qwen3.5:9b` (Primary Solver/Corrector) running right here on the R730. This ensures maximum speed by avoiding VRAM bottlenecks on the desktop.
- **Expert Tasks**: Large codebase analysis uses the Primary Solver `qwen3.5:9b` model.
- **Image/3D**: Routed to ComfyUI on Justin-PC's 16GB GPU.
