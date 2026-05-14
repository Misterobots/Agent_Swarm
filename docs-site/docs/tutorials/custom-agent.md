---
title: "Tutorial: Create a Custom Agent"
---

# Create a Custom Agent

Build, register, and deploy your own specialized agent.

## What You'll Learn

- The agent interface and registration API
- How to implement custom logic
- How to integrate with existing tools

## Prerequisites

- Development environment set up (see [Local Development](../developer-guide/local-dev.md))
- Understanding of the agent architecture (see [Agent System](../architecture/agent-system.md))

## Step 1: Create the Agent File

Create `agents/my_agent.py`:

```python
from agents.lamport import Coordinator
from agents.logger_setup import get_logger

logger = get_logger("my_agent")


class MyAgent:
    """A custom agent that handles a specific domain."""

    def __init__(self):
        self.name = "my_agent"
        self.description = "Handles custom-domain tasks"

    async def handle(self, message: str, context: dict) -> str:
        """Process a user message and return a response."""
        logger.info(f"MyAgent handling: {message[:50]}...")

        # Your custom logic here
        # Use context for session info, owner_id, etc.

        result = await self._process(message, context)
        return result

    async def _process(self, message: str, context: dict) -> str:
        # Implement your logic
        return f"MyAgent processed: {message}"
```

## Step 2: Register the Intent

Add your agent's intent to the Router's capability map in `agents/intent_capabilities.py`:

```python
INTENT_MAP = {
    # ... existing intents ...
    "my_domain": {
        "agent": "my_agent",
        "description": "Handles custom-domain tasks",
        "examples": [
            "do my custom thing",
            "handle this special request",
        ],
    },
}
```

## Step 3: Wire the Handler

Follow the handler pattern documented in [Adding Agents](../developer-guide/adding-agents.md):

1. Create `agents/handlers/my_agent.py` as a generator function `handle_my_intent(user_input, ctx)`.
2. Add the dispatch case in `agents/church.py`:

```python
if intent == "MY_INTENT":
    from handlers.my_agent import handle_my_intent
    yield from handle_my_intent(user_input, ctx)
    return
```

If your agent needs to participate in multi-worker coordination, add a role entry in `agents/coordination/executor.py` — `_get_agent_for_role()` maps role strings to agent instances.

## Step 4: Add Tools (Optional)

If your agent needs tools, create them in `core_tools/`:

```python
# core_tools/my_tool.py
class MyTool:
    name = "my_tool"
    description = "Does a specific thing"

    async def execute(self, params: dict) -> dict:
        # Tool logic
        return {"result": "done"}
```

## Step 5: Test

```bash
# Send a test message
curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "do my custom thing"}]
    }'
```

Verify your agent handles the request by checking logs and Langfuse traces.

## Step 6: Deploy

Rebuild and restart the agent runtime:

```bash
cd execution_plane
docker compose build agent-runtime
docker compose up -d agent-runtime
```

## Next Steps

- [Developer Guide: Adding Agents](../developer-guide/adding-agents.md) — detailed guide
- [Developer Guide: Adding Tools](../developer-guide/adding-tools.md) — tool development


