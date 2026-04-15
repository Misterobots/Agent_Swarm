---
title: Settings
---

# Settings

Configure user preferences, model selection, and system behavior.

## How to Access

- **UI**: Navigate to **Settings** in the Hive Mind sidebar

## User Preferences

| Setting | Description |
|---------|-------------|
| **Default Model** | Choose the default model for new conversations |
| **Memory** | Enable/disable persistent conversation memory |
| **Theme** | Light or dark mode for the Hive UI |
| **Response Style** | Preferred response format (concise, detailed, technical) |

### Teaching Preferences via Chat

You can teach the system your preferences through conversation:

> *"Remember that I prefer Python with type hints and Google-style docstrings"*

This is classified as `TRAIN` intent and updates the memory system's rules:

```json
{
  "coding_rules": {
    "python": ["use type hints", "use Google-style docstrings"]
  }
}
```

The system applies these rules when generating future responses.

### Memory Domains

Preferences are stored in three domains:

| Domain | Examples |
|--------|---------|
| `visual_rules` | Image styles, color preferences |
| `coding_rules` | Language conventions, framework preferences |
| `general_rules` | Tone, verbosity, formatting |

## Related

- [Module: Memory](../modules/memory.md) — memory system internals
- [Module: Preferences](../modules/memory.md) — user preference storage
