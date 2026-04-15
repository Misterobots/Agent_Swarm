---
title: Glossary
---

# Glossary

| Term | Definition |
|------|-----------|
| **Action Figure Pipeline** | Specialized 3D generation workflow optimized for character models |
| **Agent** | A specialized component that handles a specific category of tasks (e.g., Image Agent, IoT Agent) |
| **Agent Runtime** | The main Python application that hosts all agents, the router, coordinator, and tools |
| **ComfyUI** | Node-based image/video generation tool used for AI art and 3D reference images |
| **Control Node** | The server ({{ control_node_ip }}) running SPIRE, PostgreSQL, and Langfuse |
| **Coordinator** | The orchestration component that manages agent dispatch and multi-step workflows |
| **Dispatcher** | Task queue manager that routes jobs to appropriate agents |
| **Execution Node** | The server ({{ execution_node_ip }}) running Ollama, Agent Runtime, ComfyUI, and voice services |
| **Gateway Node** | The R730 server ({{ gateway_node_ip }}) running Traefik, Prometheus, Grafana, and Loki |
| **GRPO** | Group Relative Policy Optimization — the preference training algorithm used by MarsRL |
| **Hive UI** | The web-based chat interface for interacting with Agent Swarm |
| **Intent** | The classified purpose of a user message (e.g., `general_chat`, `image_generation`, `iot_control`) |
| **Langfuse** | Open-source LLM observability platform used for tracing and analytics |
| **Loki** | Log aggregation system by Grafana Labs |
| **MarsRL** | Mars Reinforcement Learning — the solve → verify → reward loop that ensures response quality |
| **MemPalace** | The vector memory system using PostgreSQL + pgvector for semantic retrieval |
| **mTLS** | Mutual TLS — both client and server authenticate each other with certificates |
| **Ollama** | Local LLM inference server that runs models on GPU |
| **pgvector** | PostgreSQL extension for vector similarity search, used for embeddings |
| **Piper** | Local text-to-speech (TTS) engine |
| **Prometheus** | Metrics collection and alerting system |
| **Router** | The intent classification component that determines which agent handles a request |
| **Skills Memory** | Long-term memory system that stores user preferences and learned patterns |
| **Solver** | The primary LLM model that generates responses to user queries |
| **SPIFFE** | Secure Production Identity Framework for Everyone — standard for service identity |
| **SPIRE** | SPIFFE Runtime Environment — provides cryptographic identity (SVIDs) to services |
| **SVID** | SPIFFE Verifiable Identity Document — a short-lived X.509 certificate |
| **Traefik** | Cloud-native reverse proxy and load balancer |
| **Verifier** | The LLM model that checks response quality and safety before delivery |
| **VRAM** | Video RAM — GPU memory used for model inference |
| **Whisper** | OpenAI's speech-to-text (STT) model |
| **Workflow** | A ComfyUI node graph defining an image/video generation pipeline |
