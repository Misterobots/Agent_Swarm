---
title: "Service: OpenHands"
---

# OpenHands

Sandboxed code execution environment.

## Deployment

| Property | Value |
|----------|-------|
| **Node** | Execution ({{ lovelace_ip }}) |
| **Port** | 3300 |
| **Isolation** | Docker-in-Docker |
| **Compose** | `execution_plane/docker-compose.yml` |

## Purpose

OpenHands provides a sandboxed environment for executing user code safely. Code runs in an isolated Docker container that cannot affect the host system.

## Features

- Full Python / Node.js / shell environment
- File system isolation
- Network restrictions
- Resource limits (CPU, memory, time)
- Output capture and streaming

## Security

- Docker-in-Docker isolation
- No access to host filesystem
- Limited network access
- Execution timeouts
- Resource quotas

## Related

- [User Guide: Code Assistant](../../user-guide/code-assistant.md)
- [Architecture: Security Model](../../architecture/security-model.md)


