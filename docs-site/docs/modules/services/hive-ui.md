---
title: "Service: Hive UI"
---

# Hive UI

The web-based frontend for Agent Swarm.

## Deployment

| Property | Value |
|----------|-------|
| **URL** | `http://{{ gateway_node_ip }}/` |
| **Framework** | Web application |
| **Directory** | `ui/` |

## Features

- Chat interface with streaming responses
- Image gallery for generated artwork
- 3D model viewer (Three.js)
- Session management
- Status indicators (model loading, generation progress)
- Dark/light theme

## Access

Open a browser and navigate to:

```
http://{{ gateway_node_ip }}/
```

Or via Tailscale for remote access.

## API Communication

The Hive UI communicates with the Agent Runtime via:

```
POST /swarm/v1/chat/completions
```

Using Server-Sent Events for streaming responses.

## Related

- [User Guide: Chat](../../user-guide/chat.md) — using the chat interface
- [Getting Started: User Quickstart](../../getting-started/quickstart-user.md) — first use
