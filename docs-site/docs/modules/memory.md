---
title: "Module: Memory"
---

# Memory

Persistent knowledge storage: Skills Memory, session management, and preferences.

## Files

| File | Purpose |
|------|---------|
| `agents/memory_system.py` | Skills Memory (rule-based knowledge) |
| `agents/preferences.py` | User preference storage |
| `agents/context_manager.py` | Session context management |
| `agents/mempalace_client.py` | MemPalace API client (semantic search) |

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

# Add a rule
memory.add_rule("coding_rules", "python", "Always use f-strings for formatting")

# Get relevant rules for a prompt
rules = memory.get_relevant_rules("Write a Python function", "coding_rules")

# Get recent summaries
summaries = memory.get_recent_summaries(n=5, owner_id="user_001")
```

## Session Context

Active conversation state persisted in `agents/context_sessions/`:

```python
context = ContextManager()

# Create/get session
session = context.get_session(session_id)

# Add message
session.add_message({"role": "user", "content": "Hello"})

# Get history
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

## TRAIN Intent

When a user says something like *"Remember that I prefer bullet points"*, the router classifies this as `TRAIN` and writes to Skills Memory:

```python
memory.add_rule("general_rules", "format", "Use bullet points in responses")
```

## Related

- [Architecture: Memory System](../architecture/memory-system.md) — design overview
- [Module: MemPalace Service](services/mempalace.md) — semantic memory
- [User Guide: Settings](../user-guide/settings.md) — user-facing memory management


