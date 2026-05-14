---
title: Adding Agents
---

# Adding Agents

How to create a new specialized agent in Memex.

## Overview

To add a new agent, you need:

1. An agent class or a handler generator function
2. A new intent in the Semantic Router (or map to an existing one)
3. A handler module in `agents/handlers/`
4. Router dispatch wiring in `church.py`
5. A JWT-ACE capability profile

> **Handler pattern**: Since the May 2026 refactor, all dispatch logic lives in `agents/handlers/<name>.py` as a generator function `handle_X(user_input: str, ctx: dict)`. `church.py` is a thin wrapper that calls `yield from handle_X(...)`. See [ADR-005](../architecture/decisions/adr-005-church-handlers.md).

## Step 1: Create the Agent

Create a new file in `agents/specialized/`:

```python
# agents/specialized/my_agent.py
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class MyAgentResult:
    response: str
    metadata: dict


class MyAgent:
    """Handles MY_INTENT requests."""

    def __init__(self, config):
        self.config = config
        self.ollama_url = config.get("ollama_url", "http://localhost:11434")

    async def run(
        self,
        messages: list[dict],
        session_id: str,
        token: Optional[str] = None,
    ) -> MyAgentResult:
        """Process the user request."""
        user_message = messages[-1]["content"]
        logger.info(f"MyAgent processing: {user_message[:50]}...")

        # Your agent logic here
        result = await self._process(user_message)

        return MyAgentResult(
            response=result,
            metadata={"agent": "my_agent", "session_id": session_id},
        )

    async def _process(self, message: str) -> str:
        # Implementation
        return f"Processed: {message}"
```

## Step 2: Add Intent (Optional)

If your agent needs a new intent, update the Semantic Router:

```python
# In agents/semantic_router.py, add to the intent list:
INTENTS = [
    # ... existing intents ...
    "MY_INTENT",
]
```

Update the router prompt to include the new intent description.

## Step 3: Create a Handler Module

Create `agents/handlers/my_agent.py` as a generator:

```python
# agents/handlers/my_agent.py
import logging
from metrics import AGENT_STATE, WORKFLOW_STEPS
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace

logger = logging.getLogger("Router")


def handle_my_intent(user_input: str, ctx: dict):
    """Generator — MY_INTENT handler."""
    turn_id = ctx["turn_id"]
    session_id = ctx["session_id"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    yield _emit_turn_metadata(turn_id, "MyAgent", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "⚙️ MyAgent: Running..."}
    AGENT_STATE.labels(agent_name="MyAgent").set(2)

    from specialized.my_agent import MyAgent
    agent = MyAgent()

    try:
        result = agent.run(user_input)
        yield {"type": "response", "content": result}
        _score_trace(lf_trace, langfuse, 1.0, output=result, use_langfuse=use_langfuse)
    except Exception as e:
        yield {"type": "error", "content": f"MyAgent error: {e}"}
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    AGENT_STATE.labels(agent_name="MyAgent").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="MyAgent").inc()
```

## Step 4: Wire Dispatch in church.py

In `agents/church.py`, add the dispatch case to the handler dispatch block:

```python
if intent == "MY_INTENT":
    from handlers.my_agent import handle_my_intent
    yield from handle_my_intent(user_input, ctx)
    return
```

The `ctx` dict is already built by `chat_swarm()` — it carries session state, history, Langfuse handles, MarsRL tuning params, and everything else the handler needs.

## Step 4: Define Capabilities

Add the JWT-ACE capability profile in `agents/intent_capabilities.py`:

```python
INTENT_CAPABILITIES = {
    # ... existing intents ...
    "MY_INTENT": {
        "tools": ["search", "custom_tool"],
        "level": "L3",
    },
}
```

## Step 5: Add Tests

```python
# tests/test_my_agent.py
import pytest
from agents.specialized.my_agent import MyAgent


@pytest.mark.asyncio
async def test_my_agent_basic():
    config = {"ollama_url": "http://localhost:11434"}
    agent = MyAgent(config)
    result = await agent.run(
        messages=[{"role": "user", "content": "test input"}],
        session_id="test-session",
    )
    assert result.response
    assert result.metadata["agent"] == "my_agent"
```

## Using MarsRL Verification

If your agent should use MarsRL quality verification:

```python
from agents.mars_loop import MarsRLLoop

class MyAgent:
    async def run(self, messages, session_id, token):
        mars = MarsRLLoop(config=self.config)
        result = await mars.run(
            messages=messages,
            intent="MY_INTENT",
            session_id=session_id,
            token=token,
        )
        return result
```

## Agent Design Guidelines

- Keep agents focused on one intent or capability
- Use async/await for all I/O operations
- Log with contextual information: `logger.info(f"... session={session_id}")`
- Return structured results (dataclass), not raw strings
- Handle errors gracefully — return error info in the result, don't crash

## Related

- [Architecture: Agent System](../architecture/agent-system.md) — agent architecture
- [Developer: Adding Tools](adding-tools.md) — create tools for agents
- [Architecture: MarsRL](../architecture/marsrl.md) — quality verification


