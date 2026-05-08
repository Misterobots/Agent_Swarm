---
title: "Module: Memory"
---

# Memory

Agent-side memory implementation. Covers the local, in-process subsystems
(Skills Memory, Preferences, Session Context) plus the HTTP integration
into the networked [MemPalace service](services/mempalace.md).

## Files

| File | Purpose |
|------|---------|
| `agents/memory_system.py` | Skills Memory — rule-based knowledge |
| `agents/preferences.py` | Per-user preferences |
| `agents/context_manager.py` | Session context lifecycle |
| `agents/main.py` (`_mempalace_extract_http`) | HTTP caller for `/v1/extract` |
| `agents/mempalace_client.py` | Legacy embedded-library client (one residual caller; deprecation candidate) |

## Skills Memory

File-backed JSON store at `agents/skills_memory.json`.

### Domains

| Domain | Examples |
|--------|----------|
| `visual_rules` | Art style hints — "cyberpunk: neon lighting" |
| `coding_rules` | Code conventions — "use type hints" |
| `general_rules` | Communication style — "be concise" |
| `session_summaries` | Auto-generated conversation recaps |

### API

```python
memory = SkillsMemory()
memory.add_rule("coding_rules", "python", "Always use f-strings for formatting")
rules = memory.get_relevant_rules("Write a Python function", "coding_rules")
summaries = memory.get_recent_summaries(n=5, owner_id="user_001")
```

## Session Context

Active conversation state persisted in `agents/context_sessions/`:

```python
context = ContextManager()
session = context.get_session(session_id)
session.add_message({"role": "user", "content": "Hello"})
history = session.get_messages()
```

## Preferences

Per-user configuration:

```python
prefs = Preferences()
prefs.set("user_001", "response_style", "concise")
prefs.set("user_001", "default_model", "{{ solver_model }}")
style = prefs.get("user_001", "response_style")  # "concise"
```

## TRAIN intent → MemPalace integration

When a user says "Remember that I prefer bullet points", the router
classifies it as `TRAIN` and writes to two places:

1. **Skills Memory** as a rule:
   ```python
   memory.add_rule("general_rules", "format", "Use bullet points in responses")
   ```
2. **MemPalace** as a procedural memory (semantic recall in future sessions):
   ```python
   mempalace_client.store(
       content="format: Use bullet points in responses",
       memory_type="procedural",
       domain="general",
       owner_id=owner_id,
   )
   ```

The MemPalace write currently goes through `agents/mempalace_client.py`
in a `try/except: pass` fallback — it's a legacy embedded-library client
that survives only for this one caller. The dominant integration is the
HTTP call to `MEMPALACE_API_URL` (`http://{{ hopper_ip }}:8200`) used by
`agents/main.py:_mempalace_extract_http` after each turn.

## Per-turn extraction

After every model response completes, `agents/main.py` POSTs a short
conversation summary to `MEMPALACE_API_URL/v1/extract`:

```python
async def _mempalace_extract_http(conversation: str, owner_id: str | None) -> int:
    """POST conversation text to the MemPalace /v1/extract endpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_MEMPALACE_API_URL}/v1/extract",
            json={"conversation": conversation, "owner_id": owner_id},
        )
        return len(resp.json())
```

MemPalace runs the conversation through an LLM extractor, embeds the
resulting facts, and persists everything in a single transaction
alongside an extraction-attempt audit row. See
[MemPalace Deep Dive — Extraction Pipeline](../architecture/mempalace-deep-dive.md#data-flow-extraction-pipeline).

## Related

- [Architecture: Memory System](../architecture/memory-system.md) — design overview of all four subsystems
- [Module: MemPalace Service](services/mempalace.md) — operator reference
- [MemPalace API Reference](../developer-guide/api/mempalace.md) — full HTTP contracts
- [User Guide: Settings](../user-guide/settings.md) — user-facing memory management
- [Memory Palace UI](../user-guide/palace.md) — 3D viewer
