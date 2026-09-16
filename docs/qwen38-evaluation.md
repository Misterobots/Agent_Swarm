# Qwen 3.8 evaluation suite

This suite qualifies the opt-in `qwen3.8:27b` Memex profile in six cases:

1. code review against seeded defects;
2. multi-file implementation with hidden deterministic checks;
3. approval and project isolation;
4. image understanding from fixed fixtures;
5. long-context fact recovery;
6. provider recovery and contention behavior.

The suite has two modes. `mock` is offline and deterministic, but it executes
real temporary-project flows: files are created and read, approved writes are
performed, denied writes and commands are blocked, and the build case runs a
hidden pytest command. Mock output is never evidence that the live model, GPU
queue, browser authentication, or Memex tools work. `live` uses the existing
Memex dev API after the caller supplies authentication and explicitly passes
`--live`.

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

## Live adapter and qualification prerequisites

The live adapter targets `http://127.0.0.1:8009` by default and implements:

- blank project creation/deletion at `/v1/dev/projects`;
- session creation at `/v1/dev/sessions`;
- tree, read, and write operations at `/v1/dev/files`;
- streamed `/v1/chat/completions` with `context_profile`, project/session
  identity, attachments, and contract metadata extraction;
- approval calls at `/api/v1/dev/approve/{call_id}` and
  `/api/v1/dev/deny/{call_id}`;
- Qwen-tokenizer measurement for the long case when
  `QWEN38_TOKENIZER_PATH` points to a local tokenizer.

Credentials must be supplied by the caller through either
`QWEN38_EVAL_HEADERS_JSON` or `QWEN38_EVAL_BEARER_TOKEN`. The adapter never
creates an `X-authentik-*` identity, and reports only `auth_source` from the
configured caller credentials. A synthesized header or successful HTTP status
is not browser authentication proof.

Run only after the integrator has completed the development integration and the
coordinator has released the live-run gate:

```powershell
$env:QWEN38_EVAL_HEADERS_JSON = Get-Content .\caller-headers.json -Raw
python scripts/qwen38_eval/runner.py --mode live --live --base-url http://127.0.0.1:8009 --report artifacts/qwen38-live.json
```

The live runner creates and deletes unique blank projects. It does not touch a
live repository. The inspected original dev default is explicitly recorded as
`qwen3:14b`, from the dev runtime's effective `_DEFAULT_CHAT_MODEL`/`PRIMARY_MODEL`
configuration. The baseline adapter replays the same fixture inputs and case
prompts with that model; it never substitutes Qwen 3.8 for the baseline.
For image cases, `qwen3:14b` is not sent an image. The baseline adapter requests
the existing legacy vision route. Read-only local Ollama inspection observed
`minicpm-v:latest` installed with `completion,vision` capabilities, and the
legacy candidate order begins with that model. Live acceptance records the
actual `actual_model` returned by the runtime; an installed legacy VLM is not
counted as a Qwen fallback failure.

Use the staged gate first:

```powershell
python scripts/qwen38_eval/runner.py --mode live --stage smoke --live --baseline-model qwen3:14b
python scripts/qwen38_eval/runner.py --mode live --stage exhaustive --live --smoke-passed --runs 3 --baseline-model qwen3:14b
```

The smoke stage runs one bounded review and four-way vision transport check for
Qwen and the existing-default baseline. Only after that passes should the
exhaustive stage run three positive repetitions and three identical-input
baseline repetitions. Build approval requires an authenticated human approval
callback unless `--fixture-approval` is explicitly enabled with authorized
caller credentials. Recovery and contention remain blocked until the lead
supplies safe transport-fault and queue-observation hooks. The long case is
blocked when the actual Qwen tokenizer is unavailable, rather than treating a
configured context maximum as a success.
The approvals case can be exercised without a human click by adding
`--fixture-approval`; this sends a deny decision through the configured caller
credentials after a real approval event and verifies that the mutation did not
occur. It does not create an identity, grant a session/workspace rule, or prove
browser authentication.

Authentication requirements by case:

| Case | Direct API credentials | Browser/user authentication for UI proof |
|---|---|---|
| Review | caller credentials | required for UI workflow proof |
| Build | caller credentials plus human approval callback | required |
| Approvals/isolation | caller credentials plus human approval/denial | required |
| Vision | caller credentials | required for attachment UI proof |
| Long context | caller credentials and local Qwen tokenizer | required for context-selector UI proof |
| Recovery/contention | caller credentials plus lead fault/queue hooks | optional for API, required for UI status proof |

## Audit status against the acceptance specification

The runner now contains the required seeded review defects at actual lines 18,
42, and 77; the mock build performs writes and executes hidden pytest checks;
the mock approval case covers denied actions, owner isolation, and checkpoint
resume without a duplicate mutation; and the vision fixtures include separate
chart and dashboard screenshot attachments. The live vision case sends a chart
through ordinary chat and a screenshot through Code, and the live context-probe
implementation defines six actual tokenizer-sized probes: 70% and 90% of each
of `chat`, `project`, and `long`.

The following acceptance subchecks remain blocked and are reported individually
instead of being converted into an aggregate pass:

- three sequential positive runs and identical-input existing-default baselines
  are implemented with the observed `qwen3:14b` baseline identity, but remain
  gated until the coordinator releases live inference;
- live approval policy requires the coordinator's authorized authenticated
  fixture callback or UI callback. The adapter has the approve/deny endpoints,
  but it never generates a decision or broadens a grant;
- live resume duplicate-mutation evidence requires the integrated checkpoint
  event and resume contract;
- live recovery/contention requires a safe transport-fault injection hook and
  queue observation hook from the lead;
- the six tokenizer probes require `QWEN38_TOKENIZER_PATH` to exist and point
  to a locally loadable Qwen tokenizer.

The current read-only prerequisite check found the dev endpoint reachable, but
no configured evaluation headers or bearer token and no configured tokenizer
path. No inference request was sent. These checks report only booleans and never
print credential values.

With one serialized heavy-model lane, the bounded worst-case estimate is about
10 hours: three 80-minute positive suites (4 hours), three 80-minute baseline
suites (4 hours), and six context probes at up to 20 minutes each (2 hours),
plus project setup and cleanup. Warm successful cases should finish much sooner;
the 10-hour figure is the sum of declared case deadlines, not a performance
claim.

Before live cases, capture model identity and digest, Ollama/provider version,
configured context map, effective context for each request, GPU residency, and
health. Do not treat a successful HTTP status or synthetic authenticated header
as browser authentication proof. Do not claim long-context success from the
configured 122,880-token maximum; the long case must recover facts from a real
large input. Any fallback, cloud escalation, or wrong model identity invalidates
that case as Qwen evidence while remaining evidence for recovery behavior.
