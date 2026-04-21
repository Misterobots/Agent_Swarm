---
title: "ADR-004: Inference-Time MarsRL Verification"
---

# ADR-004: Inference-Time MarsRL Verification

**Status**: Accepted  
**Date**: 2026-01

## Context

LLM outputs can contain errors: syntax bugs in code, hallucinated facts, unsafe content, or incoherent responses. Two approaches exist for quality improvement:

1. **Training-time**: Fine-tune the model to make fewer errors (RLHF, DPO, GRPO)
2. **Inference-time**: Verify and fix outputs before returning them

Agent Swarm already uses GRPO training for model improvement, but training cycles are slow (hours/days) and models can still produce bad outputs.

## Decision

Implement **MarsRL** — an inference-time Solver → Verifier → Corrector loop that catches and fixes errors before they reach the user.

### Architecture

```
User Request
    → Solver (generate response)
    → Verifier (3-layer validation)
        Layer 1: AST parse (code only)
        Layer 2: Coherence (all responses)
        Layer 3: Safety (llama-guard-3)
    → If score < 0.60: Corrector (rewrite) → back to Verifier
    → If score ≥ 0.60: Return to user
    → After 2 iterations: Return best attempt
```

### Rationale

- **Complementary to training**: Training reduces error rate; MarsRL catches remaining errors
- **Immediate effect**: No retraining needed — fixes work on the current model
- **Observable**: Every verification step is traced in Langfuse with process-reward scores
- **Tunable**: Thresholds, max iterations, and verifier layers are configurable
- **Named for**: Mars — Roman god of war (aggressive quality defense) + RL (Reinforcement Learning, as it uses reward signals)

## Consequences

### Positive

- **Higher quality outputs**: Catches syntax errors, repetition, and unsafe content
- **Immediate deployment**: No model retraining required
- **Full observability**: Every verification is traced with scores
- **Training signal**: Failed verifications generate comparison pairs for GRPO training
- **Configurable strictness**: Adjust thresholds per intent

### Negative

- **Latency cost**: Up to 3× token generation for failed responses (solver + 2 corrections)
- **Token cost**: Corrector uses the same model, consuming additional inference tokens
- **False negatives**: Simple heuristics (AST, coherence) may miss subtle errors
- **Complexity**: Three-agent pipeline is harder to debug than direct inference

## Performance Impact

| Scenario | Latency Overhead |
|----------|-----------------|
| Pass on first try (majority) | ~200ms (verifier only) |
| One correction round | ~2–3s additional |
| Max iterations (2) | ~4–6s additional |

In practice, ~80% of responses pass on the first try.

## Related

- [Architecture: MarsRL Loop](../marsrl.md) — full design details
- [Module: MarsRL Loop](../../modules/mars-loop.md) — implementation reference
- `agents/mars_loop.py` — source code


