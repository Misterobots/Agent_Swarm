---
title: User Guide
---

# User Guide

Feature-by-feature guides for everything Agent Swarm can do. Each page covers what a feature does, how to access it, and how to get the most out of it.

## Features

| Feature | Description | Guide |
|---------|-------------|-------|
| **Chat** | Intelligent conversation with MarsRL quality loop | [Chat](chat.md) |
| **Art Studio** | Image generation with FLUX and SD-XL | [Art Studio](art-studio.md) |
| **3D Generation** | 3D models and action figures | [3D Generation](3d-generation.md) |
| **Voice** | BMO voice synthesis and TTS | [Voice](voice.md) |
| **IoT Control** | Home Assistant device control | [IoT Control](iot-control.md) |
| **Code Assistant** | Code generation, debugging, git ops | [Code Assistant](code-assistant.md) |
| **Research Mode** | Multi-source knowledge synthesis | [Research Mode](research-mode.md) |
| **Training** | Model fine-tuning pipeline | [Training Interface](training-interface.md) |
| **Governance** | Approval workflow for sensitive ops | [Governance Requests](governance-requests.md) |
| **Settings** | Preferences and model selection | [Settings](settings.md) |

---

## Source References

??? info "Source of Truth â€” Canonical Files"

    | Source | Type | Relevance |
    |--------|------|-----------|
    | `turing_gateway/docker-compose.yml` | Infrastructure | Gateway Node service definitions |
    | `execution_plane/docker-compose.yml` | Infrastructure | Execution Node (GPU + agent runtime) |
    | `control_plane/docker-compose.yml` | Infrastructure | Control Node (Langfuse, SPIRE, PostgreSQL) |
    | `ui/src/app/` | Implementation | Hive Mind UI workspace routing |
    | `agents/main.py` | Implementation | Agent runtime API entry point |
    | `docs/INDEX.md` | Documentation | Master documentation index |


---

## Maintenance & Update Guide

### Updating Service URLs Table

When service ports or URLs change, update the "How Do I Access It?" table. Cross-reference `turing_gateway/docker-compose.yml` for current port mappings.

### Updating Workspaces Table

When new workspaces are added to the UI, add a row to the Workspaces table. Cross-reference `ui/src/app/` for the current workspace routes.

### Version & Phase Status

Update the "System Status" section after each phase milestone. Check off completed features and note known gaps.

---

---

## Functionality Testing

### Manual Verification

1. **Service accessibility**: For each URL in the access table, verify it loads correctly from a browser on the home network.
2. **Workspace navigation**: Click through each workspace in the sidebar ? verify each loads without errors.
3. **Tailscale access**: Connect via Tailscale from an external network ? verify all services are reachable.
4. **Privacy check**: Run `tcpdump` or Wireshark on the Gateway Node ? verify no outbound AI API calls during inference.

---

*For technical details, see Admin: Design Framework · [Back to Index](../index.md)*


