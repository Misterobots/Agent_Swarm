# Phase 2–4 Training Pipeline Upgrade — Implementation Report

> **Date:** 2026-05-04  
> **Preceding phase:** Phase 1 (qwen3.6:27b model upgrade, commit 549ab9e)  
> **Commit:** 4771ed5 — `feat(training): Phase 2-4 training pipeline upgrade`

---

## Summary

This document records the implementation of Phases 2, 3, and 4 of the Agent Swarm training pipeline upgrade.

---

## Phase 2 — Training Job Dispatcher (`agents/training/dispatcher.py`)

### Purpose
FastAPI service running on Lovelace (`http://192.168.2.101:8001`). Accepts training job requests from Turing's `agent_runtime`, runs preflight checks, and launches `grpo_trainer.py` as a local subprocess using Lovelace's dual RTX 5060 Ti (32 GB VRAM).

### Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Liveness probe — returns status, active jobs, available archetypes |
| POST | `/train` | `X-Dispatcher-Key` | Submit a training job |
| GET | `/train/{job_id}` | `X-Dispatcher-Key` | Poll job status + exit code |
| GET | `/jobs` | `X-Dispatcher-Key` | List recent jobs (newest-first, max 50) |
| DELETE | `/train/{job_id}` | `X-Dispatcher-Key` | Terminate a running job |

### Authentication
Shared secret: `DISPATCHER_SECRET` env var.  
Header: `X-Dispatcher-Key: <secret>`  
If `DISPATCHER_SECRET` is unset, all requests return `503` (fail-safe).

### Job Lifecycle
```
POST /train → validate archetype → preflight check → reject if job already running
            → launch subprocess → return {job_id, status: "running"}
GET /train/{job_id} → poll subprocess → update status → return current state
```

### Request Body (`POST /train`)
```json
{
  "archetype": "coder",          // required — must be in ARCHETYPE_TRAINING_CONFIGS
  "dataset_path": "/workspace/training_data/curated.jsonl",  // optional
  "base_model": "Qwen/Qwen3.6-27B",  // optional
  "max_seq_len": 2048,           // optional override
  "force": false,                // bypass training time window
  "dry_run": false               // preflight only, no training
}
```

### Docker Compose Integration
Added to `execution_plane/docker-compose.yml` as `training-dispatcher` service:
- Image: `home-ai-lab/agent-runtime:latest` (same Dockerfile as agent-runtime)
- Port: `8001:8001`
- GPU passthrough (`count: all`)
- Environment: `DISPATCHER_SECRET`, `TRAINING_*` vars, `HF_TOKEN`
- Also removed stray `8001:8001` mapping from `agent-ui` (was a leftover conflict)

### Validation
```
✅ Syntax check: OK
✅ ARCHETYPE_TRAINING_CONFIGS import: OK  
✅ Docker service definition: no port conflicts
```

---

## Phase 3 — Dataset Curator Improvements (`agents/training/dataset_curator.py`)

### New Datasets Added to `CURATED_DATASETS`
| Key | HF ID | Samples | Category |
|-----|-------|---------|----------|
| `code-feedback` | `m-a-p/CodeFeedback-Filtered-Instruction` | 10,000 (default) | code |
| `the-stack-v2` | `bigcode/the-stack-v2-train-smol-ids` | 5,000 (default) | code |

Both added to `"code_developer"` recommended archetypes.  
`the-stack-v2` uses new `"format": "code"` which triggers the `_code_to_grpo()` converter (wraps raw code files in a single instruction → completion turn).

### Source Whitelist (`config/source_whitelist.json`)
New JSON file listing approved HuggingFace organisation slugs.  
Only datasets whose owner org appears in `approved_orgs` pass the whitelist check.

**Approved orgs (initial list):**
`glaiveai`, `NousResearch`, `teknium`, `Open-Orca`, `m-a-p`, `bigcode`,  
`mistralai`, `Qwen`, `meta-llama`, `EleutherAI`, `allenai`, `HuggingFaceH4`,  
`HuggingFaceFW`, `openai`, `databricks`, `WizardLMTeam`, `TIGER-Lab`, `cognitivecomputations`

Behaviour if whitelist file is missing: warning logged, check disabled (fail-open for local dev).

### llama-guard Pre-scan
Before the existing injection scanner runs, each sample's first 20 whitespace-separated tokens are sent to Turing's `llama-guard-3:8b` (`http://192.168.2.103:8008/v1/chat/completions`).  
- If the guard replies with anything other than `"safe ..."`, the sample is written to the `_rejected.jsonl` file and counted as `guard_blocked`.
- If Turing is unreachable (network error, timeout), the scan **passes** (fail-open) with a debug log — prevents curation from blocking on a down node.
- Configurable via env: `TURING_OLLAMA_HOST`, `GUARD_MODEL`

### Validation
```
✅ CURATED_DATASETS keys: ['glaive-function-calling', 'hermes-function-calling', 
   'openhermes', 'glaive-code-assistant', 'slim-orca', 'code-feedback', 'the-stack-v2']
✅ Source whitelist loaded: 18 approved orgs
✅ m-a-p whitelisted: True
✅ bigcode whitelisted: True  
✅ random-org blocked: True (correctly rejected)
✅ DatasetCurator instantiates correctly
```

