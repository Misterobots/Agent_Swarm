# Relay — Roadmap

**Relay** is the project codename for the personal, Jarvis-style voice assistant being built
on top of the BMO hardware (wake-word device, GPU-backed TTS/STT, and the vault-grounded
conversational brain). The assistant's own in-conversation name is separate from both the
project name and the hardware's name: it speaks as **Friday** as of 2026-07-03
(`services/bmo_brain/persona.py`, `FRIDAY_SYSTEM_PROMPT`) — a JARVIS-successor-style AI
assistant persona, matching this project's own "Jarvis-style" framing. BMO-the-character
(`BMO_SYSTEM_PROMPT`, same file) was briefly wired as the active persona on 2026-07-02 but
turned out to be ahead of where the project actually wants to be right now — BMO-the-character
remains the *eventual* goal for this hardware, kept in the file for later, not the current
voice. "Relay" is what we call the overall system in docs, code comments, and planning — not
the voice itself; "BMO" is what we call the physical hardware/Pi project — also not the voice.

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
`bmo_satellite.service` unit are retired.

**Partially live-verified 2026-07-03.** Deployed to the physical Pi; wake word detection
itself confirmed working twice on real hardware ("Hey Beemo" triggered Porcupine correctly).
Two real bugs found and fixed in that pass: (1) the systemd unit's `--input_device 3` had zero
input channels and failed to open at all — `_wake_word_loop` now verifies the configured
device first and falls back to name-based auto-detection (matching what `voice_satellite.py`
always did) rather than trusting an unverified index; (2) the STT request in
`handle_voice_interaction()` had no timeout, so a slow/unreachable `voice_engine` hung for
~2 minutes before an unrelated outer timeout surfaced a blank error message — fixed with an
explicit 30s timeout and better error logging. Full round-trip (wake word → STT → brain →
TTS → playback) has not yet been retested after those fixes — still the next concrete step.

**Google Home entry point — staged, not yet done (2026-07-03).** A third way to reach the same
brain, alongside HA's Assist pipeline and the Pi: "Hey Google, talk to Friday" via HA Cloud's
(Nabu Casa) Google Assistant conversation relay. `cloud`, `google_assistant`, and
`ollama.conversation` are all confirmed active HA components, but the actual relay toggle
lives in Nabu Casa's own UI (Settings → Home Assistant Cloud → Google Assistant) and can't be
inspected or set via HA's REST API — needs the user to walk through renaming the Assist
pipeline to "Friday," enabling the conversation-relay exposure there, and testing live. No
code changes needed for this one; it's pure configuration once bmo_brain speaks as Friday.

Remaining known gaps at this tier: no automated tests (only the manual `scripts/bmo_sandbox.py`
harness), no barge-in/interrupt support, and the `-Justin-PC` file-pair pattern (duplicate
service/launch files for a second deployment target) still has no single source of truth.

### Tier 1 — Grounded chat (done)

