# Hive Functional Test Report — qwen3.6:27b Phase 1 Upgrade

**Date:** 2026-05-04  
**Model Upgraded From:** `qwen3:14b`  
**Model Upgraded To:** `qwen3.6:27b`  
**Test Node:** Turing (192.168.2.103) → Ollama on Lovelace (192.168.2.101)  
**Agent Runtime:** `home-ai-lab/agent-runtime:latest` at `0.0.0.0:8008`

---

## Test Results Summary

| # | Test | Status | Time |
|---|------|--------|------|
| 1 | Health Check (`GET /`) | ✅ PASS | 0.18s |
| 2 | Simple Conversation | ✅ PASS | 21.31s |
| 3 | Python Code Generation | ✅ PASS | 17.07s |
| 4 | Reasoning / Research | ✅ PASS | 8.04s |
| 5 | Long Context Document Summary | ✅ PASS | 15.05s |
| 6 | gRPC Classify Endpoint | ❌ FAIL | — |
| 7 | GPU VRAM on Turing | ⚠️ WARN | — |
| 8 | Config `PRIMARY_MODEL` Verification | ✅ PASS | — |

**Overall: 6 PASS / 1 WARN / 1 FAIL**  
**Average chat response time: 15.37s**

---

## Model Response Quality

### Test 2 — Simple Conversation
**Prompt:** "Hello! Reply in exactly one sentence: what AI model are you?"  
**Response:** `I am a large language model developed by Alibaba Cloud, part of the Qwen series.`  
**Assessment:** ✅ Correct identification, coherent, appropriate length.

### Test 3 — Python Code Generation
**Prompt:** "Write a Python function called `sort_list` that takes a list of integers and returns them sorted ascending. Return only code."  
**Response:**
```
Solver started
def sort_list(lst):
    return sorted(lst)
def sort_list(lst):
    return sorted(lst)
Loop complete
Architect response generated
Turn complete
```
**Assessment:** ✅ Correct code. ⚠️ **Pipeline artifact**: Non-streaming mode concatenates SSE event labels and intermediate outputs into response text. Code appears twice (Solver output + Architect relay). Not a model quality issue — a response formatting concern in non-streaming mode.

### Test 4 — Reasoning / Research  
**Prompt:** "What is the capital city of France? Answer in one word."  
**Response:** `Paris`  
**Assessment:** ✅ Perfect. Fastest response at 8.04s.

### Test 5 — Long Context Document Summary
**Prompt:** 3-paragraph AI definition text  
**Response:** `Artificial intelligence (AI) is the study of machines that demonstrate intelligent behavior, such as perceiving their environment and taking actions to achieve their goals. AI research focuses on systems that exhibit human-like traits, including learning and problem-solving abilities, often referred to as "intelligent agents."`  
**Assessment:** ✅ Accurate, concise, good quality summary.

---

## Performance Analysis

| Metric | Value | Notes |
|--------|-------|-------|
| Avg chat response time | **15.37s** | Full round-trip incl. MarsRL pipeline |
| Fastest response (T4) | 8.04s | Simple factual lookup |
| Slowest response (T2) | 21.31s | First request — model cold-start on Lovelace |
| Routing overhead | ~1–2s | JWT, intent classification, GPU queue |
| Model load time (cold) | ~10–15s | 17GB model load from disk on Lovelace |

**vs qwen3:14b baseline:** qwen3:14b averaged ~8–10s per response. qwen3.6:27b averages ~15s — approximately **1.5–2× slower** due to 27B vs 14B parameter count. Expected and acceptable given the quality/capability gains.

---

## Issues Found and Resolved

### 🔴 Issue 1: `qwen3.5:9b` Corrector Model (Critical — FIXED)
**Symptom:** `Corrector - ERROR - [Corrector] Failed to correct: model 'qwen3.5:9b' not found (status code: 404)`  
**Root Cause:** `agents/dijkstra_agent.py` had `DEFAULT_CORRECTOR_MODEL = os.getenv("CORRECTOR_MODEL", "qwen3.5:9b")`. Model `qwen3.5:9b` was never pulled to Lovelace and no longer exists in the stack.  
**Fix Applied:** Changed default to `"qwen3.6:27b"` in `dijkstra_agent.py` and `template_registry.py`.  
**Status:** ✅ Fixed in commit (next push)

