# Home AI Lab — System Overview

> **Back to:** [Documentation Index](../INDEX.md)

---

## What Is Home AI Lab?

Home AI Lab is a **private, self-hosted AI assistant** running on dedicated hardware in your home network. It gives you access to powerful AI capabilities — coding help, image generation, 3D modeling, voice interaction, IoT control, and more — without sending your data to external cloud services.

At its core is the **Agentic Hive**: a coordinated swarm of specialized AI agents that collaborate to answer your questions, write and run code, generate creative media, and control your smart home.

---

## What Can It Do?

### Intelligent Chat & Coding
Ask anything. The Hive routes your request to the most appropriate specialist agent. For coding tasks, a multi-step verification loop (`Solver → Verifier → Corrector`) ensures the code actually works before you see it — broken syntax and unsafe code are automatically fixed or blocked.

### Image & 3D Generation
Generate photorealistic images and 3D models using ComfyUI and TripoSG. Describe what you want; the Creative Forge agent handles the rest.

### Voice Interaction (BMO)
Speak to BMO, a physical voice-enabled robot that responds using a cloned voice model. The Voice Studio handles speech recognition, TTS synthesis, and RVC voice cloning.

### Smart Home Control
The IoT Agent integrates with Home Assistant. Say "turn off the living room lights" or "set the thermostat to 70°F" — it translates natural language into safe, validated Home Assistant API calls.

### Autonomous Code Execution
The DevOps and Coding agents can write, run, and debug code in isolated VS Code sandbox environments. They do not execute arbitrary commands without verification layers.

### Hardware Prototyping
The Maker Space workspace simulates and programs embedded hardware (ESP32, Arduino) using Wokwi, and can flash physical devices via ESPHome.

---

## How Do I Access It?

All services are available through the **Gateway Node** (`http://<gateway-node-ip>`).

| Interface | URL | What It's For |
|-----------|-----|---------------|
| **Hive Mind UI** | `http://<gateway-node-ip>` | Primary chat + all workspaces |
| **Open-WebUI** | `http://<gateway-node-ip>:3000` | Alternative chat interface |
| **ComfyUI** | `http://<gateway-node-ip>/comfy` | Direct image/3D workflow editor |
| **Grafana** | `http://<gateway-node-ip>:3001` | System performance dashboards |
| **Langfuse** | `http://<control-node-ip>:3000` | AI trace viewer (LLM call history) |

For remote access outside the home network, use Tailscale MagicDNS — connect to the Gateway Node as your entry point for all services.

---

## Workspaces

The Hive Mind UI is organized into **workspaces**, each optimized for a different task:

| Workspace | What You Do There |
|-----------|-------------------|
| **Chat** | General AI assistance, Q&A, research, writing, coding help |
| **Media** | Image and 3D model generation (ComfyUI) |
| **Voice Studio** | Record voice samples, test TTS, interact with BMO |
| **Coding** | Collaborative code editing in a VS Code sandbox |
| **DevOps** | Infrastructure management, Docker, system automation |
| **Maker Space** | IoT prototyping, hardware simulation, device flashing |
| **Governance** | Review AI security evaluations and output quality |
| **Control** | System status, node health, live metrics |
| **Documents** | This documentation — user guides, admin reference, specs |

---

## Privacy & Data

- **All data stays on your hardware.** No requests are sent to external AI services.
- Every AI interaction is logged to **Langfuse** (on your Control Node) for quality monitoring and optional model training.
- Logs are stored locally on the Gateway Node for 90 days (Prometheus metrics) and indefinitely (Loki logs, unless purged).
- You can review all traces at `http://<control-node-ip>:3000`.

---

## System Status

The current system is running **Version 3.3** (Phase 6 complete):
- ✅ MarsRL inference-time quality loop
- ✅ JWT-ACE capability-based security
- ✅ ExpertiseTemplate versioned agents
- ✅ GRPO fine-tuning pipeline with A/B testing
- ⚠️ Gateway Node not yet enrolled in SPIRE zero-trust identity (JWT-ACE covers runtime gaps)

---

*For technical details, see [Admin: Design Framework](../admin/design_framework.md) · [Back to Index](../INDEX.md)*
