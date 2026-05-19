# Phase 0: VISION Intent Fix — Completion Report

**Date:** 2025-06-10  
**Git Tag:** `phase-0-complete`  
**Commit:** `96a2e36`  

---

## Objective

Fix the misroute where "What do you see in this image?" was classified as IMAGE (art generation) instead of VISION (image analysis). Add a complete VLM (Vision Language Model) pipeline using moondream via Ollama.

## Root Cause

Two-layer classification failure:

1. **Dispatcher** (`detect_intent()`): Keyword matcher hit `"image"` in the input string → returned `IMAGE` intent before any semantic analysis
2. **Router** (`chat_swarm()` SSE path): No VISION handler existed; `CREATIVE_INTENTS = {"IMAGE", "3D", "ACTION_FIGURE"}` would redirect to Art Studio

## Changes Made

### 1. `agents/semantic_router.py`
- Added **VISION** as category 13 with keywords: "what do you see", "describe this image", "analyze this image", "what is in this picture", "read this screenshot", "OCR", "identify", "what's happening in this photo", "look at this"
- Description explicitly distinguishes VISION (analyze existing) from IMAGE (generate new)

### 2. `agents/intent_capabilities.py`
- Added VISION capability mapping:
  - Agent: Vision Analyst
  - Template: `vision_analyst`
  - Capabilities: `image_read`, `model_generate`, `file_read`
  - Security: `L1_PUBLIC`

### 3. `agents/router.py` (4 changes)
- Added `import requests` at module level
- **SSE path:** VISION handler before `CREATIVE_INTENTS` block — extracts base64 image from `extracted_context`, calls moondream:latest via Ollama `/api/generate`, streams analysis back. Graceful fallback when no image attached.
- **Async path:** VISION handler in `handle_task_event()` — routes to moondream if `image_data` in payload, falls back to Orchestrator otherwise
- Added `"VISION"` to fallthrough exclusion list

### 4. `agents/dispatcher.py`
- Added `vision_phrases` list checked BEFORE `"image" in text` keyword match
- Prevents false IMAGE classification for vision-related queries

### 5. Infrastructure
- Pulled `moondream:latest` (~1.7GB) on Lovelace Ollama (GPU 0)

## Test Results

### Intent Classification
| Input | Before | After |
|---|---|---|
| "What do you see in this image?" | IMAGE | VISION ✅ |
| "Hello, are you working?" | CONVERSATION | CONVERSATION ✅ |

### UI Regression (Hive UI — Turing port 3200)
| Route | Status |
|---|---|
| /chat | 200 ✅ |
| /art-studio | 200 ✅ |
| /control | 200 ✅ |
| /dev | 200 ✅ |
| /governance | 200 ✅ |
| /media | 200 ✅ |
| /monitor | 200 ✅ |
| /settings | 200 ✅ |
| /tools | 200 ✅ |
| /training | 200 ✅ |

### SSE Chat Flow
- Security: PASS (Llama-Guard)
- Intent classification: Working (CONVERSATION at 95% confidence)
- Response streaming: Working ("Yes, I am working. How can I assist you today?")
- Turn management: Working

## Snapshot/Restore Point

- **Git tag:** `phase-0-complete`
- **Compose backups:** `migration_backup_20260314_163149/phase-0/`
  - `execution_plane_docker-compose.yml`
  - `turing_gateway_docker-compose.yml`
  - `control_plane_docker-compose.yml`
- **Rollback:** `git checkout phase-0-complete` or `git revert HEAD`

## Known Issues (Pre-existing, Not Introduced)

- SPIRE SVID fetch errors (intermittent, pre-existing)
- Langfuse OTLP export 401 Unauthorized (pre-existing)
- TemplateRegistry FK constraint for `default` template_id (pre-existing)
- ComfyUI checkpoint `v1-5-pruned-emaonly.ckpt` not found (no checkpoints installed)
- Turing Ollama `OLLAMA_GPU_OVERHEAD=512MiB` parsing bug (pre-existing)

## Next Phase

**Phase 1: Coordinator Mode** — Hybrid Python orchestration + LLM synthesis for multi-worker task coordination.

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `agents/semantic_router.py` | Implementation | VISION intent classification fix |
| `agents/intent_capabilities.py` | Implementation | Intent-to-capability mapping for VLM |
| `agents/router.py` | Implementation | VLM pipeline routing |
| `agents/dispatcher.py` | Implementation | Task dispatching with vision support |
| Git tag `phase-0-complete` | VCS | Phase 0 baseline snapshot |
| Commit `96a2e36` | VCS | Phase 0 merge commit |

</details>

---

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-02-01 | AI-Copilot | Initial Phase 0 report — VLM pipeline and VISION fix |

</details>

---

## Maintenance & Update Guide

This is a **historical phase report**. Update only if:

- A rollback to this phase is executed (document the reason and outcome).
- Post-phase bugs are discovered that trace back to changes made here.

---

## Verification

| Claim | How to Verify |
|-------|---------------|
| VISION intent routes to VLM | Send an image-analysis prompt → confirm moondream model is invoked |
| moondream model available | `curl http://<ollama-host>:11434/api/tags` → confirm `moondream:latest` listed |
| Git tag exists | `git tag -l phase-0-complete` |
