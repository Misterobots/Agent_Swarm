# Relay — Roadmap

**Relay** is the project codename for the personal, Jarvis-style voice assistant being built
on top of the BMO hardware (wake-word device, GPU-backed TTS/STT, and the vault-grounded
conversational brain). The assistant's own in-conversation name is separate from the project
name: it speaks as **BMO ("Beemo")** as of 2026-07-02 (`services/bmo_brain/persona.py`) — the
"Claude"-placeholder persona this doc originally described has been retired now that the
BMO character prompt (already written and proven in `agents/specialized/bmo_persona.py`) was
ported in. "Relay" is what we call the overall system in docs, code comments, and planning —
not the voice itself.

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

**2026-07-02: wake-word/mic-capture consolidated into `bmo_driver.py`.** This tier's own
description was stale — `bmo_driver.py` never actually had wake-word/STT capability; that was
still living in `scripts/voice_satellite.py`, a second process coupled to `bmo_driver.py` only
via a FIFO (`/tmp/bmo_cmd.fifo`) for face-display sync, which was *also* still calling the
now-retired `agent_runtime` `/v1/voice/chat` endpoint end-to-end (its own STT call, its own
brain call, its own `aplay` playback — bypassing `bmo_brain` and `bmo_driver.py`'s TTS
pipeline entirely). Discovered while working the "unify conversation paths" item below, since
deleting `voice_satellite.py` outright would have killed wake-word detection on the live
device. Fixed by porting its Porcupine wake-word loop, VAD recording, speaker-verification
gate, and STT call directly into `bmo_driver.py` as a new thread, wired into the *existing*
`chat()` (→ `bmo_brain`) and `handle_text_interaction()` (→ TTS/face/playback, already
hardened) methods — `bmo_driver.py` is now the single, self-sufficient canonical script.
`scripts/voice_satellite.py` (+ its `-Justin-PC`/`_pi_template` variants) and the
`bmo_satellite.service` unit are retired. **Not yet verified against real hardware** — no way
to test Porcupine/mic capture from a dev machine; needs a live-deployment pass with the user
(sync `bmo_driver.py`, disable the old `bmo_satellite.service`, restart `bmo.service`, test a
real "Hey Beemo").

Remaining known gaps at this tier: no automated tests (only the manual `scripts/bmo_sandbox.py`
harness), no barge-in/interrupt support, and the `-Justin-PC` file-pair pattern (duplicate
service/launch files for a second deployment target) still has no single source of truth.

### Tier 1 — Grounded chat (done)