---

## Phase 3 — Trace Exporter Improvements (`agents/training/export_traces.py`)

### Threshold: 0.85 (was 0.8)
- New constant: `EXPORT_MIN_SCORE = float(os.getenv("EXPORT_MIN_SCORE", "0.85"))`
- Both `fetch_training_candidates()` and `export_dataset()` default to this value
- Override at runtime: `EXPORT_MIN_SCORE=0.90 python -m training.export_traces`
- The `compute_reward(final_score=...)` floor was also updated to use `EXPORT_MIN_SCORE`

### Content-Based Deduplication
Within a single `export_dataset()` run:
- Tracks a set of `output_fingerprints` (first 100 chars of the last assistant turn)
- Skips any trace whose fingerprint was already seen in this run
- ID-based dedup (across all historical runs via `exported_ids.json`) is preserved

### Topic Diversity Balancing
- Topics: `code`, `math`, `tool_use`, `creative`, `general`
- Per-topic cap = `total_limit // num_topics` (only active when `total_limit` is set)
- Classification uses simple keyword matching — no extra LLM call needed
- Distribution logged at export completion: e.g. `Topic distribution: {'code': 45, 'math': 12, ...}`

### Validation
```
✅ EXPORT_MIN_SCORE: 0.85 (default)
✅ Topic classification: code test → 'code', general test → 'general'
✅ Topic keywords: ['code', 'math', 'tool_use', 'creative', 'general']
```

---

## Phase 4 — Archetype Training Configs (`agents/config.py`)

### Added `ARCHETYPE_TRAINING_CONFIGS`
```python
ARCHETYPE_TRAINING_CONFIGS: dict = {
    "coder":       {"datasets": ["glaive-code-assistant", "code-feedback"],          "epochs": 3, "base_model": TRAINING_BASE_SOLVER},
    "coordinator": {"datasets": ["hermes-function-calling", "slim-orca"],            "epochs": 2, "base_model": TRAINING_BASE_SOLVER},
    "researcher":  {"datasets": ["openhermes", "slim-orca"],                         "epochs": 2, "base_model": TRAINING_BASE_SOLVER},
    "creative":    {"datasets": ["openhermes"],                                      "epochs": 2, "base_model": TRAINING_BASE_SOLVER},
}
```

### Integration Points
- `dispatcher.py`: validates submitted `archetype` against this dict (returns `422` for unknown archetypes)
- `/health` endpoint: exposes `available_archetypes` list
- Future: `grpo_trainer.py` can pull per-archetype dataset list + epoch count from this config

### Validation
```
✅ Import test: from config import ARCHETYPE_TRAINING_CONFIGS
✅ Keys: ['coder', 'coordinator', 'researcher', 'creative']
```

---

## Files Changed

| File | Change |
|------|--------|
| `agents/training/dispatcher.py` | **NEW** — FastAPI training job dispatcher |
| `agents/training/dataset_curator.py` | 2 new datasets, source whitelist, llama-guard pre-scan, `_code_to_grpo()` converter |
| `agents/training/export_traces.py` | Threshold 0.85, content dedup, topic diversity |
| `agents/config.py` | Added `ARCHETYPE_TRAINING_CONFIGS` |
| `config/source_whitelist.json` | **NEW** — 18 approved HF org slugs |
| `execution_plane/docker-compose.yml` | Added `training-dispatcher` service, removed stray port 8001 from agent-ui |

---

## Known Limitations & Next Steps

- Dispatcher job state is in-memory only — restart clears job history. A future phase should persist to Redis or SQLite.
- llama-guard pre-scan is fire-and-forget (fail-open on network errors). Consider adding a strict mode flag.
- `the-stack-v2` `_code_to_grpo()` converter produces low-quality single-turn samples; a future improvement could use surrounding context for multi-turn instruction building.
- `DISPATCHER_SECRET` must be added to `execution_plane/.env` and `network.env` on both Lovelace and Turing before the dispatcher is useful in production.

---

## Activation (2026-05-04)

Post-commit activation steps completed on the same day:

### Secrets added
| File | Variable | Value |
|------|----------|-------|
| `execution_plane/.env` | `DISPATCHER_SECRET` | 64-char hex (generated via `secrets.token_hex(32)`) |
| `network.env` | `DISPATCHER_SECRET` | Same value (shared secret) |
| `network.env` | `DISPATCHER_URL` | `http://192.168.2.101:8001` |

### Containers started
```
docker compose -f execution_plane/docker-compose.yml up -d training-dispatcher
# → training_dispatcher Started

# Turing: agent_runtime force-recreated to pick up DISPATCHER_SECRET + DISPATCHER_URL
ssh misterobots@192.168.2.103 'cd Home_AI_Lab/turing_gateway && docker compose up -d --force-recreate agent-runtime'
# → agent_runtime Recreated, Started
```

### Health check
```json
GET http://192.168.2.101:8001/health
{
  "status": "online",
  "node": "lovelace",
  "ip": "192.168.2.101",
  "active_jobs": 0,
  "total_jobs": 0,
  "available_archetypes": ["coder", "coordinator", "researcher", "creative"]
}
```

The training pipeline is **fully active** as of 2026-05-04T07:00 CDT.
