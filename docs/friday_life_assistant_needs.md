# Friday — Life-Assistant Capability Map

Companion to `docs/relay_roadmap.md`. That doc tracks the tiered build of the voice
pipeline (Tiers 0–3: voice I/O, grounded chat, actions, memory write-back). This doc asks a
bigger question: **what does Friday need to become a fully functioning life assistant**, not
just a home-automation voice-command handler — and how much of that already exists in this
repo. Written 2026-07-11 from a full read of the actual code, not from the roadmap's claims
alone; everything cited below was verified against source. Where the roadmap already names a
gap (barge-in, memory judgment layer, no voice-path tests/observability), this builds on it
rather than restating it.

Method note on "exists": this repo has a strong pattern of code-complete-but-unverified
work (the whole 2026-07-09 batch). "Exists" below means the code is in the tree; live-verified
status is flagged where the roadmap records it.

## The one-paragraph diagnosis

Friday today is a **well-built reactive answerer with hands that reach exactly one domain
(the home) and a memory that records everything but judges nothing.** The voice loop, the
grounded-recall loop, and HA device control are real and largely shipped. What separates
this from a life assistant is not more of the same — it's four structural absences: (1)
**Friday cannot speak first** (no proactive channel, no scheduler — every interaction begins
with the user); (2) **Friday cannot own a task over time** (swarm delegation is inert,
synchronous, and loses its result on timeout; there is no reminder, todo, or follow-up
mechanism of any kind); (3) **the Pi surface has no conversational state** (each turn is a
fresh single-message request — the brain literally never sees the previous exchange except
through the memory cache); (4) **the life-data integrations are zero** (no calendar, email,
messaging, notes, or lists — the only external world Friday touches is weather, BBC
headlines, and DuckDuckGo).

---

## Domain 1 — Memory & personal context

**What a life assistant needs.** Episodic memory ("what did I say about the deck last
week"), semantic memory (facts, preferences, people, projects), procedural memory (how
things are done around here), high-precision recall under a voice-latency budget,
consolidation (dedupe, contradiction resolution, updating stale facts), selective
forgetting, a judgment layer deciding what's worth keeping, and a user-facing verb for
"remember this" / "forget that."

**What exists.** This is Friday's most mature life-assistant domain — considerably more
exists than the roadmap's terse Tier 3 section implies:

- **The store**: the Bush vault (`192.168.2.107`, MemPalace-shaped,
  `control_plane/mempalace/app/main.py`), 7,136+ memories under owner
  `vlt-e0eb20075b9b72b6`. The schema already distinguishes `semantic | episodic |
  procedural` (`MemoryCreate`, plus `preference`/`discovery` halls in `_HALL_MAP`), carries
  `domain`, `access_count`, per-memory audit log (`MemoryAuditLog`, `PATCH /v1/memories/{id}`,
  `GET .../audit`), and an **entity knowledge graph** (`Entity`/`EntityRelation`,
  `POST /v1/entities/extract`, `/v1/palace/graph` — typed relations, community detection).
- **Three-tier recall** (`services/bmo_brain/main.py`): `_vault_recall` (semantic, score ≥
  `VAULT_MIN_SCORE` 0.4, limit 6) runs **concurrently** with `_pending_recall` (keyword
  ILIKE over the not-yet-processed queue, `/v1/extract/pending/search`) and
  `local_pending.search_local` (same-day SQLite cache, 2-day prune). Ground-truth injection
  patterns for questions recall can't answer: `_live_status()` and `_vault_stats()`.