`services/bmo_brain/main.py` recalls vault memories, injects them as context, and answers as
BMO in character (`services/bmo_brain/persona.py`, ported from `agents/specialized/bmo_persona.py`
— see structural cleanup #2). It serves both Home Assistant's native Ollama/OpenAI-Conversation
integration and, as of 2026-07-02, the Pi driver directly. A full-prompt override is still
available via `BMO_PERSONA` (note: must be added manually to the `bmo-brain` service's
`environment:` block in `execution_plane/docker-compose.yml` — it is not read from `.env`
automatically); the old `BMO_ASSISTANT_NAME`/`BMO_OWNER_NAME` name-templating mechanism is
gone now that the persona is a fixed character rather than a configurable placeholder name.

**2026-07-03: vault recall is actually live.** `VAULT_URL`/`VAULT_OWNER` had been unset since
this service was first stood up, so recall (and, once it shipped, the memory write below) had
been silently inert this whole time — every response was answering blind. The persona swap
above made this visible: without the old "Claude" persona's explicit "you have access to a
private memory vault" framing, the model started actively denying having vault/MemPalace
access instead of just not knowing (fixed in `_answer()`'s system-prompt text, which now
states the capability explicitly rather than relying on the persona to). Root config gap fixed
separately: `execution_plane/.env` now sets `BMO_VAULT_URL=http://192.168.2.102:8200`
(MemPalace, on Hopper) and `BMO_VAULT_OWNER=misterobots` (confirmed via `memex_palace` — that
owner_id holds the real 192 memories; `default`/`justin` hold none). `/health` now reports
`vault: true`, and a real query pulled real recalled memories end to end.

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
  Live end-to-end verified 2026-07-02 against real HA plus an exposed entity
  (light.living_room_light_right, both on and off, confirmed via independent state checks).
  That pass also caught and fixed a real bug: `_answer()` was dropping HA's tool-result
  messages and the assistant's own prior tool_calls turn from the conversation history on every
  round of HA's tool-calling loop, so a failed target resolution just re-guessed the same tool
  call forever until HA's iteration cap gave up. Fixed by preserving `role: "tool"` messages and
  content-empty assistant turns in `_answer()`'s message filter.
- **Self-executing tools for non-HA callers (done 2026-07-02).** The passthrough model above
  only works for callers that supply their own `tools` array and can execute the resulting
  `tool_calls` themselves (HA does both). The Pi driver can't — it just wants an answer back.
  `_answer()` now branches: no `tools` in the request → `bmo_brain` offers its own tool set
  (`services/bmo_brain/tools.py`: weather via Open-Meteo, time/date, news via RSS, a simple
  DuckDuckGo web search, and HA device control via direct REST calls), executes any `tool_calls`
  itself, feeds results back as `role: "tool"` messages, and loops (capped, graceful fallback)
  until the model returns final text — only text is ever returned to these callers. Ported from
  `agents/specialized/voice_assistant.py`'s phi-Agent-based tool set (retired — see structural
  cleanup #1), reimplemented standalone since `bmo_brain`'s Dockerfile can't reach the `agents/`
  package tree. Device-control here uses direct HA REST calls (same mechanism the old path
  used), not the HA-exposure-list authorization boundary the HA passthrough path deliberately
  relies on — this is a real difference in trust model between the two callers, not an oversight
  (the Pi driver is a trusted first-party client; HA's tool-calling passthrough is scoped
  because HA's own opt-in exposure list is what makes that path safe for HA to drive).

Not yet built:

- **Delegation to `agent_runtime`'s swarm/coordinate pipeline** for "go build X" / "go research X"
  voice requests — a separate action capability from device control, still unwired.
- **Tool-use confirmation tuning.** The live test showed the model doesn't reliably recognize
  "the tool already succeeded, stop and confirm" — one exchange took 6 rounds of `HassTurnOff`
  before settling on a text reply, and that reply hedged ("let's try specifying it more clearly")
  even though the action had already worked. The `PERSONA` prompt in `bmo_brain/main.py` says
  nothing about tool-use behavior today. Small, cheap follow-up: add explicit guidance (e.g.
  "once a tool call succeeds, confirm in one short sentence and stop calling tools").

### Tier 3 — Memory that writes back (basic write shipped 2026-07-02)

Vault recall used to be one-directional: `bmo_brain` read from the vault, nothing wrote to it.
`_store_memory()` now fires a background write (`{VAULT_URL}/v1/extract`, same `owner_id`
convention as the read path) after every answer that produced real text — live as of
2026-07-03 now that `VAULT_URL`/`VAULT_OWNER` are actually configured (see Tier 1). Ported
from `voice_assistant.py`'s equivalent
(which wrote to MemPalace directly with a different `agent_id`-based convention — standardized
on `owner_id` here to match `bmo_brain`'s own read path, so anything written can actually be
recalled later by the same query shape). No judgment layer yet: every exchange with a text
reply gets stored, with no filtering of conversational noise vs. what's actually worth
persisting — that discernment is still not built.

## Structural cleanup still owed

These aren't new capabilities, but they're blockers to building Tier 2/3 cleanly on top of the
current foundation:

1. **~~Unify the two conversation paths.~~ Done 2026-07-02.** `bmo_brain` is now canonical for
   both HA and the Pi driver (`agents/bmo_voice/bmo_driver.py`'s `chat()`). Old path retired:
   `agents/specialized/voice_assistant.py`, `agent_runtime`'s `/v1/voice/chat` route, and the
   `scripts/voice_satellite.py` family are all deleted. This turned out to also require
   reconstructing wake-word/mic-capture inside `bmo_driver.py` (see Tier 0) since
   `voice_satellite.py` had been quietly doing that job too — not anticipated when this item
   was originally written.
2. **~~Collapse persona into one source.~~ Mostly done 2026-07-02.** `services/bmo_brain/persona.py`
   now carries the BMO/Beemo character (ported from `agents/specialized/bmo_persona.py`,
   which stays the reference copy — see its module docstring). Not a true single source: it's
   a manual copy, not an import, because `bmo_brain`'s Dockerfile only `COPY`s its own
   directory and can't reach `agents/`. A real single source would need a shared package both
   services can install, or a build-time copy step — not done, flagged here for whoever hits
   persona drift next.
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

Updated 2026-07-02: steps 1-3 below are done. Actual order ended up matching the plan —
device control first, then path unification (which pulled persona collapse and a basic
memory write along with it, since porting the Pi driver onto `bmo_brain` meant it needed
tools and character voice too, not just a URL change).

1. ~~Build Tier 2's first slice: HA device-control via tool-calling passthrough in
   `bmo_brain`.~~ Done 2026-07-02.
2. ~~Unify the conversation path (structural cleanup #1).~~ Done 2026-07-02 — turned out to
   also require Tier 0's wake-word reconstruction and most of Tier 2's self-executing tool
   loop, not just a redirect.
3. ~~Collapse persona (#2).~~ Done (as a copy, not a true single source) 2026-07-02.
4. **Live-deploy and verify against the physical Pi.** Everything above is code-complete and
   `py_compile`-clean but unverified against real hardware — needs the user, a real "Hey
   Beemo," and someone watching `bmo_brain`/`voice_engine` logs. This is the actual next step,
   ahead of new capability work, since nothing past this point matters if the live device
   doesn't work.
5. Build Tier 2 swarm/coordinate delegation — the heavier action capability, reuses
   `agent_runtime` infrastructure that already exists.
6. Tune tool-use confirmation behavior (Tier 2 follow-up above) and add a judgment layer to
   Tier 3's memory writes (right now everything gets stored, no filtering).
7. Docs rewrite + test coverage + observability can happen in parallel with any of the above;
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

**Update 2026-07-02:** the persona swap-in this section originally deferred as a separate
"content/asset task" ended up landing as part of path unification instead — the Pi driver
needed the BMO character prompt regardless, once it became bmo_brain's caller too, so it
wasn't really separable in practice. What's still genuinely deferred: actual TTS voice
cloning (making `voice_engine`'s Qwen3-TTS output sound like a specific BMO voice rather than
its default voice) — that remains a content/asset task, independent of everything above,
whenever voice samples are ready.
