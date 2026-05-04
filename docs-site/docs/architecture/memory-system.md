---
title: Memory System
---

# Memory System

Memex provides persistent knowledge storage across sessions through multiple memory subsystems.

## Architecture

```mermaid
graph TB
    subgraph Local["Local Memory · Execution Node"]
        SM[Skills Memory<br/>skills_memory.json]
        Prefs[User Preferences<br/>preferences.py]
        Sessions[Session Context<br/>context_sessions/]
    end

    subgraph Remote["Remote Memory · Control Node"]
        MP[MemPalace<br/>Semantic Memory]
        PG[(PostgreSQL<br/>pgvector)]
    end

    Agent --> SM
    Agent --> Prefs
    Agent --> Sessions
    Agent --> MP
    MP --> PG
```

## Skills Memory

The primary persistent knowledge base. Stores learned rules and session summaries.

### Structure

```json
{
    "visual_rules": {
        "cyberpunk": ["neon lighting", "rain-slicked streets"],
        "portrait": ["soft lighting", "shallow depth of field"]
    },
    "coding_rules": {
        "python": ["use type hints", "prefer dataclasses"],
        "error_handling": ["log with context", "use specific exceptions"]
    },
    "general_rules": {
        "tone": ["be concise", "use bullet points"]
    },
    "session_summaries": [
        {
            "date": "2026-04-10",
            "topic": "GRPO training pipeline",
            "summary": "Configured batch size and learning rate...",
            "owner_id": "user_001"
        }
    ]
}
```

### API

| Method | Description |
|--------|-------------|
| `add_rule(domain, keyword, rule)` | Add a rule to a domain |
| `get_relevant_rules(prompt, domain)` | Keyword-match rules against a prompt |
| `get_all_rules()` | Retrieve the full knowledge base |
| `add_session_summary(date, topic, summary, owner_id)` | Save a session recap |
| `get_recent_summaries(n, owner_id)` | Retrieve recent session summaries |

### Storage

File: `/workspace/agents/skills_memory.json` (persisted via Docker volume mount)

## MemPalace

Semantic memory service running on the Control Node. Provides vector-based similarity search for knowledge retrieval.

| Property | Value |
|----------|-------|
| **URL** | `http://{{ hopper_ip }}:8200` |
| **Backend** | PostgreSQL with pgvector extension |
| **Embedding** | Sentence transformers |

MemPalace stores and retrieves knowledge based on semantic similarity rather than keyword matching, complementing the rules-based Skills Memory.

## Session Context

Active conversation state. Stored in `agents/context_sessions/` as JSON files, one per session ID.

Sessions track:

- Message history
- Active tools
- Scratchpad artifacts (Coordinator sessions)
- JWT-ACE token metadata

## User Preferences

The `preferences.py` module stores per-user configuration:

- Default model selection
- Response style preferences
- Memory enable/disable flags

Teaching preferences via chat:

> *"Remember that I prefer concise answers with code examples"*

This is routed to `TRAIN` intent and writes to `general_rules` in Skills Memory.

## Key Files

| File | Purpose |
|------|---------|
| `agents/memory_system.py` | Skills Memory  rule storage and retrieval |
| `agents/preferences.py` | User preference management |
| `agents/mempalace_client.py` | MemPalace API client |
| `control_plane/mempalace/` | MemPalace service (Control Node) |

## Related

- [Getting Started: Concepts](../getting-started/concepts.md)  simplified overview
- [Module: Memory](../modules/memory.md)  implementation reference
- [Module: MemPalace Service](../modules/services/mempalace.md)
- [User Guide: Settings](../user-guide/settings.md)  teaching preferences


