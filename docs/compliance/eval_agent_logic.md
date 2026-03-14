# MAESTRO Evaluation: Agent Logic

**Component**: Swarm Runtime (MarsRL Loop, Router, Dispatcher)
**Date**: 2026-02-22
**Status**: ✅ COMPLIANT — Upgraded (MarsRL LogicVerifier added)

## 1. Component Description

The application logic layer where agents operate. Includes the `Dispatcher` (Event Bus), `Router` (Decision Engine), and `Tools`.

## 2. MAESTRO Layer Alignment

- **Layer 4 (Agent Framework)**: Orchestration, looping, and tool usage.
- **Layer 6 (Security)**: Active defense and guardrails.

## 3. Compliance Evidence

### L4: Orchestration Safety

- **Requirement**: "No infinite loops."
- **Implementation**:
  - `Dispatcher` enforces concurrency limits.
  - `MarsRLLoop` enforces `max_iter=2` — loop cannot run indefinitely.
  - Agent run-loops rely on finite state steps (Phidata).
- **Verification**: `agents/dispatcher.py`, `agents/mars_loop.py`.

### L4: Output Verification (MarsRL LogicVerifier — NEW v3.0)

- **Requirement**: "Validate agent outputs before user delivery."
- **Implementation**:
  - **Layer 1** (AST Parse): All Python code blocks are parsed with `ast.parse()`. SyntaxError → Corrector invoked.
  - **Layer 2** (Coherence): Length, repetition, and truncation checks. Fail → Corrector invoked.
  - **Layer 3** (Safety): `llama-guard-3:8b` safety check. Fail → **Hard block** (response suppressed entirely).
  - Pass threshold: score ≥ 0.60. Below threshold → Corrector produces revised response.
- **Verification**: `agents/verifier_agent.py`, `tests/test_mars_loop.py`.

### L6: Active Defense (Guardrails)

- **Requirement**: "Monitor and block malicious actions."
- **Implementation**:
  - **SecurityAgent**: Intercepts commands.
  - **Blocklist**: Regex-based blocking of `rm`, `mkfs`, `curl`.
  - **Drift**: Static Analysis of codebase for unauthorized patterns.
  - **LogicVerifier**: Runtime output sanitization (NEW).
- **Verification**: `agents/security_agent.py`, `agents/verifier_agent.py`.

### L6: Supply Chain Security

- **Requirement**: "Vet dependencies."
- **Implementation**:
  - `drift` governance approves/rejects new imports.
  - `SecurityAgent.review_dependency()` checks against known bad packages.
  - Blocked packages never installed (hard stop before `pip install`).
- **Verification**: `security_agent.py` unit tests.

## 4. Residual Risks

- **Context Window Attacks**: Prompt injection is mitigated by llama-guard-3 input pre-screening and LogicVerifier output post-screening, but adversarial prompts remain a theoretical risk.
- **Verifier Bypass**: A sufficiently adversarial response that passes AST parse and coherence but contains logic bugs. Future mitigation: add unit test execution in Layer 1.

## 5. Diagnostic Tooling — Token Inspection

**Text Generation WebUI** (profile: `diagnostic`) provides runtime token-level observability for the MarsRL loop:

- **Logit viewer**: Shows per-token probabilities at each generation step
- **Entropy indicators**: Highlights high-entropy (uncertain) tokens — audit signals for borderline verifier scores
- **Sampler experimentation**: Test `top_k`, `top_p`, `min_p` before updating Primary Solver prompts
- **Not in request path** — started manually during debug sessions only

```bash
docker-compose --profile diagnostic up text-gen-webui -d
# Access at http://localhost:7860
```

This directly addresses the **Verifier Bypass** residual risk — borderline scores (0.60–0.70) can now be correlated to specific high-entropy tokens in the solver output, enabling targeted prompt improvements.