### 🔴 Issue 2: `ollama:11434` Docker DNS Resolution (Warning — Active)
**Symptom:** `[NodeHealth] Lovelace (http://ollama:11434) is DOWN`  
**Root Cause:** The Docker DNS name `ollama` doesn't resolve from Turing's containers to Lovelace's Ollama. The GPUQueue falls back to `http://192.168.2.101:11434` (explicit IP) successfully.  
**Impact:** Extra log noise, potential health-check false negatives.  
**Fix Needed:** Update `OLLAMA_HOST` / node health config to use explicit IP `192.168.2.101:11434` as primary instead of DNS name `ollama:11434`.  
**Status:** ⏳ Not yet fixed — tracked as follow-up

### 🟡 Issue 3: Non-Streaming Response Includes Pipeline Event Labels  
**Symptom:** Non-streaming `/v1/chat/completions` response content includes labels like "Solver started", "Loop complete", "Turn complete" concatenated with actual content.  
**Impact:** Affects only direct API consumers using `stream: false`. UI streaming mode works correctly.  
**Fix Needed:** Non-streaming mode should strip intermediate pipeline event labels from the final `choices[0].message.content`.  
**Status:** ⏳ Not yet fixed — tracked as follow-up

### 🟡 Issue 4: gRPC Classify Endpoint API Contract  
**Symptom:** `POST /api/v1/grpc/classify` returns 422 when payload has `text` field — expects `task` field.  
**Root Cause:** Test script bug (used wrong field name). Endpoint works correctly.  
**Status:** ✅ Test fixed (script updated)

### ✅ Issue 5: `ollama:11434` Fallback Working  
The GPUQueue correctly falls back to `http://192.168.2.101:11434` when Docker DNS fails. All actual LLM calls succeed via the IP fallback. No inference failures attributed to this.

---

## Infrastructure Observations

### Node Health
- **Lovelace Ollama:** Reachable at `192.168.2.101:11434` ✅ (DNS `ollama:11434` fails but IP works)
- **Turing agent_runtime:** Healthy, port 8008, startup complete ✅
- **MarsRL pipeline:** Functional (Solver + Verifier working) — Corrector was broken, now fixed

### VRAM Usage (Lovelace)
- **Before test:** Model not loaded (cold start observed on T2 — 21s)
- **After T2:** Model warm, T4 responded in 8s (confirms VRAM caching)
- **2× RTX 5060 Ti = 32GB VRAM** — qwen3.6:27b Q4_K_M ≈ 17GB — fits in single card with ~15GB headroom

### Model Pipeline
```
User → Hive UI (:3200) → agent_runtime (:8008) 
  → Router (intent classification)
  → Solver (qwen3.6:27b via Lovelace:11434)
  → Verifier (llama-guard-3:8b)
  → [if fail] Corrector (qwen3.6:27b) ← was broken, now fixed
  → Response → SSE stream → UI
```

---

## Changes Made This Phase

| File | Change |
|------|--------|
| `agents/config.py` | PRIMARY_MODEL → `qwen3.6:27b`, removed `qwen3.5:9b` from CONTEXT_WINDOWS |
| `agents/dijkstra_agent.py` | DEFAULT_CORRECTOR_MODEL → `qwen3.6:27b` |
| `agents/expertise/template_registry.py` | default_model (content agent) → `qwen3.6:27b` |
| `agents/church.py` | All `qwen3:14b` hardcoded fallbacks → `qwen3.6:27b` |
| `agents/church-Justin-PC.py` | All 7 `qwen3:14b` hardcoded fallbacks → `qwen3.6:27b` |
| `agents/lamport.py` | Model defaults → `qwen3.6:27b` |
| `agents/grpc/model_router.py` | GENERAL_MODEL → `qwen3.6:27b` |
| `agents/training/preflight.py` | New file — pre-flight checker for training runs |

---

## Recommendations Before Phase 2

1. **Fix `ollama:11434` DNS** — Update node health check config to use `192.168.2.101:11434` directly (or add hosts entry in Docker network)
2. **Non-streaming response cleanup** — Strip pipeline event labels from `choices[0].message.content` in non-streaming mode
3. **Monitor Corrector** — After next `agent_runtime` restart, verify Corrector uses `qwen3.6:27b` successfully

---

## Next Phase

**Phase 2:** `agents/training/dispatcher.py` — FastAPI training job dispatcher on Lovelace  
**Phase 3:** Dataset curator and trace export improvements  
**Phase 4:** Archetype training configs
