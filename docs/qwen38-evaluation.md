# Qwen 3.8 evaluation suite

This suite qualifies the opt-in `qwen3.8:27b` Memex profile in six cases:

1. code review against seeded defects;
2. multi-file implementation with hidden deterministic checks;
3. approval and project isolation;
4. image understanding from fixed fixtures;
5. long-context fact recovery;
6. provider recovery and contention behavior.

The suite has two modes. `mock` is offline and deterministic. It validates the
runner, evidence schema, fixture isolation, hidden assertions, and failure
accounting. Mock output is never evidence that the live model, GPU queue,
browser authentication, or Memex tools work. `live` is reserved for the parent
integrator's adapter contract and currently exits before making requests.

Every result records the requested model, actual model, provider, configured
context maximum, effective context budget, measured input size, owner/session/
project identity, elapsed time, approval wait time, fallback status, and case
status. A fallback response cannot pass a Qwen success assertion. The hidden
assertions are acceptance authority; a same-model verifier or narrative answer
does not qualify a case.

Case deadlines are 10 minutes for review, approvals, vision, and recovery, and
20 minutes for build and long-context. Approval wait time is recorded separately
from model latency. Each case receives a unique owner, session, and project
identity. Fixtures are created under temporary directories and never touch a
live repository.

## Run the offline suite

From the evaluation worktree:

```powershell
python -m pytest tests/qwen38_eval -q
python scripts/qwen38_eval/runner.py --mode mock --report artifacts/qwen38-evaluation.json
```

The generated report is an artifact and is intentionally not part of the owned
source directories. The report should be attached to the agent handoff, along
with the commit and exact command output.

## Live qualification prerequisites

The parent integrator must provide the live adapter contract before enabling
live mode. It must identify the actual Memex endpoint and auth headers, create
isolated test projects, stream progress without a short client timeout, expose
approval decisions, and return actual model/provider/context metadata. It must
also provide a safe contention test that observes GPU queue state without
disruptive Friday requests.

Before live cases, capture model identity and digest, Ollama/provider version,
configured context map, effective context for each request, GPU residency, and
health. Do not treat a successful HTTP status or synthetic authenticated header
as browser authentication proof. Do not claim long-context success from the
configured 122,880-token maximum; the long case must recover facts from a real
large input. Any fallback, cloud escalation, or wrong model identity invalidates
that case as Qwen evidence while remaining evidence for recovery behavior.

