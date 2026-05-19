---
title: Chat Completions API
---

# Chat Completions API

The primary API for interacting with Memex. OpenAI-compatible format.

## Endpoint

```
POST /v1/chat/completions
```

Via Gateway: `POST http://{{ turing_ip }}/swarm/v1/chat/completions`

## Request

### Headers

| Header | Required | Value |
|--------|----------|-------|
| `Content-Type` | Yes | `application/json` |

### Body

```json
{
    "messages": [
        {"role": "system", "content": "Optional system prompt"},
        {"role": "user", "content": "Your message here"}
    ],
    "stream": true,
    "model": "{{ solver_model }}",
    "session_id": "optional-session-id",
    "owner_id": "optional-user-id",
    "dev_mode": false,
    "temperature": 0.7,
    "max_tokens": 4096
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | array | *required* | Chat messages (role + content) |
| `stream` | bool | `true` | Enable SSE streaming |
| `model` | string | `{{ solver_model }}` | Model override |
| `session_id` | string | auto-generated | Conversation session ID |
| `owner_id` | string | `"default"` | User identifier |
| `dev_mode` | bool | `false` | Enable developer tools |
| `temperature` | float | `0.7` | Sampling temperature |
| `max_tokens` | int | `4096` | Maximum response tokens |

## Response (Non-Streaming)

```json
{
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1712764800,
    "model": "{{ solver_model }}",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Here's your response..."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 200,
        "total_tokens": 250
    },
    "metadata": {
        "intent": "CODE",
        "confidence": 0.92,
        "mars_score": 0.85,
        "trace_id": "trace-xyz789"
    }
}
```

## Response (Streaming)

With `"stream": true`, the response is Server-Sent Events:

```
data: {"event": "status", "data": "Classifying intent..."}

data: {"event": "status", "data": "Intent: CODE (0.92)"}

data: {"event": "thought", "data": "Analyzing the request..."}

data: {"event": "response", "data": "Here's the code:\n```python\n..."}

data: {"event": "response", "data": "```\n"}

data: [DONE]
```

### Event Types

| Event | Description |
|-------|-------------|
| `status` | Progress updates (intent classification, verification) |
| `thought` | Agent reasoning (visible in debug mode) |
| `response` | Content tokens |
| `tool_call` | Tool invocation details |
| `error` | Error information |

## Examples

### cURL

```bash
curl -X POST http://{{ turing_ip }}/swarm/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Write a Python fibonacci function"}],
        "stream": false
    }'
```

### Python

```python
import requests

response = requests.post(
    "http://{{ turing_ip }}/swarm/v1/chat/completions",
    json={
        "messages": [{"role": "user", "content": "Write a Python fibonacci function"}],
        "stream": False,
    },
)
print(response.json()["choices"][0]["message"]["content"])
```

### Python (Streaming)

```python
import requests

with requests.post(
    "http://{{ turing_ip }}/swarm/v1/chat/completions",
    json={
        "messages": [{"role": "user", "content": "Explain Docker"}],
        "stream": True,
    },
    stream=True,
) as resp:
    for line in resp.iter_lines():
        if line:
            print(line.decode())
```

## Error Responses

| Status | Description |
|--------|-------------|
| 400 | Invalid request body |
| 500 | Internal server error |
| 503 | Ollama unavailable |

```json
{
    "error": {
        "message": "Model not found: invalid-model",
        "type": "model_not_found",
        "code": 400
    }
}
```


