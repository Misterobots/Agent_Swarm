# Relay — Roadmap

**Relay** is the project codename for the personal, Jarvis-style voice assistant being built
on top of the BMO hardware (wake-word device, GPU-backed TTS/STT, and the vault-grounded
conversational brain). The assistant's own in-conversation name is separate from the project
name: it currently goes by **"Claude"** (after Claude Shannon, a placeholder) and is expected
to take on the **BMO** persona once that character work is done. "Relay" is what we call the
overall system in docs, code comments, and planning — not the voice itself.

This doc exists because there was previously no forward-looking plan for this system anywhere
in the repo — only a single inline comment (`services/bmo_brain/main.py:11`) gesturing at a
"Tier-2 (later)" delegation feature. Written 2026-07-01 after a full foundation review and a
ship-correction pass that retired the dead RVC TTS stack (commit `19eb52e`).

## Current state, by tier

### Tier 0 — Voice I/O (done, recently hardened)

Wake word → Pi driver (`agents/bmo_voice/bmo_driver.py`) → Qwen3-TTS/STT engine
(`services/voice_engine/main.py`) → speaker. This loop works end-to-end. As of the 2026-07-01
correction pass:

- The dead RVC stack (`bmo-voice` service, `server.py`, RVC/Kokoro/fairseq deps) is fully
  retired; `voice-engine` is the sole owner of host port 8100.
