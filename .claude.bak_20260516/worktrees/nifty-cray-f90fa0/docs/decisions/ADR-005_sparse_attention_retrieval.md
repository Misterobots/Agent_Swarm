# ADR-005: Sparse Attention Patterns for MemPalace Retrieval and Context Assembly

Document ID: ADR-005
Domain: Architecture / Memory / Agents
Owner: Core Platform
Reviewers: Architecture, Security, Platform
Status: Proposed
Version: 1.0
Last Updated: 2026-05-06
Review Due: 2026-08-06
Source of Truth: docs/decisions/
Related Controls: MAESTRO L2 (Observability), L4 (Memory Integrity)
Related Evidence: docs/evidence/sparse_attention_proposal_2026_05_06.md
Supersedes: None

---

## Status
**Proposed** (2026-05-06)

## Context

The agent memory retrieval and context injection pipeline in `church.py` currently exhibits three
compounding problems as conversation depth and memory store size grow:

1. **Undifferentiated retrieval**: `church.py` posts a single flat query to MemPalace
   (`/v1/memories/search`) with no domain filter, regardless of the resolved intent. An `IMAGE`
   request retrieves memories from `infrastructure` and `coding` domains with the same probability
   as `comfyui` memories — introducing irrelevant signal into the generation context.

2. **Blunt similarity threshold**: The sole quality gate is a hardcoded `score > 0.5`
   cosine-similarity cutoff applied caller-side in `church.py` (line 1039). The scoring formula
   (`1.0 - cosine_distance`) does not account for memory age or access frequency, so a 90-day-old
   memory with a marginally relevant embedding ranks above a freshly reinforced memory with slightly
   lower cosine similarity.

3. **Unbounded context growth**: The full conversation history is serialized into `history_context`
   without truncation (lines 798–804). `CONTEXT_WINDOWS` is defined in `agents/config.py` (line 113)
   with per-model token budgets, but is never imported or applied in `church.py`. As context windows
   fill, later turns are silently truncated by the model with no caller-side control or visibility.

`COMPACT_AUTO_THRESHOLD = 0.95` (defined in `config.py`) was intended to trigger compaction but has
never been wired to any mechanism.

---

## Decision

**Implement four incremental improvements to the retrieval and context pipeline, each independently
deployable:**

### Phase 1 — Intent-Gated Domain Filtering

Add a module-level `INTENT_DOMAIN_MAP` dict in `church.py`. When posting to
`/v1/memories/search`, include `domain=` when the resolved intent maps to a specific domain.
`SearchQuery.domain` already exists in the MemPalace API and is passed through to a SQL `WHERE`
clause — no API changes required.

**Domain mapping:**

| Intent | Domain Filter |
|--------|--------------|
| `IMAGE`, `ACTION_FIGURE` | `comfyui` |
| `DEVOPS`, `IOT_CONTROL` | `infrastructure` |
| `CODE`, `IOT_DEV` | `coding` |
| `DATA` | `data` |
| `TRAIN` | `agents` |
| `CONVERSATION`, `COORDINATE`, `RESEARCH`, `DOCUMENTATION` | *(none — broad recall)* |

### Phase 2 — Composite Retrieval Scoring

Replace the raw `1.0 - cosine_distance` score in `search_memories()` and `search_memories_mcp()`
with a weighted composite:

$$\text{score} = 0.6 \cdot s_{\cos} + 0.25 \cdot e^{-d/30} + 0.15 \cdot \frac{\log(1 + n_{a})}{\log(101)}$$

where:
- $s_{\cos}$ = cosine similarity (`1.0 - cosine_distance`)
- $d$ = days since `created_at`
- $n_a$ = `access_count`

Add `min_score: Optional[float]` to `SearchQuery` to push threshold enforcement server-side,
allowing removal of the hardcoded `> 0.5` check in `church.py`.

### Phase 3 — Cross-Encoder Re-Ranking

After initial vector retrieval, over-fetch `limit × 3` candidates and re-score using
`CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` (22M params, CPU-resident, ~20–80ms).
Blend composite score and cross-encoder logit via sigmoid normalization:

$$\text{final} = 0.5 \cdot \text{composite} + 0.5 \cdot \sigma(\text{reranker\_logit})$$

