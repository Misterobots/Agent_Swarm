---
title: Chat
---

# Chat

The primary interface for interacting with Agent Swarm. Every message goes through intent classification, agent routing, and the MarsRL quality verification loop.

## How to Access

- **UI**: Navigate to **Chat** in the Hive Mind sidebar
- **API**: `POST /v1/chat/completions` (OpenAI-compatible)
- **URL**: `http://{{ gateway_node_ip }}/swarm/v1/chat/completions`

## Quick Example

=== "UI"

    1. Open Chat workspace
    2. Type: *"Write a Python function to merge two sorted lists"*
    3. Observe status indicators: routing → solving → verifying → streaming

=== "API (cURL)"

    ```bash
    curl -X POST http://{{ gateway_node_ip }}/swarm/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{
        "messages": [
          {"role": "user", "content": "Write a Python function to merge two sorted lists"}
        ],
        "model": "default",
        "stream": true
      }'
    ```

=== "API (Python)"

    ```python
    import requests

    response = requests.post(
        "http://{{ gateway_node_ip }}/swarm/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Write a Python merge sort"}],
            "model": "default",
            "stream": False,
        },
    )
    print(response.json())
    ```

## Detailed Usage

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | `List[ChatMessage]` | *required* | Conversation history (`role` + `content`) |
| `model` | `string` | `"default"` | Model to use (or `"default"` for auto-routing) |
| `stream` | `bool` | `false` | Enable Server-Sent Events streaming |
| `session_id` | `string` | auto-generated | Conversation session ID for context persistence |
| `memory_enabled` | `bool` | `false` | Enable persistent memory for this session |
| `user_id` | `string` | `null` | User identity for scoped storage |
| `skill` | `string` | `null` | Force a specific skill |
| `style` | `string` | `null` | Response style hints |
| `research_mode` | `bool` | `false` | Enable multi-source research mode |
| `ultraplan_mode` | `bool` | `false` | Decompose task into a plan only — no execution |
| `ultrathink_mode` | `bool` | `false` | Deep reasoning with visible chain-of-thought |
| `dev_mode` | `bool` | `false` | Enable Phase 2 dev tools (file ops, terminal) |
| `attachments` | `List[dict]` | `null` | File attachments for context |
| `grounding_web` | `bool` | `false` | Inject live web search results (requires `web_grounding` permission) |
| `grounding_docs` | `bool` | `false` | Inject knowledge-base document chunks (requires `docs_grounding` permission) |

### Streaming

When `stream: true`, the response is delivered as Server-Sent Events:

```
data: {"type": "status", "content": "Routing request..."}
data: {"type": "status", "content": "Solver generating..."}
data: {"type": "thought", "content": "Analyzing the merge algorithm..."}
data: {"type": "response", "content": "Here's a merge function:\n```python..."}
data: {"type": "tool_call", "content": {"tool": "read_file", "args": {...}}}
data: [DONE]
```

Event types: `status`, `thought`, `response`, `tool_call`, `error`.

### Intent-Based Routing

The Semantic Router ({{ router_model }}) classifies your message and routes it to the appropriate agent. You don't need to specify the intent — it's detected automatically.

The confidence threshold is **0.60**. Below that, the router retries with additional context or falls back to `CONVERSATION`.

### Session Memory

When `memory_enabled: true`, the system persists conversation context across sessions. This uses the MemPalace semantic memory service on the Control Node.

### Models

Available models returned by `GET /v1/models`:

| Model ID | Description |
|----------|-------------|
| `swarm-standard` | Default routing through MarsRL loop |
| `Home-AI-Swarm` | Alias for standard routing |

The actual model used depends on the classified intent and the ExpertiseTemplate registry.

## Tips & Common Patterns

!!! tip "Be Specific"
    The more context you provide, the better the router classifies intent. *"Write Python code to parse CSV"* routes to `CODE`; *"CSV"* alone may route to `CONVERSATION`.

!!! tip "Use Dev Mode for File Operations"
    Set `dev_mode: true` to enable file read/write and terminal access tools.

!!! tip "Session Persistence"
    Use the same `session_id` across requests to maintain conversation context.

## Related

- [Architecture: Data Flow](../architecture/data-flow.md) — how a request travels through the system
- [Architecture: MarsRL](../architecture/marsrl.md) — the quality verification loop
- [Module: Router](../modules/router.md) — semantic routing internals
- [API Reference: Chat Completions](../developer-guide/api/chat-completions.md) — full API docs
- [Troubleshooting: Common Errors](../troubleshooting/agent-runtime.md)
- [Tutorial: Your First Chat](../tutorials/first-chat.md)
