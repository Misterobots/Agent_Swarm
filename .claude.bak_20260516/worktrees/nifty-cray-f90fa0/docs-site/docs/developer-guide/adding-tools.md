---
title: Adding Tools
---

# Adding Tools

How to create new tools that agents can use during execution.

## Tool Structure

Tools are Python functions registered in the tool registry. Each tool has:

- A name (used in JWT-ACE capability tokens)
- A description (shown to the LLM for tool selection)
- An implementation function

## Create a Tool

```python
# agents/tools/my_tool.py
import logging

logger = logging.getLogger(__name__)


def my_tool(param1: str, param2: int = 10) -> dict:
    """
    Description shown to the LLM when selecting tools.

    Args:
        param1: What this parameter does
        param2: Optional parameter with default
    
    Returns:
        Result dictionary with output data
    """
    logger.info(f"my_tool called: param1={param1}, param2={param2}")

    # Tool implementation
    result = do_something(param1, param2)

    return {
        "status": "success",
        "output": result,
    }
```

## Register the Tool

Add the tool to the tool registry in `agents/tools/__init__.py`:

```python
from agents.tools.my_tool import my_tool

TOOL_REGISTRY = {
    # ... existing tools ...
    "my_tool": {
        "function": my_tool,
        "description": "Does something useful with the given parameters",
        "parameters": {
            "param1": {"type": "string", "required": True},
            "param2": {"type": "integer", "required": False, "default": 10},
        },
    },
}
```

## Add to Capability Profiles

Update `agents/intent_capabilities.py` to allow specific intents to use the tool:

```python
INTENT_CAPABILITIES = {
    "CODE": {
        "tools": ["file_ops", "terminal", "ast_tool", "my_tool"],
        "level": "L4",
    },
}
```

## Existing Tools

| Tool | File | Purpose |
|------|------|---------|
| `file_ops` | `tools/file_ops.py` | Read, write, list files |
| `terminal` | `tools/terminal.py` | Execute shell commands |
| `ast_tool` | `tools/ast_tool.py` | Python AST analysis |
| `search` | `tools/search.py` | Web and document search |
| `ha_call_service` | `tools/ha_tools.py` | Home Assistant service calls |
| `ha_turn_on` | `tools/ha_tools.py` | Home Assistant device on |
| `ha_turn_off` | `tools/ha_tools.py` | Home Assistant device off |
| `mqtt_publish` | `tools/mqtt_tools.py` | MQTT message publishing |

## Security Considerations

- Tools are gated by JWT-ACE tokens — an agent can only call tools listed in its token
- Dangerous operations (file deletion, shell commands) should validate inputs
- Never execute user input directly — sanitize and validate
- Log all tool invocations with contextual info for audit trails

## Testing Tools

```python
# tests/test_my_tool.py
from agents.tools.my_tool import my_tool


def test_my_tool_basic():
    result = my_tool(param1="test", param2=5)
    assert result["status"] == "success"
    assert "output" in result


def test_my_tool_default_param():
    result = my_tool(param1="test")
    assert result["status"] == "success"
```

## Related

- [Developer: Adding Agents](adding-agents.md) — create agents that use tools
- [Architecture: Security Model](../architecture/security-model.md) — capability gating