- **Three-tier write-back**: `_store_memory()` → local SQLite queue + `/v1/extract/queue`
  (zero LLM cost) → `process_pending` batch (external cron) drains through
  `extract_memories()` (`control_plane/mempalace/app/embeddings.py`). `tool_trace` is
  appended so the extractor can learn device-control lessons from failed/succeeded tool
  calls — and `EXTRACTION_PROMPT` explicitly instructs it to extract those as procedural
  memories. Point-in-time answers (status/count) are deliberately **not** stored
  (`_answer()`'s `if not status_q and not count_q` guard) — a first, narrow slice of
  judgment.
- **A domain-specific procedural memory that actually works**: the learned-synonym table
  (`hass_synonyms.py` + `hass_resolver.py` five-stage resolution, reactive
  correction-learning with the round-guard in `_extract_tool_attempts`). This is the best
  "learning from experience" loop in the system — narrow, but real.

**The gap.**
- **The judgment layer is thinner than it looks and lives in the wrong place.** The *only*
  filter between "every text exchange" and "durable memory" is the `EXTRACTION_PROMPT` rules
  ("Only extract genuinely useful, durable information"), executed nightly by
  `EXTRACT_MODEL` — which defaults to `qwen2.5-coder:14b-instruct-q4_k_m`, a **coder** model
  doing personal-memory curation. There is no dedupe (asking the same question 10 times can
  mint 10 near-identical memories), no contradiction resolution (a changed preference
  coexists with the old one; recall surfaces both), and no decay/forgetting (`access_count`
  is bumped on every search hit but used for nothing).
- **The promotion pipeline is a silent single point of failure.** `process_pending` is
  triggered by an external cron that exists **nowhere in this repo** (verified: the only
  references to `process_pending` are mempalace itself and the roadmap). If that cron dies,
  curated memory silently stops growing; nothing alerts (the `maintenance_router` /
  Alertmanager stack watches infra, not this).
- **No temporal recall.** "What did we talk about Tuesday?" has no path — vault search is
  similarity-only, pending search is keyword-only, and nothing indexes by time for the
  user's benefit.
- **No user-facing memory verbs.** There is no `remember_this` / `forget_that` tool in
  `tools.py`, despite MemPalace having exactly the endpoints for it
  (`POST /v1/memories`, `DELETE /v1/memories/{id}`, both with audit logging).

**Next steps.**
1. Bring the promotion cron **into the repo** (a small scheduler container or a compose
   `cron` sidecar hitting `/v1/extract/process_pending`) and alert on queue age via the
   existing maintenance stack.
2. Add a dedupe/merge pass to `process_pending`: before insert, semantic-search the owner's
   existing memories for near-duplicates (the embedding is already computed) and skip/merge/
   supersede instead of blind-inserting. This is the cheapest 80% of "consolidation."
3. Add `remember_fact` and `forget_about` to `TOOL_SCHEMAS` in `services/bmo_brain/tools.py`
   — explicit user-directed writes should bypass the nightly judgment entirely.
4. Switch `EXTRACT_MODEL` to a general instruct model and add a `created_at`-aware recall
   mode for temporal questions.

---

## Domain 2 — Agency & task execution

**What a life assistant needs.** Acting beyond the light switch: research that comes back
later with an answer, multi-step errands ("book, then confirm, then remind me"), a task
ledger it owns, graduated confirmation (do lights silently; confirm the lock; never touch
finances), and tool breadth that grows safely.

**What exists.**
- Two execution modes through one chokepoint (`_answer()` in `services/bmo_brain/main.py`):
  HA **passthrough** (HA owns execution + the exposure-list authorization boundary, hardened
  by `_sanitize_hass_tool_calls`, the clarify-loop breaker at `HASS_CLARIFY_THRESHOLD`, and
  the resolver) and **self-executing** (`_self_execute_tools`, capped at
  `SELF_TOOL_MAX_ROUNDS` 6) with the `tools.py` set: weather ×2, time/date, BBC RSS news,
  DuckDuckGo `web_search`, four direct-REST HA device tools, and `delegate_to_swarm`.
- `delegate_to_swarm(task, mode)` maps research/build/plan onto `agent_runtime`'s mode flags
  — the bridge to the entire swarm (`agents/church.py` → coordinator → DevHarness workers)
  is *designed*.
- The swarm side (out of scope here but relevant as the delegation target) has real tool
  breadth: `agents/tools/` includes `web_browser.py`, `home_assistant.py`, `mqtt_ops.py`,
  `esphome_ops.py`, `git_ops.py`, file/terminal ops, etc.

**The gap.**
- **Delegation is inert and, even when wired, structurally lossy.** `AGENT_RUNTIME_URL` is
  absent from `bmo-brain`'s environment in `execution_plane/docker-compose.yml` (verified —
  the env block has vault/Ollama/HA vars only). Worse: the tool is synchronous with a 90s
  `SWARM_TIMEOUT`, and on timeout returns "The swarm is still working on that one" — but the
  eventual result **has no way back to the user**. There is no job handle, no polling, no
  callback. Real swarm runs (research mode, build mode) routinely exceed 90s, so the current
  design mostly delivers an apology. Async delegation is blocked on Domain 3 (there is no
  channel for Friday to announce a finished result).
