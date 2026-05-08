# Sparse Attention Retrieval — Design Proposal Record

**Date:** 2026-05-06
**Component:** MemPalace retrieval pipeline · `church.py` context assembly
**Environment:** Production stack — Hopper MemPalace (`:8200`), agent_runtime on Turing, Lovelace Ollama
**Status:** Proposed — pending ADR-005 acceptance
**ADR Reference:** `docs/decisions/ADR-005_sparse_attention_retrieval.md`

---

## Motivation

Analysis of the MemPalace retrieval path and `church.py` context injection on 2026-05-06 identified
three compounding issues that grow in impact as memory store size and conversation depth increase:

| # | Issue | Evidence Location |
|---|-------|------------------|
| 1 | Cross-domain memory noise | `church.py` line 1035 — no `domain=` filter in POST payload |
| 2 | Staleness-blind ranking | `control_plane/mempalace/app/main.py` lines 238–281 — score = `1.0 - cosine_distance` only |
| 3 | Unbounded history growth | `church.py` lines 798–804 — full history serialized; `CONTEXT_WINDOWS` (config.py:113) never imported |

---

## Baseline State (captured 2026-05-06)

### MemPalace search endpoint
**File:** `control_plane/mempalace/app/main.py` lines 238–281

- Scoring: `similarity = 1.0 - cosine_distance`
- Ordering: SQL `ORDER BY cosine_distance ASC` — pure vector proximity, no time or frequency signal
- `access_count` is incremented on every retrieval (data exists and is populated), but not used in score
- `created_at` is a non-null `DateTime` column on the `Memory` model, but not used in score

### `church.py` retrieval call
**File:** `agents/church.py` lines 1027–1050

```python
json={"query": user_input, "owner_id": owner_id, "limit": 5}
```

- No `domain=` filter passed — intent is fully resolved before this call (overrides complete at ~line 1346)
- Caller-side threshold: `score > 0.5` (line 1039) — hardcoded, cannot be tuned per intent
- All context layers (history, memories, web grounding, doc grounding) injected unconditionally

### `church.py` history serialization
**File:** `agents/church.py` lines 798–804

```python
history_context = "\n\n[Previous Conversation History]:\n"
for msg in history:
    role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    history_context += f"- {role.upper()}: {content}\n"
```

- No length limit — entire `history` list is serialized
- `CONTEXT_WINDOWS` dict defined at `agents/config.py` line 113, never imported into `church.py`
- `COMPACT_AUTO_THRESHOLD = 0.95` defined in `config.py` — wired to nothing

### `SearchQuery` Pydantic model
**File:** `control_plane/mempalace/app/main.py` lines 83–91

```python
class SearchQuery(BaseModel):
    query: str
    owner_id: Optional[str] = None
    agent_id: Optional[str] = None
    team_id: Optional[str] = None
    memory_type: Optional[str] = None
    domain: Optional[str] = None
    limit: int = 10
```

- `domain=` field exists and is wired to a SQL `WHERE` clause — caller just never passes it
- No `min_score` field — threshold enforcement is caller-side only
- No `rerank` flag

### `Memory` ORM model
**File:** `control_plane/mempalace/app/database.py` lines 45–80

Relevant columns already present (no schema changes needed for Phases 1–3):

| Column | Type | Phase Used |
|--------|------|-----------|
| `domain` | `String(100)` | Phase 1 |
| `created_at` | `DateTime(timezone=True)` | Phase 2 |
| `access_count` | `Integer, default=0` | Phase 2 |
| `embedding` | `Vector(768)` | All phases |

---

## Proposed Changes Summary

| Phase | Files | Change Type | New Dependency? |
|-------|-------|-------------|----------------|
| 1 — Intent domain filter | `agents/church.py` | ~20 lines config + logic | No |
| 2 — Composite scoring | `control_plane/mempalace/app/main.py` | Algorithm replacement in 2 functions | No |
| 3 — Cross-encoder re-rank | `control_plane/mempalace/app/reranker.py` (new), `main.py`, `church.py`, `Dockerfile`, `requirements.txt` | New module + infra | Yes (`sentence-transformers`, model ~90 MB) |
| 4 — Context budget manager | `agents/context_budget.py` (new), `agents/church.py` | New module + wiring | No |

---

## Expected Post-Implementation Behaviour

| Phase | Observable Change |
|-------|------------------|
| 1 | `IMAGE` intent MemPalace call includes `"domain": "comfyui"`; returned memories are `comfyui`-scoped only |
| 2 | A memory with `access_count=50` outranks a semantically equal memory with `access_count=1`; a 1-day-old memory outranks a 90-day-old memory at equal cosine similarity |
| 3 | `RESEARCH` and `DEVOPS` requests show re-ranked memory ordering in logs; latency overhead ≤ 150ms |
| 4 | `history_context` length plateaus at model context budget; `role=system` messages always preserved; `CONTEXT_WINDOWS` config is load-bearing |

---

## Source References

| Source | File | Lines |
|--------|------|-------|
| MemPalace search endpoint | `control_plane/mempalace/app/main.py` | 238–281 |
| SearchQuery model | `control_plane/mempalace/app/main.py` | 83–91 |
| Memory ORM model | `control_plane/mempalace/app/database.py` | 45–80 |
| church.py MemPalace recall block | `agents/church.py` | 1027–1050 |
| church.py history build | `agents/church.py` | 798–804 |
| church.py intent overrides | `agents/church.py` | 1251–1346 |
| CONTEXT_WINDOWS definition | `agents/config.py` | 113 |
| COMPACT_AUTO_THRESHOLD | `agents/config.py` | ~115 |
| search_memories_mcp tool | `control_plane/mempalace/app/main.py` | 687–716 |
