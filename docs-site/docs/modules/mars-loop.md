---
title: "Module: MarsRL Loop"
---

# MarsRL Loop

Inference-time quality verification: Solver → Verifier → Corrector.

## Files

| File | Purpose |
|------|---------|
| `agents/mars_loop.py` | `MarsRLLoop` class — orchestration |
| `agents/architect_agent.py` | Solver (response generation) |
| `agents/verifier_agent.py` | Verifier (3-layer validation) |
| `agents/corrector_agent.py` | Corrector (error rewriting) |

## Class: MarsRLLoop

### `run()` Method

```python
async def run(
    messages: list[dict],
    intent: str,
    session_id: str,
    token: Optional[str] = None,
    stream_callback: Optional[Callable] = None,
) -> MarsLoopResult
```

### Algorithm

```
1. Solver generates response
2. Verifier runs 3 checks:
   a. AST parse (code only)
   b. Coherence check
   c. Safety check (llama-guard-3)
3. If score ≥ 0.60: PASS → return
4. If score < 0.60 and iterations < 2:
   a. Corrector rewrites response
   b. Go to step 2
5. If iterations ≥ 2: return best attempt
```

### MarsLoopResult

```python
@dataclass
class MarsLoopResult:
    response: str
    iterations: int
    solver_score: float
    corrector_invoked: bool
    final_score: float
    trace_id: Optional[str]
    token: Optional[str]
    template_metadata: dict
    metadata: dict
```

## Verifier Details

### Layer 1: AST Parse

```python
try:
    ast.parse(code_content)
    # Score unchanged
except SyntaxError:
    score -= 0.40
```

Only runs when the response contains Python code blocks.

### Layer 2: Coherence

Checks for:

- Non-empty response
- No repetition loops (same phrase repeated 3+ times)
- Response addresses the user's question

Score penalty: −0.25 per failed check.

### Layer 3: Safety

Uses {{ verifier_model }} to check for harmful content. A safety failure forces score to 0.0 and blocks the response.

## Langfuse Integration

Every run creates:

- A **trace** with session ID and intent metadata
- **Spans** for each step (solver, verifier, corrector)
- **Scores** recorded as float 0.0–1.0

## Related

- [Architecture: MarsRL](../architecture/marsrl.md) — design document
- [Architecture: ADR-004](../architecture/decisions/adr-004-marsrl.md) — decision rationale


