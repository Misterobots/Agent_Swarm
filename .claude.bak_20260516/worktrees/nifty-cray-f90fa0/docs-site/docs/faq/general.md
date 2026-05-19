---
title: "FAQ: General"
---

# General FAQ

## What is Memex?

Memex is a self-hosted, multi-agent AI platform that runs on your own hardware. It orchestrates multiple specialized AI agents — for chat, image generation, 3D modeling, voice, IoT control, and more — through a unified interface.

## Who is it for?

Anyone who wants a private, extensible AI assistant. The three main audiences are:

- **Users** — interact via the Hive UI
- **Admins** — deploy and manage the infrastructure
- **Developers** — extend with custom agents and tools

## What hardware do I need?

At minimum:

- One machine with an NVIDIA GPU (8 GB+ VRAM)
- 32 GB RAM
- 100 GB storage

The recommended setup uses three nodes (Control, Execution, Gateway). See [Prerequisites](../admin-guide/deployment/prerequisites.md).

## Is it free?

Yes. Memex is open source. The LLMs run locally via Ollama — no API keys or subscriptions required.

## What models does it use?

By default:

| Role | Model |
|------|-------|
| Solver | {{ solver_model }} |
| Router | {{ router_model }} |
| Verifier | {{ verifier_model }} |

You can switch to any Ollama-compatible model. See [Switch Models](../procedures/switch-models.md).

## Can I use it without internet?

Yes, once models are downloaded. All inference, storage, and processing happen on your local network. Internet is only needed for web searches in Research Mode.

## How is it different from ChatGPT/Claude?

- **Private** — your data never leaves your network
- **Multi-agent** — specialized agents for different tasks
- **Self-hosted** — runs on your hardware
- **Extensible** — add custom agents, tools, and workflows
- **IoT-connected** — controls smart home devices