- **No confirmation tiers.** `turn_off_device` executes immediately on any entity the HA
  token can reach. Fine for lights; the same code path would fire a lock or garage door.
  The trust asymmetry the roadmap documents (exposure list for HA callers vs. full-token
  REST for the Pi) grows sharper with every tool added.
- **No task ledger.** Nothing persists an intention. "Remind me to call the vet" has no tool
  to land in; a multi-step errand has no state that survives the exchange.
- Cosmetic but telling: `_self_execute_tools`'s round-exhaustion fallback still says
  *"Beemo tried a few things there but could not finish that one"* — a BMO-persona leftover
  that Friday's voice now speaks verbatim (`main.py:227`).

**Next steps.**
1. Set `AGENT_RUNTIME_URL` and live-verify the existing synchronous path for fast plans —
   then **re-architect to async**: `delegate_to_swarm` returns immediately with a spoken
   acknowledgment + a job row (SQLite, same pattern as `local_pending.py`); a background
   poller collects the result and hands it to the proactive channel (Domain 3).
2. Add a `CONFIRM_DOMAINS` set (lock, cover, alarm_control_panel, climate…) to the
   self-executing path: tool calls in those domains return a "confirm?" question instead of
   executing, honored by a yes within the follow-up window.
3. Add a minimal task ledger (`tasks.db`, fail-soft, same contract as `hass_synonyms.py`)
   with `add_task` / `list_tasks` / `complete_task` tools — the substrate reminders,
   swarm jobs, and multi-step errands all sit on.
4. Fix the Beemo string in `_self_execute_tools`.

---

## Domain 3 — Proactivity & initiative

**What a life assistant needs.** Speaking first: reminders and timers, a morning brief,
"your laundry is done / someone's at the door" event nudges, follow-ups on its own tasks
("that research you asked for is ready"), and enough judgment about *when and where* to
interrupt.

**What exists.** Almost nothing in-repo — Friday is purely reactive, and this is the single
largest structural gap. The inventory of "ways Friday can emit sound unprompted" is:
- The Pi FIFO (`/tmp/bmo_cmd.fifo`, `_command_fifo_thread` in `agents/bmo_voice/bmo_driver.py`)
  — `echo 'say:...' > fifo` speaks with face animation. A working *local* delivery
  mechanism with no producer in the repo.
- `voice_engine`'s `/speak` — and a comment there (`services/voice_engine/main.py:82`)
  reveals that "the morning brief" is a live consumer of it. **The morning brief exists only
  as an out-of-repo HA automation** — no trace of it in this codebase (verified by grep).
  Proactivity today is configuration living solely in HA's UI, invisible to and unmanaged by
  this repo.
- HA itself, which could run automations calling Assist/TTS — same story.

**The gap.** No scheduler, no reminder store, no event subscriptions, no notification
router, no in-repo definition of the one proactive behavior that already runs. Every other
ambitious capability in this map (async swarm results, reminders, memory-pipeline alerts,
calendar nudges) dead-ends into this missing channel.

