---
title: "Module: Router"
---

# Router

The Semantic Router is the entry point for all user requests. It classifies intent, issues capability tokens, and dispatches to the appropriate agent.

## Files

| File | Purpose |
|------|---------|
| `agents/semantic_router.py` | Intent classification (Nemotron LLM) |
| `agents/router.py` | Request handling, token issuance, dispatch |
| `agents/intent_capabilities.py` | Intent → capability mapping |

## Intent Classification

Uses {{ router_model }} to classify messages into 14 intents:

```python
INTENTS = [
    "CONVERSATION", "CODE", "DEVOPS", "DATA",
    "IMAGE", "3D", "ACTION_FIGURE",
    "RESEARCH", "DOCUMENTATION", "TRAIN",
    "IOT_CONTROL", "IOT_DEV", "VISION", "COORDINATE",
]
```

### Classification Prompt

The router sends a structured prompt to the LLM with:

- The user's message
- List of available intents with descriptions
- Instructions to return JSON: `{"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}`

### Fallback Logic

| Condition | Action |
|-----------|--------|
| Confidence ≥ 0.60 | Accept intent |
| Confidence < 0.60 | Retry with stronger prompt |
| Intent = AMBIGUOUS | Retry or ask disambiguation question |
| Timeout / error | Fallback to CONVERSATION |

## Token Issuance

After classification, the router generates a JWT-ACE token:

```python
token = issue_token(
    intent="CODE",
    tools=["file_ops", "terminal", "ast_tool"],
    level="L4",
    session_id=session_id,
    owner_id=owner_id,
)
```

## Dispatch Table

| Intent | Pipeline |
|--------|----------|
| CODE, CONVERSATION, DEVOPS, DATA, DOCUMENTATION | MarsRL Loop |
| IMAGE | Image Agent |
| 3D, ACTION_FIGURE | 3D Pipeline |
| COORDINATE, RESEARCH | Coordinator |
| IOT_CONTROL | IoT Agent |
| IOT_DEV | IoT Dev Agent |
| TRAIN | Memory System |
| VISION | Vision Agent |

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Router model | {{ router_model }} | Intent classification LLM |
| Min confidence | 0.60 | Below this triggers retry |
| Max retries | 2 | Classification retry limit |
| Timeout | 10s | LLM response timeout |

## Related

- [Architecture: Agent System](../architecture/agent-system.md) — design overview
- [Architecture: Data Flow](../architecture/data-flow.md) — request lifecycle


