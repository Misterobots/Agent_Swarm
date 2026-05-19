# Phase 6 Testing Plan: GRPO Training Pipeline

**Date**: 2026-03-21
**Scope**: Training Data Pipeline, QLoRA Fine-Tuning, A/B Testing, Monitoring Dashboards
**Status**: Ready for Execution

---

## 1. Unit Tests

### 1.1 Training Data Export (`agents/training/export_traces.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U1 | Export with valid Langfuse traces | 5+ traces tagged `training_candidate` | Valid JSONL with conversations, reward, metadata |
| U2 | Export with no matching traces | Empty Langfuse result | Empty file, no error |
| U3 | Reward calculation | Trace with verifier_score=0.9, iterations=2, guard_pass=True | `{"correctness": 0.9, "efficiency": 0.5, "safety": 1.0}` |
| U4 | Malformed trace handling | Trace missing observations | Skip with warning, don't crash |

### 1.2 Synthetic Generation (`agents/training/synthetic_gen.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U5 | Generate single trajectory | `target_count=1, domain="code"` | 1 valid JSONL record with tool_calls |
| U6 | Generate multi-domain batch | `target_count=10` | 10 records spanning code, file, iot, research |
| U7 | Tool definition loading | Default tool registry | All 4 tool families present (file_ops, terminal, model_route, iot_control) |
| U8 | Trajectory validation | Generated trajectory | Schema-valid: has id, conversations, reward, metadata |

### 1.3 Reward Function (`agents/training/reward_function.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U9 | Perfect score | correctness=1.0, efficiency=1.0, safety=1.0 | composite = 1.0 |
| U10 | Weighted composite | correctness=0.8, efficiency=0.6, safety=1.0 | composite = 0.8×0.5 + 0.6×0.3 + 1.0×0.2 = 0.78 |
| U11 | Safety failure | safety=0.0 (guard flagged) | composite penalized heavily |
| U12 | Edge: all zeros | correctness=0, efficiency=0, safety=0 | composite = 0.0, no crash |

### 1.4 GRPO Trainer (`agents/training/grpo_trainer.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U13 | Config validation | Default GRPOTrainingConfig | All fields populated, batch_size=1, lora_rank=16 |
| U14 | Training run DB record | Mock training start | Row in `swarm.training_runs` with status='running' |
| U15 | Training completion | Mock training end | Row updated: status='completed', metrics populated |
| U16 | Training failure | Simulated OOM | Row updated: status='failed', error_message set |

### 1.5 GGUF Conversion (`agents/training/convert_gguf.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U17 | LoRA merge config | adapter_path, base_model | merge_and_unload() called with correct args |
| U18 | Modelfile generation | model name + GGUF path | Valid Modelfile with FROM and PARAMETER lines |
| U19 | Ollama import | Mock /api/create | 200 OK, model_versions row created |
| U20 | Cleanup after merge | Successful GGUF extraction | Merged model dir deleted, GGUF preserved |

### 1.6 A/B Testing (`agents/training/ab_test.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U21 | Start A/B test | template_id, candidate, base, split=0.2 | Row in `swarm.ab_tests` with status='active' |
| U22 | Route 80/20 split | 1000 route_model() calls | ~800 base, ~200 candidate (±5%) |
| U23 | Record result | model_used, score, latency | Row in `swarm.ab_test_results` |
| U24 | Evaluate — candidate wins | candidate_avg=0.85, base_avg=0.75, n=200 | winner='candidate', p<0.05 |
| U25 | Evaluate — no winner | candidate_avg=0.76, base_avg=0.75, n=50 | winner=None (insufficient data or not significant) |
| U26 | Welch's t-test accuracy | Known distributions | t-stat and p-value match scipy reference within 1% |
| U27 | Auto-promote candidate | concluded test with winner=candidate | Template default_model updated, old version retired |

### 1.7 GPU Queue Training Context (`agents/utils/gpu_queue.py`)

