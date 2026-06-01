---
title: Changelog
---

# Changelog

All notable changes to Memex are documented here.

## [1.2.0] — 2026-06-01

### Added

**Design Studio — `immersive-ui` skill**

- New skill for full-screen tablet and kiosk interfaces, triggered by keywords: `tablet`, `kiosk`, `holographic`, `immersive`, `sci-fi ui`, `cinematic ui`, `full screen`
- System prompt instructs the model to produce a full-bleed 1280×800 landscape interface with dark atmospheric backgrounds, continuous animation, and no external CDN links
- Includes guidance on CSS `-webkit-text-stroke` for hollow outlined letterforms and header/flex layout padding patterns

**Design Studio — assistant prefill**

- Ollama `/api/chat` call now injects `<!DOCTYPE html>\n<html lang="en">` as the start of the assistant turn
- Forces the model to begin generating HTML immediately — eliminates preamble/explanation that previously caused `parse_artifact_html` to return `None`
- Replaces the `phi.agent.Agent` wrapper which could not expose the messages array for prefill injection

**Design Studio — skill detection improvements**

- `detect_skill_from_prompt()` now uses whole-word regex matching (`\b` boundaries) — fixes false positives where substring keywords matched inside unrelated words (e.g. `graph` inside `typography` → wrongly triggered `dashboard` skill)
- Removed ambiguous `landing page` keyword from `saas-landing` triggers — screen names like "Main Landing Page" no longer misroute design requests
- Added context-doc fallback: if the user message alone matches only the `web-prototype` fallback, Design Studio scans the first 2 KB of any attached context document for skill keywords

**Attachment pipeline**

- `church.py` now routes file attachments to `extracted_context` — previously the `attachments` parameter was declared in `route()` but never used, silently dropping all attached files
- `image/*` attachments promoted as base64 data-URIs; text/json/pdf attachments base64-decoded and appended as labelled text blocks
- Multiple attachments accumulate correctly (previously each image overwrote the previous)

**Design Studio — context injection**

- `handlers/design.py` now includes `extracted_context` in the final model prompt under `[Attached context / reference material]`
- Previously, attached documents and images were extracted by `church.py` but never forwarded to the designer model

**Vision handler — model fallback chain**

- `handlers/vision.py` now tries models in priority order: `minicpm-v` → `llava:13b` → `llava:7b` → `llava:latest` → `moondream:latest` → `gemma4:31b`
- If no vision model is installed, returns a clear install instruction rather than a cryptic error
- Fixed: was previously hardcoded to `moondream:latest` only, which is not installed

**`parse_artifact_html` resilience**

- Strips `<think>/<thinking>` blocks before extraction (UltraThink reasoning tokens no longer block HTML detection)
- Extracts from markdown code fences (` ```html...``` `)
- Finds `<!DOCTYPE html>` or `<html>` anywhere in the output, not only at the start
- All four extraction methods tried in sequence before returning `None`

**Dev workspace coordination**

- `ui/src/components/dev/AGENTS.md` — frontend coordination notes for parallel worktrees; conflict-zone rules, store slices, panel registry pattern, active task table (P0–M1)
- `ui/src/components/dev/tasks/` — implementation handoff files for design-debt tasks: D0 (orphan deletion), D1 (Monaco/xterm theme reactivity), D2 (token sweep), D3 (Pioneers reskin), Q6 (mobile placeholder)
- `agents/agents.md` — backend coordination notes for parallel workstreams on the dev workspace continuity initiative

### Fixed

**`_langfuse_span` double-yield generator bug** (`handlers/base.py`)

