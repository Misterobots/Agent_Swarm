---
title: "MemPalace Integration Deep Dive"
---

# MemPalace Integration — Architecture Deep Dive

```
Document ID: ARCH-MEM-001
Domain: Architecture
Owner: Core Platform
Status: Approved
Version: 2.0
Last Updated: 2026-04-16
```


---

## Purpose

Documents the integration of the official [MemPalace](https://github.com/mempalace/mempalace) library (v3.3.0+) as the agent memory subsystem. Replaces the previous custom pgvector HTTP service with an embedded ChromaDB-backed palace architecture.

---

## Source References

| Source | Type | Relevance |
|--------|------|-----------|
| [MemPalace Library](https://github.com/mempalace/mempalace) | Open source (pip) | Core dependency — palace hierarchy, ChromaDB backend, KnowledgeGraph |
| [ChromaDB](https://github.com/chroma-core/chroma) | Open source | Underlying vector store used by MemPalace for drawer persistence |
| [Method of Loci](https://en.wikipedia.org/wiki/Method_of_loci) | Cognitive science | Memory palace spatial metaphor that MemPalace implements |
| [Semantic Memory in AI Agents (Park et al., 2023)](https://arxiv.org/abs/2304.03442) | Research paper | Generative agent memory architecture with retrieval |
| [pgvector](https://github.com/pgvector/pgvector) | Open source | Previous vector store (replaced by ChromaDB in v2) |

---

## Changelog: Source → Hive Implementation

This table documents what was adopted from the official MemPalace library and what was customized for the Hive.

<details markdown>
<summary><strong>View full changelog table</strong> (click to expand)</summary>

| Feature | MemPalace Library (v3.3.0) | Hive Implementation | Delta |
|---------|---------------------------|---------------------|-------|
| Palace hierarchy | Wing → Hall → Room → Drawer | Wing → Hall → Drawer (skip Room) | Simplified — Room layer auto-created but not exposed |
| Wing derivation | Manual wing names | Auto-derived from agent name (`"Code Developer"` → `"Code_Developer"`) | Automatic mapping, no manual config |
| Hall mapping | Free-form hall names | Fixed set of 6 halls mapped from `memory_type` | Constrained to known categories |
| ChromaBackend | Default persistent client | Configured with `MEMPALACE_DATA_DIR` env var | Environment-driven path |
| KnowledgeGraph | SQLite-backed, full API | Wrapped as `team_store/team_get/team_search/team_clear` | Simplified team-scoped API |
| Diary / snapshots | CLI commands | Wrapped `save_snapshot()` / `get_snapshot()` with fallback | Graceful degradation if CLI unavailable |
| Error handling | Raises exceptions | All methods catch exceptions, return safe defaults | Never propagates errors to callers |
| Initialization | Explicit `Palace()` constructor | Singleton `MemPalaceClient` with lazy init | One instance per process |
| Search | `search_memories(query, n)` | `search(query, agent_name, memory_type, limit)` with wing/hall scoping | Scoped search per agent + type |
| `extract()` | Not in base library | Custom fact extraction using LLM (optional) | Added intelligence layer |

</details>

---

## Architecture Overview

<details markdown>
<summary><strong>Architecture Diagram</strong> (click to expand)</summary>

```
┌─────────────────────────────────────────────────────┐
│                 Agent Layer                           │
│   router.py  ·  coordinator.py  ·  main.py           │
│       ↓              ↓                ↓              │
│       └──────── mempalace_client.py ─────────┘       │
│                     │                                 │
│           ┌─────────┴──────────┐                     │
│           │  MemPalace Library  │                     │
│           │  (pip install)      │                     │
│           ├─────────────────────┤                     │
│           │ ChromaBackend       │ ← Drawer storage   │
│           │ search_memories()   │ ← Semantic search   │
│           │ KnowledgeGraph      │ ← Team memory       │
│           │ Diary / CLI         │ ← Snapshots         │
│           └─────────────────────┘                     │
│                     │                                 │
│           ┌─────────┴──────────┐                     │
│           │ ChromaDB (embedded) │                     │
│           │ SQLite (KG)         │                     │
│           └────────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

</details>

No separate memory server is required. MemPalace runs embedded in the agent process.

---

## Palace Hierarchy

MemPalace organizes memory in a spatial metaphor:

| Level | Concept | Mapped to |
|-------|---------|-----------|
| **Palace** | Top-level container | One per Hive instance |
| **Wing** | Agent or team grouping | Agent name (e.g., `Code_Developer`) or team ID |
| **Hall** | Memory category | `conversations`, `decisions`, `code_patterns`, `errors`, `tasks`, `general` |
| **Room** | Not used (library creates auto) | — |
| **Drawer** | Individual memory unit | One ChromaDB document per memory |

### Memory Type → Hall Mapping

| `memory_type` | Hall |
|----------------|------|
| `conversation` | `conversations` |
| `decision` | `decisions` |
| `code` | `code_patterns` |
| `error` | `errors` |
| `task` | `tasks` |
| *(default)* | `general` |

### Wing Derivation

Wings are derived from agent names:

```python
"Code Developer"  → "Code_Developer"
"Art Director"    → "Art_Director"
"team:research-1" → "team_research_1"
```

---

## Client API

The `MemPalaceClient` singleton (`agents/mempalace_client.py`) exposes this interface:

<details markdown>
<summary><strong>Full Client API — Individual Memory</strong> (click to expand)</summary>

| Method | Signature | Description |
|--------|-----------|-------------|
| `store()` | `(content, agent_name, memory_type, metadata)` | Store a memory in the appropriate wing/hall/drawer |
| `search()` | `(query, agent_name, memory_type, limit) → list[dict]` | Semantic search across an agent's memories |
| `delete()` | `(memory_id) → bool` | Delete a specific memory by ID |
| `stats()` | `() → dict` | Collection statistics (count, palace name) |
| `extract()` | `(text, agent_name) → list[dict]` | Extract structured facts from raw text |

</details>

<details markdown>
<summary><strong>Full Client API — Snapshots</strong> (click to expand)</summary>

| Method | Signature | Description |
|--------|-----------|-------------|
| `save_snapshot()` | `(tag) → dict` | Save current palace state (CLI-based) |
| `get_snapshot()` | `(tag) → dict` | Retrieve a saved snapshot |

</details>

<details markdown>
<summary><strong>Full Client API — Team Memory (KnowledgeGraph)</strong> (click to expand)</summary>

| Method | Signature | Description |
|--------|-----------|-------------|
| `team_store()` | `(team_id, key, value, author_agent)` | Store a team-scoped fact |
| `team_get()` | `(team_id, key) → str or None` | Retrieve a team fact by key |
| `team_search()` | `(team_id, query) → list[dict]` | Search team facts |
| `team_clear()` | `(team_id)` | Clear all facts for a team |

</details>

### Health

| Method | Signature | Description |
|--------|-----------|-------------|
| `healthy()` | `() → bool` | Check if MemPalace library is importable and configured |

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MEMPALACE_PALACE_NAME` | `"agent_swarm"` | Palace instance name |
| `MEMPALACE_DATA_DIR` | `"~/.mempalace"` | ChromaDB + SQLite storage directory |

No API keys, URLs, or external services required.

---

## Usage in Agent System

### Router (Contextual Memory)

```python
# agents/router.py — After response generation
from mempalace_client import mempalace

mempalace.store(
    content=f"User asked: {user_input}\nResponse: {response_text}",
    agent_name="Code Developer",
    memory_type="conversation",
    metadata={"session_id": session_id, "intent": intent},
)
```

### Coordinator (Team Memory)

```python
# agents/coordinator.py — Research phase
mempalace.team_store(
    team_id=coordination_id,
    key=f"research_{role}_{worker_id}",
    value=result[:2000],
    author_agent=role,
)

# Synthesis phase — read all team findings
findings = mempalace.team_search(coordination_id, user_input)
```

### Search (Context Injection)

```python
# Enrich agent prompt with relevant past memories
relevant = mempalace.search(
    query=user_input,
    agent_name="Code Developer",
    memory_type="conversation",
    limit=5,
)
context = "\n".join(m["content"] for m in relevant)
```

---

## Fallback Behavior

The client gracefully degrades:

1. **Library not installed** → `healthy()` returns `False`, all operations return empty/safe defaults.
2. **ChromaDB error** → Falls back to raw `chromadb.Client()` for drawer operations.
3. **KnowledgeGraph error** → Team operations log warnings and return `None`/`[]`.
4. **CLI unavailable** → Snapshot operations return `{"status": "unavailable"}`.

No operation raises an exception to callers.

---

## Migration from v1 (HTTP Client)

<details markdown>
<summary><strong>Migration Comparison Table</strong> (click to expand)</summary>

| Aspect | v1 (Old) | v2 (Current) |
|--------|----------||--------------|
| Backend | pgvector HTTP service on port 9200 | Embedded ChromaDB |
| Protocol | HTTP REST via httpx | Python library calls |
| Persistence | PostgreSQL with pgvector | ChromaDB files + SQLite |
| Team memory | Not supported | KnowledgeGraph (SQLite) |
| External dependency | Separate Docker container | `pip install mempalace` |
| Failure mode | Connection errors | Graceful ImportError fallback |

</details>

### Deployment

The `mempalace` package is included in the execution plane Dockerfile:

```dockerfile
RUN pip install mempalace  # Added to agents dependency block
```

---

## Maintenance & Update Guide

### Updating the MemPalace Library

```bash
# Check current version
pip show mempalace

# Update to latest
pip install --upgrade mempalace

# Verify compatibility
python -c "from mempalace import Palace, ChromaBackend, KnowledgeGraph; print('OK')"
```

After updating, run the test suite (see Functionality Testing below) to verify no API breaking changes.

### Adding New Hall Types

To add a new memory category (e.g., `"feedback"` hall):

1. Add the mapping in `agents/mempalace_client.py` in the `_HALL_MAP` dictionary:
   ```python
   _HALL_MAP = {
       "conversation": "conversations",
       "feedback": "feedback",  # new
       ...
   }
   ```
2. Callers can now use `mempalace.store(content, agent, memory_type="feedback")`.

### Adding New Agent Wings

Wings are auto-derived from agent names. No configuration needed — new agents automatically get their own wing.

### Managing ChromaDB Storage

```bash
# Check storage size
du -sh ~/.mempalace/

# Back up
tar czf mempalace_backup_$(date +%Y%m%d).tar.gz ~/.mempalace/

# Clear all data (destructive)
rm -rf ~/.mempalace/chroma/  # Removes all vector data
rm -f ~/.mempalace/*.db        # Removes KnowledgeGraph
```

### Modifying Fallback Behavior

All methods use try/except with safe defaults. To change fallback behavior (e.g., raise instead of suppress), edit the error handling in `agents/mempalace_client.py`.

---

## Functionality Testing

### Running Existing Tests

```bash
pytest tests/test_mempalace_client.py -v
```

The test suite uses mocks for the MemPalace library internals and verifies:
- Singleton initialization
- `store()` routes to correct wing/hall
- `search()` returns properly formatted results
- `team_store()` / `team_get()` delegation to KnowledgeGraph
- Fallback behavior when library is unavailable
- `healthy()` status reporting

### Manual Verification

| Test Case | Command / Steps | Expected Result |
|-----------|----------------|----------------|
| Store memory | `curl -X POST http://localhost:8008/v1/memory -d '{"content": "test", "agent_name": "tester", "memory_type": "conversation"}'` | 200 OK, memory stored |
| Search memory | `curl http://localhost:8008/v1/memory/search?query=test&agent=tester` | Returns matching memories |
| Health check | `curl http://localhost:8008/v1/memory/health` | `{"healthy": true}` |
| Stats | `curl http://localhost:8008/v1/memory/stats` | Collection count and palace name |
| Team store | Use coordinator with COORDINATE intent | Team facts stored in KnowledgeGraph |

### Integration Test (ChromaDB Persistence)

```bash
# Store a memory, restart the process, verify it persists
python -c "
from agents.mempalace_client import mempalace
mempalace.store('integration test', 'test_agent', 'conversation')
results = mempalace.search('integration', 'test_agent')
assert len(results) > 0, 'Memory not found'
print(f'Found {len(results)} result(s) - PASS')
"
```

---

<details markdown>
<summary><strong>Source of Truth</strong> (click to expand)</summary>

| Component | File |
|-----------|------|
| MemPalace client singleton | `agents/mempalace_client.py` |
| Unit tests | `tests/test_mempalace_client.py` |
| Dockerfile dependency | `execution_plane/Dockerfile` |
| Router usage | `agents/router.py` (L672, L1635) |
| Coordinator usage | `agents/coordinator.py` (L38, L46) |
| API endpoints | `agents/main.py` (L999, L1060) |

</details>