| # | Test Case | Input | Expected Output |
|---|-----------|-------|-----------------|
| U28 | is_training_window (in window) | hour=3 (window 2-6) | True |
| U29 | is_training_window (out of window) | hour=14 | False |
| U30 | is_training_window (wrap-around) | window 22-6, hour=23 | True |
| U31 | Training lock request | context="training" | Both ollama and comfyui evicted |

---

## 2. Integration Tests

### 2.1 Data Pipeline End-to-End

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| I1 | Synthetic → JSONL → Validate | Generate 10 synthetic trajectories, write to JSONL, reload and validate schema | All 10 records valid, rewards in [0,1] |
| I2 | Langfuse export → JSONL | Seed 5 traces in Langfuse with `training_candidate` tag, run export | 5 matching JSONL records with trace_ids |
| I3 | JSONL → Dataset loading | Load JSONL into HuggingFace Dataset | Correct column schema, tokenizable |

### 2.2 Training Pipeline (Requires GPU — Lovelace)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| I4 | QLoRA training (toy dataset) | 10 trajectories, 1 epoch, batch=1 | LoRA adapter saved to disk (~100MB) |
| I5 | GPU mutex during training | Start training, attempt Ollama inference | Ollama request blocked/queued until training completes |
| I6 | LoRA → GGUF conversion | Merge adapter, convert with llama.cpp | Valid GGUF file (Q4_K_M), loadable by Ollama |
| I7 | Ollama model import | Create Modelfile, `ollama create` | Model appears in `ollama list`, generates text |

### 2.3 A/B Testing Flow

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| I8 | Full A/B lifecycle | Start test → route 200 requests → evaluate → promote | Winner promoted, template updated, old model retired |
| I9 | Router integration | Submit chat_swarm request with active A/B test | Request routed to candidate or base per split ratio |
| I10 | Template updater evaluation | Run async_template_updater with concluded test | Auto-promotion triggers, version bumped |

### 2.4 Monitoring Integration

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| I11 | Grafana Training Pipeline dashboard | Open dashboard, verify all panels | 7 panels render with data from PostgreSQL-Swarm |
| I12 | Grafana Template Scores dashboard | Open dashboard, verify all panels | Score trends, invocation volume, corrector rate visible |
| I13 | Prometheus training metrics | Scrape /metrics after training run | `training_runs_total`, `training_dataset_size` incremented |
| I14 | PostgreSQL-Swarm datasource | Test connection in Grafana | Successful query against swarm.* tables |

---

## 3. System Tests

### 3.1 Full Pipeline (End-to-End on Lovelace)

| # | Test Case | Pre-conditions | Steps | Expected Result |
|---|-----------|---------------|-------|-----------------|
| S1 | Cold start pipeline | No training data exists | 1. Generate 50 synthetic trajectories<br>2. Train 1 epoch QLoRA<br>3. Convert to GGUF<br>4. Import to Ollama<br>5. Start A/B test<br>6. Run 100 requests<br>7. Evaluate | New model version in Ollama, A/B results in DB |
| S2 | Training window enforcement | Clock outside 2-6am window | Attempt training run | Rejected or queued until window opens |
| S3 | VRAM budget validation | ComfyUI + Ollama loaded | Start training | GPU mutex evicts both, training uses ~12.5GB |
| S4 | Disk space management | 3 model versions exist | Run cleanup | Oldest non-promoted version removed |

### 3.2 Failure Recovery

| # | Test Case | Fault Injected | Expected Result |
|---|-----------|---------------|-----------------|
| S5 | Training OOM | Reduce VRAM artificially | Training fails gracefully, status='failed', GPU released |
| S6 | DB connection lost mid-training | Kill PostgreSQL | Training completes locally, DB write retried on reconnect |
| S7 | Ollama unavailable for import | Stop Ollama during GGUF import | Error logged, GGUF preserved for manual import later |
| S8 | Langfuse export auth failure | Wrong credentials | Clear error message, no partial data written |

---

## 4. Security & Compliance Tests

