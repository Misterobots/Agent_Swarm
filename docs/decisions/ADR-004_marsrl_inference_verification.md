# ADR-004: MarsRL Inference-Time Verification Loop

Document ID: ADR-004
Domain: Architecture / ML / Observability
Owner: Architecture
Reviewers: Security, Platform, ML Lead
Status: Accepted
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-06-30
Source of Truth: docs/decisions/
Related Controls: MAESTRO L1 (Quality), L2 (Observability)
Related Evidence: TBD (Mars loop verification traces)
Supersedes: None

---

## Status
**Accepted** (2026-03-31)

## Context

The system uses a multi-layer inference architecture:
- **Layer 1 (Solver)**: Language model generates candidate responses (Ollama qwen3.5:9b)
- **Layer 2 (Verifier)**: Verify response for correctness, safety, policy compliance before returning to user
- **Layer 3 (Corrector)**: If verification fails, automatically fix the response or regenerate

Previous implementations lacked explicit verification; responses were generated and immediately returned:
- No way to detect hallucinations or policy violations before user sees them
- Difficult to improve response quality systematically; no feedback loop
- Template evolution (choosing better prompts) was manual and ad-hoc
- No audit trail of verification outcomes

---

## Decision

**Implement three-stage synchronous inference loop with streaming verification and artifact capture:**

### 1. Loop Stages

```
Request arrives
  → Extract user_id, intent, context
  ↓
[SOLVER STAGE]
  → Pass to LLM "Generate candidate response"
  → Capture: raw_response, token_count, latency, seed, model_version
  → Produce: candidate_response with metadata
  ↓
[VERIFIER STAGE]
  → Run verification checks on candidate_response:
    - Fact check: Does response contain obvious hallucinations?
    - Policy check: Does response violate safety/brand guidelines?
    - Completeness: Does response address user query fully?
    - Toxicity check: Does response contain harmful content?
  → Capture: verification_result (pass/fail with reason), checks_run, latency
  ↓
[CORRECTOR STAGE] (if verification fails)
  → Regenerate response with feedback loop:
    - Pass failure reason to LLM: "Your previous response was X. Improve it by doing Y."
    - Re-run VERIFIER with new response
    - Max retries: 2 (total 3 attempts: Solver + Corrector×2)
  → If all retries fail: Return fallback response (polite generic response)
  → Capture: corrector_attempt_number, modification_applied, latency
  ↓
[RESPONSE SENT]
  → If verification passed → Return candidate_response to user
  → If verification failed and corrected → Return corrected_response to user
  → If all retries failed → Return fallback_response to user
  ↓
[ASYNC PROCESSING]
  → Store all artifacts in trace context (Langfuse)
  → Emit metrics: loops.success_rate, loops.verification_latency, loops.correction_attempts
  → Queue template evolution job (off-critical-path)
```

### 2. Verification Checks

Each check is independent and can be disabled/weighted:

```python
class VerificationCheck:
    name: str  # "fact_check", "policy_check", "toxicity_check"
    enabled: bool
    timeout: int  # milliseconds
    weight: float  # 1.0 = fail-closed, 0.5 = warning only
    
    def run(self, response: str, context: dict) -> CheckResult:
        # Return CheckResult(passed: bool, reason: str, latency_ms: int)
        pass

# Example checks
CHECKS = [
    FactCheck(timeout=1000, weight=1.0),  # Fail-closed
    PolicyCheck(timeout=500, weight=1.0),  # Fail-closed
    ToxicityCheck(timeout=2000, weight=0.5),  # Warning only
]
```

### 3. Artifact Capture

Every stage produces artifacts for audit and learning:

```python
@dataclass
class SolverArtifact:
    request_id: str
    user_id: str
    intent: str
    raw_response: str
    token_count: int
    model: str
    seed: int
    latency_ms: int
    timestamp: datetime

@dataclass
class VerifierArtifact:
    request_id: str
    response: str
    checks_run: List[str]
    checks_passed: int
    checks_failed: int
    verification_passed: bool
    failure_reason: Optional[str]
    latency_ms: int
    timestamp: datetime

@dataclass
class CorrectorArtifact:
    request_id: str
    attempt_number: int
    feedback_given: str
    new_response: str
    verification_result: bool
    latency_ms: int
    timestamp: datetime
```

