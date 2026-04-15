---
title: Models API
---

# Models API

List available models.

## List Models

```
GET /v1/models
```

### Response

```json
{
    "object": "list",
    "data": [
        {
            "id": "{{ solver_model }}",
            "object": "model",
            "owned_by": "ollama",
            "permission": []
        },
        {
            "id": "{{ router_model }}",
            "object": "model",
            "owned_by": "ollama",
            "permission": []
        },
        {
            "id": "{{ verifier_model }}",
            "object": "model",
            "owned_by": "ollama",
            "permission": []
        }
    ]
}
```

### Example

```bash
curl http://{{ gateway_node_ip }}/swarm/v1/models | python -m json.tool
```

This endpoint proxies to the Ollama `/api/tags` endpoint and transforms the response to OpenAI format.