- `/tts` and `/speak` no longer leak temp files; `generate_voice_clone` calls are serialized
  behind an `asyncio.Lock` (Qwen3-TTS inference isn't reentrant); model loading runs off the
  event loop so `/health` can report `503` while loading instead of the server refusing
  connections outright.
- The driver writes each response to a unique temp file (no more overlapping-interaction
  races on a shared filename) and derives the playback timeout from the WAV's actual duration
  instead of a flat 10s that could cut off longer replies.

Remaining known gaps at this tier: no automated tests (only the manual `scripts/bmo_sandbox.py`
harness), no barge-in/interrupt support, and the `-Justin-PC` file-pair pattern (duplicate
service/launch files for a second deployment target) still has no single source of truth.

### Tier 1 — Grounded chat (done, narrow)

`services/bmo_brain/main.py` recalls vault memories, injects them as context, and answers via
Ollama. It serves Home Assistant's native Ollama/OpenAI-Conversation integration. As of the
correction pass, its default persona is name-and-owner configurable via `BMO_ASSISTANT_NAME`
and `BMO_OWNER_NAME` env vars, with a full-prompt override still available via `BMO_PERSONA`
(note: `BMO_PERSONA` must be added manually to the `bmo-brain` service's `environment:` block
in `execution_plane/docker-compose.yml` — it is not read from `.env` automatically).

Until the change below, this tier was read-only and single-purpose: it could answer questions
grounded in recalled memories, and nothing else — no tool use, no device control, no delegation.

### Tier 2 — Actions (first slice shipped 2026-07-02; the rest not started)

The biggest gap between what exists and what "Relay" needs to be a Jarvis-style assistant
rather than a grounded voice chatbot. Shipped so far:

- **Home Assistant device control (done).** `bmo_brain` now forwards a caller's `tools` array
  to Ollama verbatim and propagates any `tool_calls` back instead of collapsing to text —
  passthrough, not a custom intent-detector. HA's own "Control Home Assistant" feature owns
  intent detection, entity resolution, and execution; entity exposure (opt-in in HA's Assist
  settings) is the sole authorization boundary, by design. Both API surfaces are covered:
  `/v1/chat/completions` translates Ollama's tool_calls into OpenAI's shape (JSON-string
  arguments, `finish_reason: "tool_calls"`); `/api/chat` passes Ollama's native shape through
  unchanged. `/api/show` now advertises the `"tools"` capability, which HA's Ollama integration
  needs in order to offer "Control Home Assistant" for this model at all. Requests without
  `tools` (e.g. the Pi driver) are byte-identical to before — verified via a mocked-Ollama
  functional test covering both the tool-call and plain-text paths on both endpoints.
  Still needs real end-to-end verification against live HA + an exposed entity, and enabling
  "Control Home Assistant" in HA's integration config (manual, out of code scope).

Not yet built:

- **Delegation to `agent_runtime`'s swarm/coordinate pipeline** for "go build X" / "go research X"
  voice requests — a separate action capability from device control, still unwired.

### Tier 3 — Memory that writes back (not started)

Vault recall today is one-directional: `bmo_brain` reads from the vault, nothing writes to it.
For the assistant to "learn" from conversations rather than only from manually-curated vault
entries, conversations need a path to store new memories (e.g. a `memex_remember`-style write),
with some judgment about what's worth persisting vs. conversational noise.

## Structural cleanup still owed

These aren't new capabilities, but they're blockers to building Tier 2/3 cleanly on top of the
current foundation:

1. **Unify the two conversation paths.** The Pi satellite (`scripts/voice_satellite.py`) still
   talks to `agent_runtime`'s `voice_assistant.py` via `/v1/voice/chat`, while Home Assistant
   talks to `bmo_brain` via `/v1/chat/completions` — different personas, different (lack of)
   grounding, no documented rule for which path is canonical. Tier 2 delegation logic shouldn't
   be built twice.
2. **Collapse persona into one source.** `agents/specialized/bmo_persona.py` is the fuller,
   more detailed persona (character rules, emotion mapping) but `bmo_brain/main.py` defines its
   own separate, thinner persona inline. These should converge before Tier 2 adds more surface
   area that would need to stay in sync across both.
3. **Docs rewrite.** `docs/bmo_complete_guide.md`, `docs/bmo_deployment_guide.md`,
   `docs/bmo_troubleshooting.md`, and `docs-site/docs/admin-guide/bmo.md` all still describe the
   retired Kokoro+RVC pipeline (models, ports, `--method rmvpe`). An operator following them today
   would try to stand up services that no longer exist.
4. **Automated test coverage.** `scripts/bmo_sandbox.py` is a solid manual regression harness
   (persona-rule checks, batch prompts, TTS smoke test) but there is no CI-run test suite for
   `bmo_brain`'s API-translation logic or `voice_engine`'s endpoints. This is exactly the kind
   of code that breaks silently on a dependency upgrade (e.g. HA's Ollama integration version).
5. **Voice-path observability.** Langfuse tracing is wired for `agent_runtime` but doesn't reach
   `bmo_brain` or `voice_engine` — there's no trace of a voice interaction end-to-end.

## Suggested sequencing

Updated 2026-07-01: reordered after deciding to take the HA device-control slice first
(see "Sequencing decision" below) rather than doing structural cleanup before any Tier 2 work.

1. **Build Tier 2's first slice: HA device-control via tool-calling passthrough in
   `bmo_brain`.** Confirmed via research that HA's native Ollama integration already supports
   "Control Home Assistant" tool-calling, gated by opt-in entity exposure, with qwen3:8b
   (bmo_brain's default model) specifically recommended for it. This only touches
   `services/bmo_brain/main.py` — no need to resolve the dual-path question first, since HA
   already owns entity/service execution regardless of what the Pi satellite path does.
2. Unify the conversation path (structural cleanup #1) — staged directly after the feature
   above. Still gates further Tier 2 work (swarm/coordinate delegation, below) so it shouldn't
   slip much further.
3. Collapse persona (#2) alongside #2 above — cheap to do at the same time since both touch
   the same files.
4. Build Tier 2 swarm/coordinate delegation — the heavier action capability, reuses
   `agent_runtime` infrastructure that already exists.
5. Tier 3 memory writes — highest payoff for "feels like Jarvis," but wants Tier 2's intent
   detection as a prerequisite (need to distinguish "remember this" from ordinary chat).
6. Docs rewrite + test coverage + observability can happen in parallel with any of the above;
   they're not blocking but the debt compounds the longer they're deferred.

### Sequencing decision (2026-07-01)

Originally planned to unify the conversation path before any Tier 2 work, to avoid building
action-handling logic twice. In practice, HA device control is scoped entirely to the
HA-facing path (`bmo_brain`) — HA owns entity resolution and service execution itself via its
own tool-calling contract, so bmo_brain only needs to stop swallowing `tools`/`tool_calls`.
Nothing about that requires deciding what the Pi-satellite path does. Deferring the
path-unification work costs nothing for this specific slice, and shipping the device-control
win first delivers the headline "assistant that can act" capability sooner. The
conversation-path fix is staged as the very next item once this feature lands.

BMO-the-character (voice clone, full persona swap-in) is intentionally not on this list — it's
a content/asset task independent of the Relay system's technical maturity, and can land
whenever the voice/character assets are ready, on top of whatever tier is current at the time.
