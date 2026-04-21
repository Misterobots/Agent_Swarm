---
title: Prerequisites
---

# Prerequisites

Hardware and software requirements for deploying Agent Swarm.

## Hardware

### Minimum (Single Node)

| Component | Requirement |
|-----------|------------|
| **CPU** | 8 cores, x86-64 |
| **RAM** | 32 GB |
| **GPU** | NVIDIA with ≥ 12 GB VRAM (CUDA 12+) |
| **Storage** | 200 GB SSD |
| **Network** | 1 Gbps LAN |

### Recommended (3-Node)

| Node | Role | CPU | RAM | GPU | Storage |
|------|------|-----|-----|-----|---------|
| Execution | GPU compute | 8+ cores | 32 GB | RTX 5060 Ti 16 GB+ | 500 GB SSD |
| Control | Databases | 4 cores | 8 GB | None | 200 GB SSD |
| Gateway | Proxy, monitoring | 8+ cores | 64 GB | RTX 3070 Ti 8 GB (optional) | 500 GB SSD |

## Software

### All Nodes

| Software | Version | Purpose |
|----------|---------|---------|
| Docker Engine | 24.0+ | Container runtime |
| Docker Compose | v2.20+ | Service orchestration |
| Git | 2.30+ | Repository cloning |

### Execution Node (Windows)

| Software | Version | Purpose |
|----------|---------|---------|
| Docker Desktop | 4.25+ | Docker on Windows |
| NVIDIA Driver | 550+ | GPU access |
| NVIDIA Container Toolkit | Latest | GPU passthrough to containers |
| WSL 2 | Ubuntu 22.04 | Linux subsystem for Docker |

### Control & Gateway Nodes (Linux)

| Software | Version | Purpose |
|----------|---------|---------|
| Ubuntu | 22.04 LTS | Host OS |
| NVIDIA Driver | 550+ | GPU access (Gateway only) |
| NVIDIA Container Toolkit | Latest | GPU passthrough (Gateway only) |

## GPU Requirements

### VRAM Allocation (Reference)

| Model | VRAM | Node |
|-------|------|------|
| {{ solver_model }} | ~6 GB | Execution |
| {{ router_model }} | ~5 GB | Execution |
| {{ verifier_model }} | ~5 GB | Execution |
| FLUX.1-schnell (ComfyUI) | ~10 GB | Execution |
| Qwen3-TTS | ~3 GB | Execution |
| Moondream2 (VLM) | ~2 GB | Execution |

!!! warning "VRAM Management"
    Not all models fit in VRAM simultaneously. Ollama manages model loading/unloading automatically. Set `OLLAMA_NUM_PARALLEL=2` and `OLLAMA_MAX_LOADED_MODELS=3` to control memory pressure.

## Network

- All nodes on the same LAN subnet (e.g., 192.168.2.0/24)
- Static IP addresses assigned to each node
- Ports 80, 443, 8000–9100 open between nodes (see [Port Map](../port-map.md))
- Internet access for model pulling and package installation

## Pre-Deployment Checklist

- [ ] All nodes powered on and accessible via SSH/RDP
- [ ] Docker installed and running on all nodes
- [ ] NVIDIA drivers installed on GPU nodes
- [ ] `nvidia-smi` shows GPU on GPU nodes
- [ ] `docker run --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` succeeds on GPU nodes
- [ ] Nodes can ping each other by IP
- [ ] Repository cloned: `git clone https://github.com/your-org/Agent_Swarm.git`
- [ ] `network.env` populated with correct values

## Next

→ [Deploy Control Plane](control-plane.md)


