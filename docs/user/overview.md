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

### Image, 3D & Action Figure Generation
Generate photorealistic images, 3D models, and 3D-printable posable action figures using the **Art Studio** workspace. Powered by ComfyUI, TripoSG, and Hunyuan3D — describe what you want and the system handles concept art, mesh generation, and export.

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
| **Art Studio** | Image, 3D model, and posable action figure generation (ComfyUI + TripoSG/Hunyuan3D) |
| **Voice Studio** | Record voice samples, test TTS, interact with BMO |
| **Coding** | Collaborative code editing in a VS Code sandbox |
| **DevOps** | Infrastructure management, Docker, system automation |
| **Maker Space** | IoT prototyping, hardware simulation, device flashing |
| **Governance** | Review AI security evaluations and output quality |
| **Control** | System status, node health, live metrics |
| **Training** | Fine-tune local models using Langfuse traces, synthetic data, or curated datasets. Convert adapters and deploy via A/B testing |
| **Documents** | This documentation — user guides, admin reference, specs |

---

## Privacy & Data

- **All data stays on your hardware.** No requests are sent to external AI services.
- Every AI interaction is logged to **Langfuse** (on your Control Node) for quality monitoring and optional model training.
- Logs are stored locally on the Gateway Node for 90 days (Prometheus metrics) and indefinitely (Loki logs, unless purged).
- You can review all traces at `http://<control-node-ip>:3000`.

---

## System Status

The current system is running **Version 3.4** (Phase 6 complete):
- ✅ MarsRL inference-time quality loop
- ✅ JWT-ACE capability-based security
- ✅ ExpertiseTemplate versioned agents
- ✅ GRPO fine-tuning pipeline with model conversion, A/B testing, and deployment
- ⚠️ Gateway Node not yet enrolled in SPIRE zero-trust identity (JWT-ACE covers runtime gaps)

---

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|-----------|
| `turing_gateway/docker-compose.yml` | Infrastructure | Gateway Node service definitions |
| `execution_plane/docker-compose.yml` | Infrastructure | Execution Node (GPU + agent runtime) |
| `control_plane/docker-compose.yml` | Infrastructure | Control Node (Langfuse, SPIRE, PostgreSQL) |
| `ui/src/app/` | Implementation | Hive Mind UI workspace routing |
| `agents/main.py` | Implementation | Agent runtime API entry point |
| `docs/INDEX.md` | Documentation | Master documentation index |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|---------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-08 | AI-Copilot | Updated for Phase 6 features (training pipeline) |
| 2026-02-20 | AI-Copilot | Initial system overview created |

</details>

---

## Maintenance & Update Guide

### Updating Service URLs Table

When service ports or URLs change, update the "How Do I Access It?" table. Cross-reference `turing_gateway/docker-compose.yml` for current port mappings.

### Updating Workspaces Table

When new workspaces are added to the UI, add a row to the Workspaces table. Cross-reference `ui/src/app/` for the current workspace routes.

### Version & Phase Status

Update the "System Status" section after each phase milestone. Check off completed features and note known gaps.

---

## Functionality Testing

### Manual Verification

1. **Service accessibility**: For each URL in the access table, verify it loads correctly from a browser on the home network.
2. **Workspace navigation**: Click through each workspace in the sidebar → verify each loads without errors.
3. **Tailscale access**: Connect via Tailscale from an external network → verify all services are reachable.
4. **Privacy check**: Run `tcpdump` or Wireshark on the Gateway Node → verify no outbound AI API calls during inference.

---

*For technical details, see [Admin: Design Framework](../admin/design_framework.md) · [Back to Index](../INDEX.md)*
