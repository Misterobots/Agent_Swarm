---
title: Adding Agents
---

# Adding Agents

How to create a new specialized agent in Agent Swarm.

## Overview

To add a new agent, you need:

1. An agent class with a `run()` method
2. A new intent in the Semantic Router (or map to an existing one)
3. Router dispatch wiring
4. A JWT-ACE capability profile

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

## Step 3: Wire Dispatch

In `agents/router.py`, add the dispatch case:

```python
# In the route_request() method:
elif intent == "MY_INTENT":
    from agents.specialized.my_agent import MyAgent
    agent = MyAgent(self.config)
    result = await agent.run(messages, session_id, token)
    return result.response
```

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