All artifacts stored in Langfuse trace with user_id correlation.

### 4. Latency Budget

End-to-end Mars loop latency must not exceed 5 seconds (user-perceived):

| Stage | Budget | Notes |
|---|---|---|
| Solver (LLM generation) | 3000ms | Can stream to user while verifier runs in parallel |
| Verifier (checks) | 1000ms | Run checks in parallel; fail-closed if any timeout |
| Corrector (if needed, per attempt) | 2000ms | 2 retry attempts max |
| Total (p99) | 5000ms | If exceed, return fallback response |

### 5. Streaming and Observability

**Streaming pattern**:
- Start sending Solver output to user as it arrives (token-by-token streaming)
- Run Verifier in parallel on complete response (can start verifying as Solver finishes)
- If Verifier finds issue during streaming → Interrupt stream, emit correction, resume with corrected response
- If Verifier passes → Streaming completes normally

**Observable events**:
```
request_id: req-123456
user_id: user-999
[event] request_started
[event] solver_started (model: qwen3.5, seed: 42)
[stream] solver_output_chunk[0] = "Hello..."
[stream] solver_output_chunk[1] = " there..."
[event] solver_completed (tokens: 100, latency_ms: 2500)
[event] verifier_started (checks: [fact, policy, toxicity])
[event] verification_check_completed (check: fact, passed: true, latency_ms: 150)
[event] verification_check_completed (check: policy, passed: false, reason: "brand_violation", latency_ms: 100)
[event] corrector_started (attempt: 1, feedback_given: "Avoid brand references")
[stream] corrected_response_chunk[0] = "Hello..."
[event] corrector_completed (corrected: true, latency_ms: 2000)
[event] verifier_rerun_completed (checks_passed: 3, verification_passed: true)
[event] response_sent (final_response_generated_by: corrector, total_latency_ms: 4650)
[async_event] template_evolution_job_queued
```

---

## Rationale

### Why Three Stages?
- **Solver (generation)**: Must complete first; cannot verify nothing
- **Verifier (validation)**: Catches quality issues early; fail-closed design
- **Corrector (fix)**: Gives verification loop a chance to self-heal; improves success rate without user impact

### Why Parallel Execution Where Possible?
- **Performance**: Start sending Solver output to user while Verifier validates in parallel
- **User experience**: User sees streaming response immediately; verification happens invisibly
- **Latency budget**: Cannot afford serial 3000ms (Solver) + 1000ms (Verifier) = 4s; need parallelism

### Why Artifact Capture?
- **Auditability**: Can replay any request and understand why it was verified/corrected
- **Learning**: Template evolution uses verification success/failure to improve prompts
- **Observability**: Every stage produces metrics for monitoring

### Why Bounded Retries?
- **Latency control**: Max 2 retries keeps p99 latency under 5s budget
- **Avoiding loops**: If Corrector×2 fails, give up and return fallback (better UX than timeout)

### Alternatives Considered

**Alternative A: Serial processing (Solver → Verifier → Corrector)**
- Simplest to implement
- ❌ **Rejected**: p99 latency > 5s; unacceptable user experience

**Alternative B: Verification only, no correction**
- If verification fails, return error
- ❌ **Rejected**: High user-facing error rate; poor UX

**Alternative C: Multiple candidate responses (ensemble)**
- Generate 3 candidates in parallel, verify all, pick best
- ✅ **Considered**: Better quality; deferred as optimization for v2
- 🔄 **Future work**: Add ensemble after single-loop proves stable

---

## Consequences

