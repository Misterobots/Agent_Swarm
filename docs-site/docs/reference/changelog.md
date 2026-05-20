---
title: Changelog
---

# Changelog

All notable changes to Memex are documented here.

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


