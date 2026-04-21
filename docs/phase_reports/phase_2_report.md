# Phase 2: MemPalace Memory Integration — Completion Report

**Date:** 2026-04-13
**Tag:** `phase-2-complete`

## Summary

Phase 2 adds hierarchical semantic memory to the Agent Swarm via MemPalace, a dedicated FastAPI microservice on the Control Node. Every conversation (when `memory_enabled=true`) triggers background extraction of durable facts, preferences, and learnings into a pgvector-backed store. On subsequent requests, semantically similar memories are recalled and injected into the LLM context, enabling cross-session continuity.

## Files Created

| File | Purpose |
|------|---------|
| `control_plane/mempalace/Dockerfile` | Python 3.11-slim container for the MemPalace service |
| `control_plane/mempalace/requirements.txt` | FastAPI, SQLAlchemy[asyncio], asyncpg, pgvector, httpx, pydantic |
| `control_plane/mempalace/app/__init__.py` | Package marker |
| `control_plane/mempalace/app/database.py` | SQLAlchemy async models: Memory, AgentSnapshot, TeamMemory (768-dim pgvector, `mempalace` schema) |
| `control_plane/mempalace/app/embeddings.py` | Ollama-backed embedding (nomic-embed-text) + LLM extraction (nemotron-mini) with robust JSON parsing |
| `control_plane/mempalace/app/main.py` | FastAPI app — 11 endpoints for memories, extraction, snapshots, team memory |
| `agents/mempalace_client.py` | Synchronous HTTP client library for agent runtime (store, search, extract, snapshots, team memory) |
| `docs/phase_reports/phase_2_report.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `agents/config.py` | Added `MEMPALACE_URL` pointing to Control Node :8200 |
| `agents/router.py` | Added MemPalace semantic recall hook (~L642): searches with >0.5 similarity, injects as `[Relevant Memories]` system message. Added MemPalace store in TRAIN intent alongside JSON file storage. |
| `agents/main.py` | Added background extraction in both streaming and non-streaming paths. Collects `response_parts` during stream, fires `asyncio.create_task()` for extraction after completion. |
| `agents/coordinator.py` | Added `_team_store()` and `_team_clear()` helpers. Team memory stored at worker results (L486), synthesis (L514), and verification (L604). |
| `control_plane/docker-compose.yml` | Changed postgres image to `pgvector/pgvector:pg15`. Added mempalace service definition with health check. Added `mempalace_data` volume. |
| `control_plane/.env` | Added `LOVELACE_IP=192.168.2.101` for compose interpolation |
| `execution_plane/docker-compose.yml` | Re-added cAdvisor service (port 8081, privileged mode) — monitoring fix |

## Architecture

```
                         ┌────────────────┐
  User Input ───────────►│  Agent Runtime │
  (memory_enabled=true)  │  (Lovelace)   │
                         └──────┬─────────┘
                                │
               ┌────────────────┼────────────────┐
               │ Recall         │ Extract         │ Team Memory
               ▼                ▼                 ▼
        ┌──────────────────────────────────────────────┐
        │              MemPalace  :8200                 │
        │         (Control Node, FastAPI)               │
        ├──────────────────────────────────────────────┤
        │  /v1/memories/search  ← cosine similarity    │
        │  /v1/extract          ← LLM extraction       │
        │  /v1/memories         ← CRUD                 │
        │  /v1/snapshots        ← agent state          │
        │  /v1/team/{id}        ← coordinator memory   │
        └──────────┬───────────────────────────────────┘
                   │
        ┌──────────┴───────────┐
        │  PostgreSQL + pgvector│
        │  (pgvector/pgvector:  │
        │   pg15, schema:       │
        │   mempalace)          │
        └──────────┬───────────┘
                   │
        ┌──────────┴───────────┐
        │ Ollama (Lovelace     │
        │  :11434)              │
        │ • nomic-embed-text    │
        │   (768-dim embed)     │
        │ • nemotron-mini       │
        │   (extraction LLM)    │
        └──────────────────────┘
