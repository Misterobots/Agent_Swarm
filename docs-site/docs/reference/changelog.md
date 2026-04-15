---
title: Changelog
---

# Changelog

All notable changes to Agent Swarm are documented here.

## [Unreleased]

### Added

- Comprehensive MkDocs documentation site
- Docker-based documentation deployment
- GitHub Pages deployment via GitHub Actions

### Changed

- Documentation restructured as a full library of procedures, tutorials, and references

---

## [1.0.0] — Initial Release

### Features

- Multi-agent orchestration (Router → Coordinator → Solver)
- MarsRL verification loop (solve → verify → reward)
- Image generation via ComfyUI integration
- 3D model generation pipeline
- Voice interface (Whisper STT + Piper TTS)
- IoT control via Home Assistant
- Research Mode with web search
- Skills Memory (PostgreSQL + pgvector)
- SPIRE-based service identity and mTLS
- Langfuse observability and tracing
- Prometheus + Grafana monitoring
- Loki log aggregation
- Traefik reverse proxy and load balancing
- GRPO preference training
- Governance system for sensitive operations
- Hive UI web interface
- GPU allocation and management
- 3-node distributed architecture

### Infrastructure

- Docker Compose deployment across 3 nodes
- Control Plane: SPIRE server, PostgreSQL, Langfuse
- Execution Plane: Ollama, Agent Runtime, ComfyUI, Voice
- Gateway: Traefik, Prometheus, Grafana, Loki