- When an exception propagated out of the `yield result` inside `_langfuse_span`, the outer `except Exception` block (designed only for setup failures) caught it and yielded `result` a second time
- Python's `@contextmanager` protocol forbids yielding after `.throw()` → `RuntimeError: generator didn't stop after throw()`
- Fix: separated setup (try/except before yield) from teardown (finally after yield); exactly one yield in every code path

**Design Studio — skill misclassification: `graph` in `typography`**

- `"graph" in "typography"` → `True` → any design prompt containing the word "typography" (e.g., a landscape tablet UI brief) was routed to the `dashboard` skill
- Fixed by `\bgraph\b` word-boundary regex — now only matches the standalone word

**Attachment accumulation overwrite**

- `church.py` attachment bridge used `extracted_context = f"data:{mime};..."` (assignment) instead of appending
- Each new image silently replaced the previous; text attachments after an image were dropped
- Fixed: all attachments now accumulate in order

## [1.1.0] — 2026-05-19

### Added

**Goals Mode** (`feature/goals`)

- Per-thread task tracking panel (`GoalsPanel`) — slides in from the right edge of the chat layout
- Ordered plan steps with `pending → in_progress → completed` status flow and manual Start / Done controls
- Evidence log for collecting `command_output`, `file_ref`, `test_result`, and `note` artifacts per goal
- Progress bar (completed steps / total steps) with live update
- Pause / Complete goal controls in the panel footer
- Goal persistence in PostgreSQL across page refreshes; one active goal per thread
- FastAPI routes: `POST /api/v1/goals`, `GET /api/v1/goals/{thread_id}/active`, step CRUD, evidence CRUD, complete, pause
- Zustand store (`goals-store.ts`) with REST sync; SSE-friendly incremental updates
- `GoalStepRow`, `GoalsPanel`, `GoalAuditPanel` React components

**Glassomorphic Sweep Animation System**

- `glass-sweep`, `glass-panel-enter`, `glass-row-enter` CSS keyframes added to `globals.css`
- `.glass-sweep-shimmer` — diagonal one-shot shimmer overlay, composable via `position:relative; overflow:hidden` container
- `.glass-surface` — frosted glass base (`backdrop-filter: blur(18px) saturate(1.4)`)
- `.glass-panel-enter`, `.glass-row-enter` — one-shot entry animations for panels and rows
- Staggered 40 ms per-row cascade on Goals panel open
- Sweep fires on `pending → in_progress` and `pending → completed` transitions in `GoalStepRow`
- Full-panel sweep fires each time `GoalsPanel` opens
- Pattern documented in [Developer Guide: Glass Animation System](../developer-guide/glass-animations.md)

### Fixed

**Research Mode: Perspective Research gate** (`agents/coordination/orchestrator.py`)

- Pioneer agent cards (Knuth, Weil, Keynes, etc.) no longer spawn for broad topics when the Research toggle is OFF
- `_decompose_task_perspectives()` LLM probe is now gated behind `research_mode=True`; previously it fired on any multi-faceted topic regardless of the toggle state
- Change: `if not _use_perspective_mode and not _is_creative_task:` → `if research_mode and not _use_perspective_mode and not _is_creative_task:`

---

## [Unreleased]

### Added

- Comprehensive MkDocs documentation site
- Docker-based documentation deployment
- GitHub Pages deployment via GitHub Actions

### Changed

- Documentation restructured as a full library of procedures, tutorials, and references

---

## [1.0.0]  Initial Release

### Features

- Multi-agent orchestration (Router ? Coordinator ? Solver)
- MarsRL verification loop (solve ? verify ? reward)
- Image generation via ComfyUI integration
- 3D model generation pipeline
- Voice interface (Whisper STT + Piper TTS)
- IoT control via Home Assistant
- Research Mode with web search
- Skills Memory (PostgreSQL + pgvector)
- SPIRE-based service identity and mTLS
- Langfuse observability and tracing
- jacquard + hollerith monitoring
- knuth log aggregation
- Traefik reverse proxy and load balancing
- GRPO preference training
- Governance system for sensitive operations
- Hive UI web interface
- GPU allocation and management
- 3-node distributed architecture

### Infrastructure

- Docker Compose deployment across 3 nodes
- Control Plane: SPIRE server, PostgreSQL, Langfuse
- Execution Plane: Ollama, Agent Runtime, ComfyUI, Voice
- Gateway: Traefik, jacquard, hollerith, knuth