| # | Test Case | MAESTRO Layer | Steps | Expected Result |
|---|-----------|--------------|-------|-----------------|
| C1 | Training data sanitization | L2 (Data) | Check exported JSONL for PII/secrets | No env vars, API keys, or credentials in training data |
| C2 | Model provenance tracking | L6 (Governance) | Check swarm.model_versions after training | Full chain: dataset → training_run → adapter → GGUF → ollama_model |
| C3 | GPU mutex prevents inference disruption | L1 (Infrastructure) | Run training, verify inference blocked | No concurrent GPU access during training |
| C4 | Training container isolation | L1 (Infrastructure) | Inspect training-runtime container | Non-root user (uid 1000), read-only agent code mount |
| C5 | A/B test traffic control | L4 (Agent Logic) | Verify split ratio over 500 requests | Actual split within ±3% of configured split |
| C6 | Auto-promotion safety | L4 (Agent Logic) | Candidate wins with p=0.06 (not significant) | Promotion blocked, test continues |

---

## 5. Performance Tests

| # | Test Case | Metric | Target |
|---|-----------|--------|--------|
| P1 | Synthetic generation throughput | trajectories/minute | >5/min with local Ollama |
| P2 | QLoRA training speed (10 trajectories) | time to complete | <30 min on RTX 5060 Ti |
| P3 | LoRA merge + GGUF conversion | time to complete | <10 min for 8B model |
| P4 | A/B test routing overhead | added latency per request | <5ms |
| P5 | Dashboard query performance | panel load time | <3s per panel |

---

## 6. Execution Plan

### Phase A: Unit Tests (Local, No GPU Required)
```bash
# Run from repo root
pytest tests/test_training_pipeline.py -v --tb=short
```

### Phase B: Integration Tests (Requires Docker + PostgreSQL)
```bash
# Ensure control plane DB is accessible
pytest tests/test_training_integration.py -v --tb=short

# Manual: verify Grafana dashboards at http://192.168.2.103:3002
```

### Phase C: System Tests (Requires Lovelace + GPU)
```bash
# Build training runtime
cd execution_plane
docker compose --profile training build training-runtime

# Run full pipeline test
docker compose --profile training run --rm training-runtime \
  python -m training.synthetic_gen --target_count=50 --output=/workspace/training_data/test_synthetic.jsonl

docker compose --profile training run --rm training-runtime \
  python -m training.grpo_trainer --dataset=/workspace/training_data/test_synthetic.jsonl --epochs=1

docker compose --profile training run --rm training-runtime \
  python -m training.convert_gguf --adapter=/workspace/training_output/grpo_*/adapter
```

### Phase D: Security & Compliance Review
- Manual review of exported training data for sensitive content
- Verify model provenance chain in PostgreSQL
- Validate container security posture

---

## 7. Test Environment Requirements

| Requirement | Details |
|-------------|---------|
| PostgreSQL | Control plane (192.168.2.102:5432) with swarm schema applied |
| Ollama | Lovelace (192.168.2.101:11434) with qwen2.5-coder model |
| Grafana | Turing (192.168.2.103:3002) with PostgreSQL-Swarm datasource |
| Docker | Training-runtime image built on Lovelace |
| GPU | RTX 5060 Ti (16GB VRAM) on Lovelace |
| Network | All 3 nodes reachable on 192.168.2.0/24 |

---

## 8. Exit Criteria

- [ ] All unit tests pass (U1-U31)
- [ ] Integration tests I1-I3 pass (data pipeline)
- [ ] Integration tests I4-I7 pass (training — requires GPU build)
- [ ] Integration tests I8-I10 pass (A/B testing)
- [ ] Integration tests I11-I14 pass (monitoring)
- [ ] System test S1 completes successfully (full pipeline)
- [ ] Security tests C1-C6 pass
- [ ] Performance targets P1-P5 met
- [ ] All evidence captured in `docs/evidence/phase6_training_pipeline_audit_2026_03_21.md`

---

**Document Version**: 1.0
**Author**: Home AI Lab Engineering
**Last Updated**: 2026-03-21
