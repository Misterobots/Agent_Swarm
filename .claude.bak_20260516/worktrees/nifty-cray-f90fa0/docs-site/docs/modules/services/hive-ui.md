---
title: "Service: Hive UI"
---

# Hive UI

The web-based frontend for Memex.

## Deployment

| Property | Value |
|----------|-------|
| **URL** | `http://{{ turing_ip }}/` |
| **Framework** | Web application |
| **Directory** | `ui/` |

## Features

- Chat interface with streaming responses
- Image gallery for generated artwork
- 3D model viewer (Three.js)
- Palace Viewer (`/palace`) with first-person room and drawer navigation
- Session management
- Status indicators (model loading, generation progress)
- Dark/light theme

## Access

Open a browser and navigate to:

```
http://{{ turing_ip }}/
```

Or via Tailscale for remote access.

## API Communication

The Hive UI uses a server-side proxy at `/api/backend/*` with split upstream routing:

| Upstream | Environment Variable | Used For |
|----------|----------------------|----------|
| Agent Runtime | `API_BASE_URL` | Identity, chat, training, ops, and general swarm APIs |
| MemPalace | `MEMPALACE_BASE_URL` | Palace Viewer layout, room, memory search, and memory CRUD |

Examples:

```
POST /swarm/v1/chat/completions
GET /api/backend/api/v1/identity
GET /api/backend/v1/palace/layout
```

Streaming chat continues to use Server-Sent Events through the Agent Runtime path.

For deployed gateway environments, the `hive-ui` container must define both `API_BASE_URL` and `MEMPALACE_BASE_URL`. Without the second variable, the Palace Viewer route renders but cannot load live Palace data.

## Related

- [User Guide: Chat](../../user-guide/chat.md)  using the chat interface
- [Getting Started: User Quickstart](../../getting-started/quickstart-user.md)  first use