### Positive
- ✅ **Quality (High)**: Verification catches hallucinations and policy violations before user sees them
- ✅ **User experience (High)**: Corrector loop fixes issues invisibly; users rarely see errors
- ✅ **Learning (High)**: Artifact capture enables template evolution; can improve prompts systematically
- ✅ **Auditability (Medium)**: Full trace of generation → verification → correction for every response
- ✅ **Safety (Medium)**: Policy violations caught and corrected; compliance risk reduced

### Negative
- ⚠️ **Latency (Medium)**: Extra 1-2 seconds added to response time (verifier + corrector)
- ⚠️ **Complexity (Medium)**: Three-stage pipeline more complex than single-stage generation
- ⚠️ **Compute cost (Low)**: Additional verification runs (especially retries) increase inference cost

### Neutral / Ongoing
- 🔄 **Check tuning**: Verification checks need periodic tuning; false positive rate needs monitoring
- 🔄 **Template evolution**: Learning system needs to capture and learn from verification outcomes
- 🔄 **Fallback response quality**: Generic fallback responses need improvement after initial launch

---

## Evidence / Verification

### Test Plan
1. **Functional tests**: Three-stage loop execution
   - Solver completes successfully with response
   - Verifier validates response and passes
   - Corrector never invoked for valid responses

2. **Failure recovery tests**: Verification failure and correction
   - Verifier detects issue and fails response
   - Corrector regenerates and passes re-verification
   - After 2 retries, returns fallback response

3. **Performance tests**: Latency budgets
   - Solver stage completes within 3s (p99)
   - Verifier stage completes within 1s (p99)
   - End-to-end completes within 5s (p99)

4. **Correctness tests**: Artifact capture
   - All three artifacts present in trace for successful loop
   - Artifacts consistent (request_id, user_id, timing match)
   - Metadata complete and correct

### Metrics to Track
- `marsrl.solver_latency_p99` (Histogram): 99th percentile solver latency; target <3000ms
- `marsrl.verification_passed_ratio` (Gauge): % of responses passing first verification; target >90%
- `marsrl.correction_success_ratio` (Gauge): % of corrections that pass re-verification; target >80%
- `marsrl.end_to_end_latency_p99` (Histogram): 99th percentile total latency; target <5000ms
- `marsrl.fallback_response_count` (Counter): Number of times fallback was used; should be <5% of total responses

### Verification Schedule
- **Week 0**: Functional tests pass; three-stage flow works end-to-end
- **Week 1**: Performance tests pass; latency budgets met in staging
- **Week 2**: Canary deployment; monitor metrics for 24 hours
- **Week 3**: Full production rollout; establish alerts on metrics

---

## Implementation Checklist

- [ ] Verifier module created with check registration framework
- [ ] Fact check implementation (can use external service or heuristics)
- [ ] Policy check implementation
- [ ] Toxicity check implementation (e.g., via nlpcloud or similar API)
- [ ] Corrector module created with feedback loop
- [ ] Artifact capture implemented in all three stages
- [ ] Langfuse trace integration updated to capture all artifacts
- [ ] Streaming updated to support parallel verification
- [ ] Fallback response content created and tested
- [ ] Latency monitoring and alerts configured
- [ ] Unit tests written for checks and corrector
- [ ] Integration tests written for three-stage loop
- [ ] Load tests run to verify latency budgets
- [ ] Documentation and runbook created for operators

---

## Related Decisions
- [ADR-002: Hook Execution Model](ADR-002_hook_execution_model.md) (verifier checks can run as hooks)
- [Design Framework: MarsRL Loop](../admin/design_framework.md) (architecture narrative)

## Reviewers and Approval
| Role | Name | Approved | Date |
|---|---|---|---|
| Architecture Lead | [To be assigned] | [ ] | — |
| ML Lead | [To be assigned] | [ ] | — |
| Platform Lead | [To be assigned] | [ ] | — |

---

**Document Owner**: Architecture  
**Last Review**: 2026-03-31  
**Next Review**: 2026-06-30  
**History**: Created as part of Sprint 2 ADR foundation; captures existing but undocumented MarsRL loop from agents/mars_loop.py and intent routing logic