```

### Data Flow

1. **Recall** (before generation): Router searches MemPalace with user query → top-K results filtered at score > 0.5 → injected as system message
2. **Generation**: Normal intent routing and LLM generation
3. **Extraction** (after generation): Background async task sends conversation text to `/v1/extract` → nemotron-mini extracts semantic/episodic/procedural facts → embedded via nomic-embed-text → stored in pgvector
4. **Team Memory** (coordinator path): Worker results, synthesis, and verification stored under team ID for cross-worker context

### Database Schema

- **`mempalace.memories`**: content, memory_type (semantic/episodic/procedural), domain, agent_id, team_id, owner_id, embedding Vector(768), metadata JSONB, access_count, relevance_decay, timestamps
- **`mempalace.agent_snapshots`**: agent_id, snapshot_data JSONB, version (auto-increment per agent)
- **`mempalace.team_memories`**: team_id, key, value TEXT, embedding Vector(768), timestamps

Index: IVFFlat with 100 lists, cosine distance on all embedding columns.

## Test Results

### Smoke Tests (10/10 PASS)
| Test | Result |
|------|--------|
| Store semantic memory | ✅ |
| Store procedural memory | ✅ |
| Store episodic memory | ✅ |
| Semantic search (ranked correctly) | ✅ cyberpunk (0.586) > coding (0.493) |
| LLM extraction from conversation | ✅ 2 memories extracted |
| Stats endpoint | ✅ |
| Snapshot save | ✅ |
| Snapshot get (versioned) | ✅ |
| Team memory store | ✅ |
| Team memory get | ✅ |

### Integration Tests
| Test | Result |
|------|--------|
| Chat with `memory_enabled=true` — recall fires | ✅ search called, results injected |
| Chat with `memory_enabled=true` — extraction fires (streaming) | ✅ 6 memories extracted (7755 chars, owner=phase2_test) |
| Chat with `memory_enabled=true` — extraction fires (non-streaming) | ✅ 2 memories extracted |
| Round-trip: store → search → recall in next chat | ✅ threshold filtering at 0.5 works |
| TRAIN intent stores to MemPalace | ✅ (alongside existing JSON file storage) |
| UI regression (10 Hive routes) | ✅ all return 200 |
| Prometheus targets (3/3) | ✅ agent-runtime, cadvisor-justin, cadvisor-turing |

### Final Memory Stats
- **Total memories:** 20
- **Breakdown:** semantic/general (4), procedural/coding (2), procedural/visual (1), semantic/preferences (1), episodic/visual (1), episodic/preferences (1), semantic/visual (4), + 6 newly extracted

## Bug Fix: JSON Parsing

The initial extraction failed because nemotron-mini occasionally returns malformed JSON (missing commas between objects). Fixed by implementing a robust `_parse_llm_json()` helper in `embeddings.py` that:
1. Strips markdown code fences
2. Attempts direct `json.loads()`
3. Extracts `[...]` via bracket-depth matching
4. Repairs common LLM errors (trailing commas, missing commas between `}{`)

## Known Issues

1. **SPIRE JWT auth** fails with `got an unexpected keyword argument 'audiences'` — falls back to secret-based auth (pre-existing)
2. **Redis auth required** — falls back to MockRedis (pre-existing)
3. **Turing GPU offload**: llama3.2:3b runs with `size_vram: 0` (CPU-only on Turing), causing ~200s generation times
4. **Extraction quality** depends on nemotron-mini's JSON compliance — robust parser mitigates but doesn't eliminate all edge cases

## Models Used

| Model | Location | Purpose |
|-------|----------|---------|
| nomic-embed-text | Lovelace Ollama :11434 | 768-dim embedding generation |
| nemotron-mini | Lovelace Ollama :11434 | Memory extraction from conversations |
| qwen3:14b | Lovelace Ollama :11434 | Coordinator decomposition/synthesis |
| llama3.2:3b | Turing Ollama :11434 | Librarian (research/devops tasks) |

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `control_plane/mempalace/` | Implementation | MemPalace microservice (Dockerfile, app/) |
| `agents/mempalace_client.py` | Implementation | MemPalace client library |
| `control_plane/docker-compose.yml` | Infrastructure | MemPalace, pgvector service definitions |
| `agents/config.py` | Configuration | MemPalace endpoint settings |
| Git tag `phase-2-complete` | VCS | Phase 2 baseline snapshot |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-02-06 | AI-Copilot | Initial Phase 2 report — MemPalace memory integration |

</details>

---

## Maintenance & Update Guide

This is a **historical phase report**. Update only if:

- MemPalace architecture changes significantly (e.g., new embedding model or storage backend).
- A rollback to this phase is executed.

---

## Verification

| Claim | How to Verify |
|-------|---------------|
| MemPalace responds | `curl http://<control-node>:8100/health` → 200 OK |
| pgvector operational | Connect to PostgreSQL → `SELECT * FROM pg_extension WHERE extname='vector'` |
| Embedding works | Store a memory → retrieve by semantic query → verify recall |
| Git tag exists | `git tag -l phase-2-complete` |