`services/bmo_brain/main.py` recalls vault memories, injects them as context, and answers as
Friday in character (`services/bmo_brain/persona.py`, `FRIDAY_SYSTEM_PROMPT` — see the intro
above for why BMO isn't the active persona yet). It serves both Home Assistant's native
Ollama/OpenAI-Conversation integration and, as of 2026-07-02, the Pi driver directly — same
brain, same persona, both surfaces. A full-prompt override is still available via
`BMO_PERSONA` (note: must be added manually to the `bmo-brain` service's `environment:` block
in `execution_plane/docker-compose.yml` — it is not read from `.env` automatically; the env
var name is a historical leftover, it overrides whichever persona is active, not just BMO's).

**2026-07-03: vault recall is actually live.** `VAULT_URL`/`VAULT_OWNER` had been unset since
this service was first stood up, so recall (and, once it shipped, the memory write below) had
been silently inert this whole time — every response was answering blind. The persona swap
above made this visible: without the old "Claude" persona's explicit "you have access to a
private memory vault" framing, the model started actively denying having vault/MemPalace
access instead of just not knowing (fixed in `_answer()`'s system-prompt text, which now
states the capability explicitly rather than relying on the persona to).

Root config gap fixed separately, and initially pointed at the wrong store — two distinct
MemPalace-shaped systems exist on this network and they are not interchangeable:
- **"Bush"** (`192.168.2.107`, undocumented elsewhere in this repo) is the real personal
  vault — 7,136+ memories (still growing) under owner_id `vlt-e0eb20075b9b72b6` (the vault's
  own identity-scoped id; distinct from the `misterobots` + two hash identities in
  `MEMPALACE_VAULT_FOR`, which gate *who's allowed to read* the vault — a different role from
  the id memories are *stored under*). `execution_plane/.env` now points here.
- **Hopper's MemPalace** (`192.168.2.102:8200`) is a separate, much smaller store — that one
  belongs to Memex, not this vault. Tried first (owner_id `misterobots`, 192 memories) before
  the correction above; wrong store, not wrong syntax — `/health` reported `vault: true` and
  recall worked fine against it, it was just the wrong data.

`/health` now reports `vault: true` against Bush, and a real query pulled real recalled
memories end to end (correctly referenced this project by its own codename, "Relay").

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
- **~~Tool-use confirmation tuning.~~ Done 2026-07-06.** The live test showed the model doesn't
  reliably recognize "the tool already succeeded, stop and confirm" — one exchange took 6 rounds
  of `HassTurnOff` before settling on a text reply, and that reply hedged even though the action
  had already worked. Reproduced live again on 2026-07-06 (a phone/HA-app "no response" report
  turned out to be this: `bmo_brain` logs showed 3 rounds of `HassTurnOff` over 24 seconds before
  a real text answer, and HA's Assist UI reads that gap as unresponsive even though the device
  state change had already happened). Fixed by adding an explicit stop-condition to both personas
  in `services/bmo_brain/persona.py`'s "USING YOUR TOOLS" section: "Once a tool call succeeds,
  stop. Do not call the same tool again to double check it worked." `bmo-brain` doesn't
  bind-mount its code (unlike `voice-engine`) — needed a `docker compose build bmo-brain` +
  `up -d`, not just a restart. Retested live from the phone 2026-07-06: round-trip dropped from
  3 rounds/24s to 2 rounds/~16s — better, but the model still doesn't reliably settle in one
  round. Not re-opened as a separate item since the practical symptom (Assist reading a slow
  reply as "no response") is resolved; the residual redundant round is cosmetic/latency, not
  correctness.
- **Room-wide device targeting picks one remembered entity instead of the whole area (found
  2026-07-06).** Same live retest surfaced a second, distinct bug: "turn off the living room
  lights" (plural, no single device named) reported success but only one of the two physical
  lights actually turned off. Added verbose tool-call/result logging to `bmo_brain/main.py`
  (`_answer()` now logs incoming `role: tool` results and prior `tool_calls`, and both
  `/api/chat`/`/v1/chat/completions` emit call arguments, not just names) to see exactly what
  happened: the model's first two `HassTurnOff` attempts mixed a specific `name` with
  `area`/`device_class` in the same call (`{name: 'living_room_light_right', area: 'living
  room', device_class: 'light'}`) — HA rejected both as `InvalidSlotInfo` — then it fell back to
  a bare `{name: 'light.living_room_light_right'}`, which succeeded but only ever targeted the
  one entity it already knew by name, never the room's other light. Root cause is on the HA
  side, not `bmo_brain`: there's no light-group entity for "the living room," so a plural/
  area-wide request has no single target to resolve to and the model guesses. Real fix (not yet
  done, needs the user in HA's UI): create a Light Group combining both living-room light
  entities under one name so room-wide requests have an unambiguous target regardless of what
  the model does. Shipped as a defense-in-depth complement: both personas in `persona.py` now
  say "when a request names a whole room or area, target by area and device type only — do not
  also include a specific device name in that call, and do not narrow a room-wide request down
  to one device you happen to remember." Not a substitute for the HA-side group fix, since it
  depends on the model reliably following a prompt instruction rather than making the ambiguity
  structurally impossible.

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
2. **~~Collapse persona into one source.~~ Mostly done 2026-07-02, superseded 2026-07-03.**
   `services/bmo_brain/persona.py` carries both `BMO_SYSTEM_PROMPT` (ported from
   `agents/specialized/bmo_persona.py`, which stays the reference copy — see its module
   docstring) and `FRIDAY_SYSTEM_PROMPT` (the active default as of 2026-07-03, no separate
   canonical source elsewhere — Friday only exists in `bmo_brain`, there's no Pi-hardware
   equivalent of `bmo_persona.py` for her). BMO's copy is still not a true single source: it's
   a manual copy, not an import, because `bmo_brain`'s Dockerfile only `COPY`s its own
   directory and can't reach `agents/`. A real single source would need a shared package both
   services can install, or a build-time copy step — not done, flagged here for whenever BMO
   becomes the active persona again and this starts mattering.
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
