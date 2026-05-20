---
title: "Module: Coordinator"
---

# Coordinator

Multi-agent orchestration for complex, multi-step tasks.

## Files

`agents/lamport.py` is a thin re-export wrapper. All implementation lives in the `agents/coordination/` package:

| File | Purpose |
|------|---------|
| `agents/lamport.py` | Public entry point — re-exports `coordinate_task`, `coordinate_project_onboarding`, session types |
| `agents/coordination/orchestrator.py` | `coordinate_task`, `coordinate_project_onboarding` — main generator loop |
| `agents/coordination/decomposer.py` | `_decompose_task`, `_decompose_task_perspectives` — LLM task breakdown |
| `agents/coordination/executor.py` | `_run_worker`, `_get_agent_for_role`, `_derive_worker_token` — worker execution |
| `agents/coordination/synthesizer.py` | `_synthesize_findings`, `_synthesize_perspective_matrix`, `_generate_followups` |
| `agents/coordination/palace.py` | MemPalace HTTP client — team store + project registry |
| `agents/coordination/pioneers.py` | Worker persona pool (named after computing pioneers) and perspective taxonomy |
| `agents/coordination/session.py` | `WorkerState`, `WorkerInfo`, `CoordinatorSession` — worker lifecycle tracking |

## When Used

The Coordinator handles `COORDINATE` and `RESEARCH` intents — tasks that require:

- Breaking a problem into subtasks
- Parallel research or investigation
- Multiple agent capabilities in one request
- Verification of the assembled result

## Phases

```mermaid
graph LR
    A[Decompose] --> B[Research]
    B --> C[Synthesize]
    C --> D[Implement]
    D --> E[Verify]
```

| Phase | Description | Workers |
|-------|-------------|---------|
| **Decompose** | LLM breaks the task into subtasks | 1 (coordinator) |
| **Research** | Workers investigate in parallel | Up to 5 |
| **Synthesize** | Merge findings into a plan | 1 (coordinator) |
| **Implement** | Execute the plan | 1–3 |
| **Verify** | Fresh worker validates results | 1 |

## Worker Roles and Personas

Workers are assigned personas from `coordination/pioneers.py` — a pool of named computing pioneers scoped to each role:

| Role | Example personas | Notes |
|------|-----------------|-------|
| `researcher` | Shannon, Minsky, Johnson | Investigate unknowns |
| `architect` | Babbage, Dijkstra, Hamilton | System design |
| `coder` | Knuth, Lovelace, Ritchie | Implementation |
| `devops` | Cerf, Torvalds, Perlman | Infrastructure |
| `analyst` | Codd, Hopper, Boole | Data and analysis |
| `verifier` | Hoare, Turing, Liskov | Validation |

Additional perspective roles (`technical`, `ethical`, `economic`, `scientific`, `regulatory`, `end_user`) are used in ultraplan/perspective-matrix synthesis.

### Perspective Research Mode Gate

Pioneer agents (the perspective-role workers — Knuth, Weil, Keynes, etc.) are only spawned when **`research_mode=True`** is passed to `coordinate_task`. This flag maps directly to the Research toggle in the chat toolbar.

**Before the fix** (historical): `_decompose_task_perspectives()` was called on any broad multi-faceted topic regardless of whether the user had enabled Research Mode, causing pioneer agent cards to appear unexpectedly.

**Current behaviour** (`orchestrator.py`):

```python
# Perspective probe is now gated behind research_mode
if research_mode and not _use_perspective_mode and not _is_creative_task:
    _use_perspective_mode = await _decompose_task_perspectives(...)
```

If `research_mode` is `False` (Research toggle OFF), the orchestrator skips the perspective probe entirely and routes through standard linear decomposition regardless of how broad the topic is.

## Scratchpad

Workers communicate via a shared scratchpad — a filesystem directory (`agents/scratchpad/`) containing intermediate artifacts:

```
agents/scratchpad/{coordination_id}/
├── plan.json           # Decomposed task plan
├── research_1.md       # Worker 1 findings
├── research_2.md       # Worker 2 findings
├── synthesis.md        # Merged findings
├── implementation.md   # Final output
└── verification.md     # Verification report
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Max workers | 5 | Parallel research workers |
| Timeout per phase | 120s | Phase execution limit |
| Max total time | 600s | Total coordination limit |

## Example Flow

User: *"Compare Python web frameworks for a REST API and build a prototype"*

1. **Decompose**: Split into "research frameworks" + "build prototype"
2. **Research**: 3 workers investigate Flask, FastAPI, Django REST
3. **Synthesize**: Merge into comparison table with recommendation
4. **Implement**: Coder builds FastAPI prototype
5. **Verify**: Verifier checks code runs and matches requirements

## Related

- [Architecture: Agent System](../architecture/agent-system.md) — routing to coordinator
- [User Guide: Research Mode](../user-guide/research-mode.md) — user-facing guide including Research toggle documentation
- [User Guide: Goals Mode](../user-guide/goals.md) — how the coordinator populates goal plan steps


