# Qwen 3.8 integration contract

Status: integration baseline

Owner: Qwen 3.8 integration lead

Model identity: `qwen3.8:27b` through the existing local Ollama provider. The unavailable remote identity `qwen3.8-27b-fp8` remains a separate catalog entry.

This contract is the handoff boundary for the Luna medium agents implementing the approved Qwen 3.8 plan. It is intentionally written against the existing Memex APIs and event stream. Agents must preserve unrelated dirty work, must not deploy, and must not change the global primary model.

## Runtime and rollout boundary

- Development target: `agent_runtime_dev` mounting `Memex_Core`.
- Local production target: `agent_runtime` mounting `Agent_Swarm`, with its existing `services/code_gateway` adapter. Production integration must adapt to that gateway; it must not replace `Agent_Swarm` with this checkout.
- Rollout order: development qualification, then Lovelace local production qualification.
- Out of scope: Turing, Friday, embeddings, safety routing, cloud escalation policy, and primary-model defaults.
- Existing `Agent_Swarm` WIP is preserved. The production adapter must be reviewed against its current gateway and compose state.

## Shared behavior contract

### Model and role snapshot

At run start, resolve the owner-scoped Team Builder role configuration once and attach the immutable role-to-model map to the run context. Every coordinator, architect, coder, DevOps, researcher, analyst, verifier, and synthesis stage reads that snapshot. A later Team Builder edit cannot change an active run.

Every model queue, worker, tool-progress, completion, checkpoint, resume, and error event that identifies a model must include:

```json
{
  "requested_model": "qwen3.8:27b",
  "actual_model": "qwen3.8:27b",
  "provider": "ollama",
  "fallback": false
}
```

Fallbacks set `fallback: true` and identify the actual fallback model. A catalog tier, estimated load time, or `vram_gb` value is not evidence that VRAM is reserved. Actual inference must acquire and release the existing GPU lease, including cancellation and error paths.

### Context profiles

The request-facing profile is one of `chat`, `project`, or `long`:

| Profile | Effective Qwen context | Use |
| --- | ---: | --- |
| `chat` | 32768 tokens | ordinary chat and image analysis |
| `project` | 65536 tokens | Code workspace and swarm project work |
| `long` | 122880 tokens | explicitly selected long repository/document analysis |

Omitted profile derives from the request mode: ordinary chat/image uses `chat`; Code and swarm project work uses `project`; `long` is explicit only. Other models retain current behavior in this integration.

The request and run metadata expose both `context_profile` and `effective_context_tokens`. The production code gateway must receive the effective value through its existing adapter; its current Qwen map is a ceiling/default adapter setting and must not silently override an explicit task profile. Reserve output/tool headroom and return a clear limit error rather than silently truncating.

### Approval and project safety

Existing approval modes and owner/project isolation remain authoritative. Plan mode may read only after the normal approval flow and may not mutate. Approved implementation work must remain inside the selected project. The evaluation runner uses isolated fixture projects and never the live repository.

## Disjoint write ownership

Agents may read across the repository but may write only their assigned paths. Shared-file changes are submitted to the integration lead as a patch or commit; agents do not edit lead-owned files directly.

| Owner | Write paths | Responsibility |
| --- | --- | --- |
| Integration lead | `agents/main.py`, `agents/config.py`, `agents/model_registry.py`, `execution_plane/docker-compose.yml`, `services/code_gateway/**` when adapting production, plus contract/integration notes | shared request/event contracts, model catalog, profile resolution, production adapter, compose wiring, lease metadata, integration and rollout |
| Agent A — roles | `agents/coordination/**`, role-resolution modules, role snapshot tests outside E-owned paths | owner-scoped role snapshot and propagation through workers/checkpoints; no `main.py`, config, registry, compose, gateway, UI, or E paths |
| Agent B — context/provider | `agents/providers/**`, provider/request helper modules, provider-focused tests outside E-owned paths | context profile validation, effective token propagation, Ollama/provider options; lead owns `agents/config.py` and gateway adapter changes |
| Agent C — vision | `agents/handlers/vision.py`, vision helper modules, vision-focused tests outside E-owned paths | Qwen vision selection, capability checks, attachment transport, explicit fallback reporting |
| Agent D — UI | `ui/src/components/**`, `ui/src/lib/**`, `ui/src/types/**`, UI docs outside E-owned paths | Team Builder preset, context selector, model/context/fallback/approval display; no backend shared files |
| Agent E — evaluation | `tests/qwen38_eval/**`, `scripts/qwen38_eval/**`, `docs/qwen38-evaluation.md` only | isolated fixtures, runner, raw result schema, six-case report and reproduction commands |

If a requested edit crosses ownership, stop and return the exact path, reason, and proposed diff to the lead. Do not resolve overlap by broad refactoring.

## Interfaces to preserve or add

The implementation should add the smallest compatible fields to existing request/run models:

```python
ContextProfile = Literal["chat", "project", "long"]

context_profile: ContextProfile | None = None
effective_context_tokens: int | None = None  # response/run metadata
requested_model: str | None = None           # event metadata
actual_model: str | None = None              # event metadata
provider: str | None = None                  # event metadata
fallback: bool = False                       # event metadata
```

The server remains backward compatible when clients omit `context_profile` and the new metadata fields. Invalid profiles fail validation. Existing SSE event names remain stable; extend their payloads rather than creating parallel event types unless the current schema cannot carry the data.

## Integration acceptance gates

- Baseline changes contain only the three prior Qwen edits plus this contract.
- Dev and production adapters both report the actual provider/model and effective context.
- Role configuration is snapshotted at run start and survives checkpoint/resume.
- Qwen vision, 32K chat, 64K project, and explicit 122880 long profiles are individually observable.
- GPU leases are measured at runtime and released on success, failure, cancellation, and timeout.
- E agent runs all six cases in isolated projects and records fallbacks separately from Qwen passes.
- Browser/authenticated UI qualification is performed after the synthesized-header API checks; synthesized headers alone do not qualify the final UI.
- No Turing deployment and no global primary-model change occur in this phase.
