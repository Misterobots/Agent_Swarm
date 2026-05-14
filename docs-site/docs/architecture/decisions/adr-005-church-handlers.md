---
title: "ADR-005: church.py Handler Package"
---

# ADR-005: church.py Handler Package

**Status**: Accepted  
**Date**: 2026-05

## Context

`agents/church.py` is the main dispatch generator for every user request. Over time it accumulated all intent handlers inline, growing to **3,173 lines** in a single file. This created several operational problems:

- **Merge conflicts**: Any two features touching different intents still landed in the same file
- **Context explosion**: Reading or reviewing the router required holding the entire file in mind
- **Test isolation impossible**: Unit-testing one handler meant importing the full church.py initialization chain (Langfuse, JWT-ACE, PgStorage, etc.)
- **Deployment risk**: A syntax error anywhere in the file took down all intent routing
- **Onboarding friction**: New team members had no obvious seam to start from when adding a handler

The file had grown organically through several major feature additions (MarsRL loop, design studio, action figure pipeline, doc standards, dev-mode gate, pending context types) and had never been decomposed.

## Decision

Decompose `church.py` into a **thin wrapper + handler package**:

```
agents/church.py          # ~500 lines — session init, routing, ctx dict, dispatch
agents/handlers/
    __init__.py
    base.py               # shared emitters, Langfuse helpers, RAG utilities
    architect.py          # ARCHITECT / CODE default
    conversation.py       # CONVERSATION
    coordinate.py         # COORDINATE
    devops.py             # DEVOPS, DATA, AMBIGUOUS
    image.py              # IMAGE
    media.py              # 3D, ACTION_FIGURE
    research.py           # RESEARCH, DOCUMENTATION, DOC_STANDARDS
    design.py             # DESIGN
    train.py              # TRAIN, IOT_CONTROL
    vision.py             # VISION
agents/routing/
    __init__.py
    gates.py              # pending-context dispatch (9 multi-turn types)
```

### Handler Contract

Every handler is a **generator function** with a fixed signature:

```python
def handle_X(user_input: str, ctx: dict):
    """Generator — yields SSE events."""
    yield {"type": "status", "content": "..."}
    yield {"type": "response", "content": "..."}
```

The `ctx` dict carries all shared state (session ID, history, Langfuse handles, JWT-ACE token, MarsRL tuning params) and is built once in `chat_swarm()` before dispatch.

### Dispatch in church.py

```python
if intent == "IMAGE":
    from handlers.image import handle_image
    yield from handle_image(user_input, ctx)
    return
# ... one block per intent ...
from handlers.architect import handle_architect
yield from handle_architect(user_input, ctx)  # default
```

All imports are **lazy** (inside the `if` block) to avoid circular imports — handlers may call back into church.py helpers (`_resolve_model_for_intent`, `_is_admin_session`, etc.).

### Pending Context Dispatch

Multi-turn state (clarification answers, onboarding steps, intent gates) is handled by `routing/gates.py` **before** intent classification runs. The generator updates a mutable `result` dict:

```python
_pending_result = {"handled": False, "user_input": user_input}
yield from handle_pending_context(pending_ctx, user_input, ..., result=_pending_result)
if _pending_result["handled"]:
    return
user_input = _pending_result["user_input"]
```

### Shared Utilities in handlers/base.py

`_score_trace` and `_langfuse_span` moved to `handlers/base.py` with explicit `use_langfuse=` kwargs. `church.py` keeps thin wrappers that inject the module-level `USE_LANGFUSE` and `langfuse` variables so call sites in the rest of the file are unchanged.

## Consequences

### Positive

- **3,173 → ~500 lines** in church.py; each handler averages 70–130 lines
- **Independent reviewability**: Adding or changing an intent handler is a focused, single-file diff
- **Test isolation**: Handler tests can import just `handlers/image.py` without triggering the full church.py init chain
- **Deployment safety**: A bug in one handler file does not prevent other intents from loading
- **Clear extension point**: Adding a new intent is documented as "create `handlers/X.py`, add one `if intent == "X":` block in church.py"
- **Public API preserved**: `chat_swarm()`, `handle_task_event()`, `run_swarm()`, and all helper functions remain at the same import path

### Negative

- **More files to navigate**: 12 new files instead of one; requires knowing the handler → intent mapping
- **Lazy import overhead**: First call to each handler pays a small import cost (one-time per process)
- **ctx dict is untyped**: The plain dict contract is convenient but not enforced; a typo in a key name fails at runtime rather than at type-check time

### Neutral

- The monolith line count reduction (3,173 → ~500) happened alongside a lamport.py → `agents/coordination/` refactor completed in the same phase
- All handlers were smoke-tested inside the running Docker container (`agent_runtime`) before merging

## Related

- [Module: Router](../../modules/router.md) — current file layout and dispatch table
- [Architecture: Agent System](../agent-system.md) — handler package in context
- [Developer Guide: Adding Agents](../../developer-guide/adding-agents.md) — step-by-step for new handlers
- `agents/church.py` — source (thin wrapper)
- `agents/handlers/` — handler modules
- `agents/routing/gates.py` — pending-context dispatch