**Next steps (this is the keystone build).**
1. **A `friday_dispatch` capability inside `bmo_brain`** (or a small sibling service): a
   queue of outbound utterances with target surface + priority, delivered via (a) the Pi
   FIFO / a new driver HTTP endpoint, (b) HA `notify.*` (companion app → phone push — this
   is nearly free and reaches the user *away from home*), and (c) HA TTS on the Wyoming
   Friday voice for in-home announcements.
2. **A scheduler** on top of the task ledger (Domain 2): time-based (reminders, morning
   brief as code) first; HA-webhook-triggered events second.
3. Wire `set_reminder(text, when)` into `TOOL_SCHEMAS` — the highest-frequency life-assistant
   verb there is, and it's currently impossible.
4. Interruption etiquette can start dumb (quiet hours env var) — don't gold-plate it before
   the channel exists.

---

## Domain 4 — Conversation quality

**What a life assistant needs.** Natural turn-taking with barge-in, real multi-turn context,
graceful handling of fragments and follow-ups, and a whole-loop latency that feels like
conversation (≤ ~2s to first audio is the felt threshold).

**What exists.**
- A carefully tuned follow-up mode on the Pi (`FOLLOWUP_WINDOW` 8s, `SILENCE_GATE_FRAMES`
  TV-noise rejection, `_is_speech_frame` RMS+ZCR gating in `bmo_driver.py`) — the user can
  continue without re-waking, when Friday's reply "sounds like a question"
  (`handle_voice_interaction`'s return heuristic: `"?" in reply or ...`).
- Layered STT-hallucination defense at both ends (`clean_stt_text` driver-side;
  `_is_likely_stt_hallucination` brain-side, deliberately without the length cutoff so the
  follow-up window's bare "no"/"ok" still works; `--vad-filter` hard gate in
  `wyoming_whisper_gpu/start.sh`).
- Real latency engineering already banked: CUDA-graph TTS (RTF 1.6 → 0.4), cached voice-clone
  prompt (skips per-call reference encoding), `keep_alive: "30m"` (avoids 8–11s model
  reloads), GPU whisper replacing the 3.2–6.2s CPU add-on, `fast` warmups at startup.

**The gap.**
- **The Pi surface is conversationally stateless.** `bmo_driver.chat()` sends
  `messages=[{"role": "user", "content": text}]` — a single message, every time. The brain
  never sees the prior turn. The follow-up window *feels* like conversation, but "what about
  tomorrow?" after a weather answer reaches `_answer()` with no antecedent — any coherence
  comes accidentally from `local_pending` keyword recall of the just-stored exchange. HA's
  surface doesn't have this problem (HA sends history), which makes the Pi the worst
  conversational surface while being the flagship one.
- **No barge-in** (roadmap-flagged): playback is a blocking `aplay` subprocess
  (`play_audio`); the wake-word `InputStream` is closed during interactions. Friday cannot
  be interrupted mid-monologue.
- **No streaming anywhere on the voice path.** `_answer()` returns complete text; `/speak`
  synthesizes one complete WAV; the driver plays it whole. `bmo_brain`'s "streaming"
  endpoints emit the full answer as a single chunk. Time-to-first-audio = LLM total + TTS
  total + transfer — observed 10–20s TTS alone for short replies on real hardware
  (`wyoming_friday_tts/server.py` comment).

**Next steps.**
1. **Rolling transcript on the Pi path** — cheapest big win in this whole document. Either
   driver-side (keep the last N exchanges in `BMODriver`, send as `messages`) or brain-side
   (a session keyed by `BMO_SOURCE_DEVICE`, since `_answer()` already receives full message
   lists from HA and handles them correctly).
2. **Sentence-streaming TTS**: split the reply on sentence boundaries, synthesize+play
   pipelined (the `_tts_lock` already serializes inference; a queue of sentence WAVs gets
   most of the perceived-latency win without touching the model).
3. Barge-in after streaming: swap `aplay` for interruptible playback and keep a VAD stream
   open during playback with echo suppression — genuinely hard on this hardware; sequence it
   last.

---

## Domain 5 — Integrations

**What a life assistant needs.** Calendar, email, messaging, notes/lists, media, phone —
the actual substrate of a life. This is where "assistant" stops being a metaphor.

**What exists.**
- **The home, deeply**: two full HA paths (Domain 2), the resolver/synonym stack, and — via
  the passthrough — everything HA exposes. `_DEVICE_CLASS_IS_ALSO_A_DOMAIN` already includes
  `media_player`, `lock`, `climate`, `vacuum`, `cover`.
- Weather (Open-Meteo, `HOME_LAT`/`HOME_LON`), news (BBC RSS, 5 topics), web search
  (DuckDuckGo HTML scrape). That is the complete list of non-home integrations.

**The gap.** No calendar, no email, no messaging, no notes/todo lists, no music service
beyond raw `media_player` entities, no phone presence. The strategic observation: **HA is
already the integration broker** — it has native calendar entities, shopping list,
`notify.mobile_app_*` (companion-app push), person/presence tracking, and timers. Friday's
brain already holds an HA admin token. Most "integrations" are therefore *one tool function
each* against an API Friday can already reach, not new infrastructure.

**Next steps (in cost order).**
1. `get_calendar_events` — HA `GET /api/calendars/{entity}?start&end`. Unlocks "what's on
   today?", the morning brief content, and calendar-based nudges.
2. `send_phone_notification` — HA `notify.mobile_app_*` service call. Unlocks Domain 3's
   away-from-home delivery for free.
3. `add_to_shopping_list` / HA todo entities — the "add milk to the list" class of request.
4. Presence-awareness (HA `person.*` state) as *context*, not a tool: inject "user is
   home/away" the way `_live_status()` injects health.
5. Email/messaging: deliberately later — highest privacy/action-safety stakes, and better
   routed through swarm delegation (which has confirmation-shaped UX) than through the
   instant voice loop.

---

## Domain 6 — Multi-surface presence & continuity

**What a life assistant needs.** One identity and one memory across every surface, with
conversations that can migrate ("as I was saying in the car…"), and output routed to
wherever the user is.

**What exists.** The architecture's genuine strength: **one canonical brain** behind three
surfaces (Pi driver → `/v1/chat/completions`; HA Assist → `/api/chat` Ollama-native; staged
"Hey Google" via Nabu Casa relay — pure config, pending the user's walkthrough). Same
persona, same vault, same tool logic. The HA-satellite stack (`wyoming_friday_tts`,
`wyoming_whisper_gpu`, the ESPHome Google-Mini config, the `hey_friday.onnx` openWakeWord
model + training pipeline) extends the same brain to commodity hardware. `source_device` is
recorded on every queued memory (`BMO_SOURCE_DEVICE` → `PendingExtraction.source_device`) —
provenance is already captured.

**The gap.** Memory is shared but **conversation state is not**: each surface's history
lives (or doesn't — see Domain 4) in the caller. There is no session registry, so "continue
where we left off" across surfaces only works via the memory cache coincidence. And with no
dispatch layer (Domain 3), Friday can't *choose* a surface — output always goes where input
came from, even if the user has left the room.

**Next steps.** Brain-side short-term session store keyed by a stable conversation id
(solves Domain 4's Pi problem and cross-surface continuity in one structure); surface
registry in the dispatch layer (which surfaces are live, last-seen), fed by HA presence.

---

## Domain 7 — Personalization & identity

**What a life assistant needs.** Knowing *who is speaking*, per-person memory and
preferences, and per-person authorization (a guest shouldn't unlock doors or read the
owner's memories).

**What exists.** More plumbing than the roadmap suggests, with the last pipe unconnected:
- **CAM++ speaker verification end-to-end**: `/enroll_speaker` (incremental
  embedding-averaging profiles) and `/verify_speaker` (cosine vs. `SPEAKER_THRESHOLD` 0.65)
  in `services/voice_engine/main.py`; the Pi driver gates interactions on it when
  `BMO_SPEAKER_VERIFY=true` (default false), fail-open throughout.
- **Owner-scoping everywhere downstream**: MemPalace requires `owner_id` on writes and
  scopes search by it; `hass_synonyms` rows carry `owner_id`; the vault distinguishes
  storage identity from read-access identities (`MEMPALACE_VAULT_FOR`, per the roadmap).

**The gap.** `_verify_speaker` *logs* `matched_speaker` and returns a boolean — **the
identity is discarded**. `bmo_brain` has exactly one hardcoded `VAULT_OWNER`; every caller
is the same person as far as memory, synonyms, and (future) preferences are concerned. HA's
own user context is likewise ignored. Friday is single-user in practice despite a
multi-user-shaped store. There is also no preference model (units, verbosity, name,
wake-time) beyond whatever the extractor happens to store as `preference`-type memories.

**Next steps.** Thread `matched_speaker` from the driver into the chat request (a
`user` field or header), map speaker → owner_id in `bmo_brain`, default unknown speakers to
a low-privilege guest owner with no vault recall and no confirm-tier tools. That single
plumbing job converts existing components into real per-person identity. Note the
enrollment-security caveat in Domain 8 before leaning on it for authorization.

---

## Domain 8 — Privacy, security, trust

**What a life assistant needs.** Local-first by default, explicit knowledge of what leaves
the LAN, authorization boundaries that scale with capability, and protection of the memory
store — which is now the most sensitive dataset in the house.

**What exists.**
- **Strong local-first core**: LLM (local Ollama), STT, TTS, wake word, speaker
  verification, and the entire vault are on-LAN. Personal config is env-only
  (`execution_plane/.env`, gitignored) — nothing personal in the repo, by design.
- **A deliberate, documented dual trust model** for device control (HA exposure list vs.
  Pi full-token REST — roadmap Tier 2 records this as a choice, not an oversight).
- Vault write auditing (`MemoryAuditLog`) and MCP DNS-rebinding protection with a host
  allowlist (`_mcp_allowed_hosts` in mempalace).

**The gap.**
- **What leaves the LAN is undocumented and growing**: Open-Meteo (coarse home coordinates),
  BBC (nothing personal), **DuckDuckGo — which receives raw user utterance content** whenever
  `web_search` fires, and the staged Google relay, where *every spoken command on that
  surface transits Google + Nabu Casa*. None of this is wrong for the posture, but no doc
  states it, and the persona's "ALWAYS call web_search before saying you don't know"
  instruction makes off-LAN query leakage the *default*, not the exception.
- **Unauthenticated LAN services with real blast radius**: `bmo_brain:8000` (any LAN device
  can converse *and drive device control through Friday's HA admin token*),
  `voice_engine:8020/8100` — including **`/enroll_speaker`, so any LAN device can poison or
  create speaker profiles**, which matters the moment Domain 7 uses identity for
  authorization — and the Bush vault API (search/store/PATCH/DELETE, no auth). Acceptable
  for a single-occupant trusted LAN; not for "life assistant that guests talk to."
- The `HOME_ASSISTANT_TOKEN` (long-lived admin) is injected into three separate containers
  (`bmo-brain`, `agent-runtime`, one more — compose lines 197/295/917).
- Everything identity-adjacent **fails open** (speaker verify on error, on missing model, on
  missing profiles). Right call for availability today; must invert for any confirm-tier
  action.

**Next steps.** Write the "what leaves the LAN" table into the roadmap; scope an HA token
per consumer (HA supports fine-grained long-lived tokens per user); add a shared-secret
header check on `bmo_brain` and `voice_engine` mutation endpoints (cheap, compose-level);
make speaker-verify fail-*closed* specifically for confirm-tier tool calls once Domain 7
lands.

---

## Domain 9 — Reliability & observability

**What a life assistant needs.** Graceful degradation (a memory hiccup must never kill a
voice command), visibility into a multi-hop pipeline, tests on the translation layers that
break silently, and alerting on the invisible background jobs.

**What exists.**
- **Fail-soft is a genuine house style**: `local_pending.py` and `hass_synonyms.py` document
  and honor a never-raise contract; `hass_resolver` degrades stage-by-stage and serves stale
  cache on registry failure; `_vault_recall`/`_pending_recall`/`_store_memory` all swallow
  and log; `wyoming_friday_tts` emits an empty AudioStart/Stop on synth failure so Assist
  completes instead of hanging (the 2026-07-11 fix); the whisper container warms CUDA before
  accepting traffic; `voice_engine` reports 503-while-loading.
- Health endpoints on every hop (`/health` on brain, engine, vault) and `_live_status()`
  turning them into spoken answers.
- An infra-maintenance stack (`services/maintenance_router`, Alertmanager → agent-safe
  auto-repair or human queue) that the voice stack is *not yet plugged into*.

**The gap** (both roadmap-flagged, both still true — verified):
- **Zero automated tests** for `bmo_brain`'s two API surfaces, the sanitize/resolve/learn
  logic (which encodes a dozen hard-won live-confirmed HA behaviors), or `voice_engine`.
  `scripts/bmo_sandbox.py` is manual. The tool-calling contract with HA's Ollama integration
  is exactly the kind of thing a dependency upgrade breaks silently.
- **No tracing on the voice path** — grep confirms zero Langfuse in `services/`. A slow
  answer today is diagnosed by reading four containers' prints. The prints are unusually
  good (`_answer()`'s per-exchange summary line, the driver's `⏱` timings) but they're not
  correlated per-interaction.
- The memory-promotion cron is un-owned and un-alerted (Domain 1).

**Next steps.** Pytest the pure logic first — `_sanitize_hass_tool_calls`,
`_extract_tool_attempts`, `_tool_result_is_error`, `_coerce_tool_call_args`,
`hass_resolver._normalize`/staging, `_is_likely_stt_hallucination` are all pure functions
with documented live-derived cases sitting in their docstrings *already written as test
specs*. Then a mocked-Ollama contract test per endpoint (the roadmap says one existed for
the 2026-07-02 passthrough work — resurrect it into CI). Then a per-interaction trace id
minted at wake/request time and passed through STT → brain → TTS, into Langfuse (Hopper's
instance already runs).

---

## Domain 10 — Latency & performance budget

**What a life assistant needs.** A stated end-to-end budget (wake → first audio ≤ ~2s feels
conversational; ≤ 5s is tolerable; 15s+ reads as broken) and per-stage measurement against it.

**What exists.** Substantial banked wins, all real: GPU whisper (replacing measured 3.2–6.2s
CPU transcription), CUDA-graph TTS RTF ~0.4 + cached clone prompt + startup warmups,
`keep_alive` 30m (vs. observed 8–11s reloads), `NUM_CTX` 16384 pinned (silent-truncation
guard), concurrent recall (halving worst-case vault latency), `fast_classify`-style
threshold breakers on the HA loop (2 rounds/~16s, down from 3/24s, on the live phone test),
and hallucination gates that prevent whole wasted round-trips. Timing prints exist at most
stages (driver `⏱ Brain/TTS/Total`, brain summary line).

**The gap.** No whole-loop number exists anywhere — the roadmap's own next step ("full
round-trip not yet retested") is still open. Known stage costs suggest the *floor* today is
roughly: VAD end-of-speech ~1.6s (20 × 80ms silence frames) + STT ~0.5–1s warm GPU + recall
≤3s worst + LLM 2–6s (qwen3:8b, 16k ctx) + TTS 4–20s + playback start ≈ **8–30s to first
audio** — the sequential TTS being the dominant term (Domain 4). One residual redundant HA
tool round (~8s) remains on device commands. All GPU consumers (chat model, embeddings,
Qwen3-TTS, faster-whisper, CAM++) share Lovelace's cards with no arbitration beyond
`keep_alive` and luck; a swarm build job (Domain 2, wired) would contend directly with the
voice loop — `gpu_queue.py` exists on the swarm side but the voice path doesn't participate.

**Next steps.** Measure first (the trace id from Domain 9 gives per-stage numbers for
free); adopt a stated budget; sentence-streaming TTS (Domain 4) as the one change that
plausibly cuts felt latency by half or more; then evaluate routing the brain's `qwen3:8b`
to Turing's fast path (roadmap pending-task list already flags the 14b-doesn't-fit and
warm-latency questions there).

---

## Prioritized build map

**Foundational (everything else lands on these):**
- **F1. Proactive dispatch channel + scheduler** (Domain 3). The keystone. Reminders, the
  morning brief as code, async swarm results, calendar nudges, and pipeline alerts all
  dead-end without it. Delivery mechanisms already exist on both ends (Pi FIFO, HA notify,
  Wyoming TTS) — only the middle is missing.
- **F2. Task/reminder ledger** (Domain 2) — the SQLite substrate F1 schedules from, in the
  house fail-soft style. Small.
- **F3. Session store for conversational state** (Domains 4/6) — fixes the stateless Pi
  turn and gives cross-surface continuity one home.

**Unlocks the most:**
- **U1. Async swarm delegation** (F1+F2 dependent): set `AGENT_RUNTIME_URL`, convert
  `delegate_to_swarm` to acknowledge-now/deliver-later. This is the moment Friday stops
  being a Q&A box and starts *doing things that take time* — the defining life-assistant
  behavior, and it reuses the entire existing swarm.
- **U2. Speaker identity → owner plumbing** (Domain 7): one data-flow change converts
  already-built CAM++ + owner-scoped storage into real per-person memory and the
  precondition for per-person authorization.

**Cheap but high-value:**
- **C1. HA calendar read + phone-notify tools** (Domain 5): two tool functions against an
  API Friday already authenticates to; combined with F1 they make the morning brief and
  "remind me" real.
- **C2. Memory pipeline hardening** (Domain 1): in-repo cron + queue-age alert + dedupe
  pass; plus `remember_fact`/`forget_about` tools.
- **C3. Pure-function test suite** (Domain 9): the specs are already written in docstrings.
- **C4.** The `Beemo` string fix and a "what leaves the LAN" doc section (minutes each).

**Big structural, sequenced later:** sentence-streaming TTS → barge-in (Domain 4/10);
fail-closed identity for confirm-tier actions (Domains 7/8); email/messaging via
swarm-mediated confirmation flows (Domain 5).

### The five highest-leverage next builds

1. **Proactive dispatch + scheduler + reminder tool** (F1+F2+ the `set_reminder` verb) —
   converts Friday from reactive to initiating; every other ambition queues behind it; both
   delivery endpoints already exist.
2. **Async `delegate_to_swarm`** (U1) — the entire Agent_Swarm platform is currently
   invisible to Friday's users; one env var + a job table + F1 delivery makes the whole
   swarm Friday's hands.
3. **Pi-path conversation history** (F3, minimal version) — probably the largest
   conversational-quality gain per line of code in the system; today's follow-up window is
   theater without it.
4. **Calendar + phone notification via HA** (C1) — the two integrations that make the
   morning brief, day-awareness, and away-from-home reach real, each ~a single tool
   function.
5. **Memory judgment: dedupe-on-promotion + in-repo cron + user memory verbs** (C2) — the
   vault is the long-term moat; at 7k+ memories and 100% ingestion with zero consolidation,
   recall quality will decay exactly when it matters most.

Rationale for the ordering: 1 and 2 create the *category change* (initiative + delegation);
3 and 4 are days-not-weeks and multiply the perceived intelligence of every existing
exchange; 5 protects the asset that makes Friday personal rather than generic. Streaming/
barge-in latency work is deliberately *not* in the top five despite being the most-felt
polish item — it's the most engineering-intensive item on the board, is purely subtractive
(removes annoyance rather than adding capability), and its groundwork (per-stage tracing)
ships with C3/Domain 9 anyway.