Gate re-ranking behind `rerank: bool = False` in `SearchQuery`; enable only for high-value intents
(`RESEARCH`, `DEVOPS`, `CODE`, `COORDINATE`). Keep disabled for latency-sensitive intents
(`CONVERSATION`, `IOT_CONTROL`).

### Phase 4 — Context Budget Manager

Introduce `agents/context_budget.py` with:

- `estimate_tokens(text) → int` — lightweight `len // 4` heuristic (no external dependencies)
- `trim_history(history, budget) → list` — walks history newest-first, always preserves
  `role=system` messages, drops oldest `user`/`assistant` turns when budget is exceeded
- `ContextBudget(model_name)` class — reads `CONTEXT_WINDOWS` from `config.py`, allocates budget:
  - 30% reserved for generation headroom
  - 50% of remainder → conversation history
  - 25% of remainder → memories + grounding
  - 25% of remainder → system instructions

Apply `trim_history()` in `church.py` before serializing `history_context`, activating the
long-dormant `CONTEXT_WINDOWS` config.

---

## Rationale

- **Phase 1** has the highest cost-to-impact ratio: ~20 lines of code, eliminates cross-domain
  retrieval noise immediately, no new dependencies. The `domain=` filter is already implemented
  in the API; only the caller needs updating.

- **Phase 2** directly addresses recency and frequency blind spots. The formula is grounded in
  established information retrieval practice — BM25 uses analogous term frequency dampening.
  No schema changes are required; `created_at` and `access_count` are already populated columns
  on the `Memory` ORM model.

- **Phase 3** is the only change requiring a new model dependency and a Hopper Docker rebuild.
  `ms-marco-MiniLM-L-6-v2` is the de facto standard for lightweight neural re-ranking; CPU
  inference is sufficient at current query volume. The `rerank=False` default means the change
  is zero-risk for all intents until explicitly opted in.

- **Phase 4** activates existing but dormant infrastructure (`CONTEXT_WINDOWS`,
  `COMPACT_AUTO_THRESHOLD`) and prevents silent model-side truncation from producing unexpected
  behavior at scale. The `len // 4` token estimator deviates ~15% from true tokenizer output —
  acceptable for budgeting purposes and avoids a tokenizer dependency.

**Alternatives considered:**

- **Dense bi-encoder upgrade** (replacing `nomic-embed-text` with a larger model): rejected —
  the bottleneck is retrieval selectivity, not embedding quality.
- **In-context summarization trigger**: rejected as premature; Phase 4's sliding window is
  sufficient and fully reversible.
- **GraphRAG (multi-hop retrieval)**: deferred — warranted if episodic chain-of-thought queries
  emerge in production, but adds significant complexity for unproven benefit today.

---

## Consequences

### Positive
- Cross-domain retrieval noise eliminated per intent category (Phase 1)
- Memory ranking reflects recency and reinforcement, not just semantic distance (Phase 2)
- Highest-recall ordering for knowledge-intensive intents at acceptable latency (Phase 3)
- Context window overflows become visible and controllable; `CONTEXT_WINDOWS` becomes
  load-bearing for the first time since it was defined (Phase 4)

### Negative
- Phase 3 adds ~20–80ms per request for `rerank=True` intents
- Phase 3 requires `sentence-transformers` on Hopper — Docker image rebuild and model download
  (~90 MB) required
- Phase 4 introduces a `len // 4` token heuristic; true counts may deviate ~15%

### Neutral / Ongoing
- `COMPACT_AUTO_THRESHOLD = 0.95` remains defined; Phase 4 establishes the trimming mechanism
  but does not yet wire the auto-trigger — that is a follow-on task
- `memory_system.py` (flat-file keyword rules) is out of scope; it is a separate subsystem
- `search_memories_mcp` MCP tool receives composite scoring (Phase 2) but not re-ranking —
  MCP callers are LLMs where extra latency is not justified

---

## Evidence / Verification

Pre-flight and post-implementation verification checklists:
`docs/evidence/sparse_attention_preflight_2026_05_06.md`

Baseline state record (captured before implementation):
`docs/evidence/sparse_attention_proposal_2026_05_06.md`

---

## Related Decisions
- [ADR-003: User-Scoped Storage](ADR-003_user_scoped_storage.md) — establishes the `owner_id`
  scoping model that Phase 1 domain filtering extends
