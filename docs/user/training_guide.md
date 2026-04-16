# Training Interface Guide

> **Back to:** [Documentation Index](../INDEX.md)

---

## Overview

The Training interface lets you fine-tune the Hive's language models directly from the browser. Instead of running CLI commands on individual machines, you select a training strategy, configure options, and launch — the system handles dataset preparation, security scanning, and GPU-bound training across the cluster.

Access it from the sidebar: **Training** > choose a tab (Overview, Run History, or Launch).

---

## Tabs

### Overview

Live dashboard showing:

- **Training Data** — total samples available (exported traces + synthetic + curated datasets)
- **Last Run** — status, model, loss, runtime of the most recent training run
- **A/B Tests** — count of model versions currently in A/B testing
- **Model Versions** — table of all trained adapters with status (candidate, ab_testing, promoted, retired), average score, and invocation count

If a run is in progress, an amber banner appears at the top with a start time and run ID.

Auto-refreshes every 15 seconds.

### Run History

Paginated table of all past training runs. Click any row to expand and see:

- **Training Report** — timing breakdown (training vs overhead), model info, hyperparameters, results, deployment status
- **Convert to Ollama Model** button — merges the LoRA adapter into the base model and imports it into Ollama for inference (appears for completed training runs)
- **Deploy for A/B Testing** button — starts an A/B test comparing the new model against the current baseline (appears after conversion)
- Error messages (for failed runs)

Auto-refreshes every 30 seconds.

### Launch

Where you start new training runs. There are five run types, described below.

---

## Run Types

### 1. Full Pipeline

**What it does:** Exports high-reward traces from Langfuse, then trains on the exported data.

**When to use:** You have active agent usage generating Langfuse traces with `training_candidate` scores, and you want to train on your own real-world conversations.

**Flow:**
```
Langfuse traces (score > 0.8)
  --> Export to GRPO JSONL
    --> QLoRA GRPO training on Execution Node GPU
      --> LoRA adapter saved
```

**Example scenario:**
The Hive has been running for a week handling coding tasks. You want the Solver model to improve based on verified successful traces. Select Full Pipeline, set a 1-hour time budget, and launch. The system exports ~200 high-scoring traces from Langfuse and trains on them.

---

### 2. Curated Datasets

**What it does:** Downloads verified datasets from HuggingFace Hub, converts them to GRPO format, runs security scanning on every sample, then trains.

**When to use:** You want to augment training with high-quality public datasets — especially useful early on when you don't have many real traces yet.

**Available datasets:**

| Dataset | Size | Category | Best for |
|---------|------|----------|----------|
| glaive-function-calling | 113K | Tool calling | Teaching the model to use tools/functions correctly |
| hermes-function-calling | 11.6K | Tool calling | IoT and home automation tool use |
| openhermes | 1M | General | Broad code, reasoning, and conversation ability |
| glaive-code-assistant | ~120K | Code | Code generation and debugging |
| slim-orca | 518K | Reasoning | Chain-of-thought reasoning |

**Flow:**
```
HuggingFace Hub
  --> Download selected datasets
    --> Convert ShareGPT format to GRPO JSONL
      --> Security scan every sample
        --> Reject poisoned/injected samples
          --> Train on clean data
```

**Example scenario:**
You want the Solver to get better at tool calling. Select Curated Datasets, check "glaive-function-calling" and "hermes-function-calling", set max samples to 5000, set a 2-hour time budget, and launch. The system downloads both datasets, converts them, rejects any samples that fail the security scan, and trains on the rest.

**Security scanning checks for:**
- Prompt injection attempts ("ignore previous instructions", DAN mode, jailbreak scaffolding)
- Hidden payloads (base64-encoded instructions, zero-width unicode tricks)
- Adversarial suffixes (GCG-style token manipulation)
- Data exfiltration patterns (curl/wget to external URLs)
- Quality issues (repetitive/corrupted text, degenerate entropy)
- Mid-conversation system prompt injection
- Code execution attempts (eval, exec, os.system patterns)

Rejected samples are saved to a separate `_rejected.jsonl` file for audit.

---

### 3. Synthetic Generation

**What it does:** Uses local Ollama models to generate diverse multi-turn tool-use problems, scores them with the reward function, security-scans the output, then trains.

**When to use:** You want to create training data without relying on external sources or existing traces. Good for bootstrapping or filling gaps in specific domains.

**Domains generated:**
- **Code** (weighted 3x) — function writing, debugging, refactoring, API endpoints, unit tests
- **File operations** — config reading, file creation, directory listing
- **IoT / Home automation** — device control, automation rules, status checks
- **Research** — concept explanations, technology comparisons, best practices

**Flow:**
```
Task templates + random filler values
  --> Ollama solver generates response
    --> Reward function scores quality (threshold: 0.6)
      --> Security scan
        --> GRPO JSONL output
          --> Train
```

**Configuration:**
- **Trajectory target** — how many high-quality samples to generate (default: 552, based on ToolOrchestra research showing this is sufficient for meaningful GRPO improvement)
- The system makes up to 3x attempts to reach the target, since low-quality responses are filtered out

**Example scenario:**
You want more IoT training data but don't have real traces yet. Select Synthetic Generation, set target to 200, set a 30-minute time budget, and launch. The system generates ~600 candidate trajectories via Ollama, keeps the ~200 that score above 0.6, scans them, and trains.

---

### 4. Train Only

**What it does:** Trains on an existing dataset file (skips export/download/generation).

**When to use:** You already have a GRPO JSONL file in the training data directory and want to re-train or train with different hyperparameters.

**Example scenario:**
A previous curated run created `curated_20260324_160000.jsonl` with 8,000 samples. You want to train again with a higher LoRA rank. Select Train Only, expand advanced options, set LoRA rank to 32, and launch. The system picks up the latest dataset file and trains.

---

### 5. Export Only

**What it does:** Exports high-reward traces from Langfuse to GRPO JSONL without running training.

**When to use:** You want to inspect the exported data before training, or you want to accumulate exports over time before running a single training job.

**Example scenario:**
You want to review what traces would be used for training. Select Export Only and launch. Check the output file in the training data directory to verify quality before doing a Train Only run.

---

## Common Options

### Time Budget

Available for all run types except Export Only. Presets: 15 min, 30 min, 1 hour, 2 hours, 4 hours, No limit. You can also enter a custom value in minutes.

When set:
- Training automatically stops when the budget expires
- Checkpoints are saved every 50 steps so no progress is lost
- A warning is logged with <2 minutes remaining

**Recommendation:** Start with 30 minutes for small datasets (<1000 samples) or 1-2 hours for larger ones. The time budget covers only the training phase — dataset download/export/generation time is separate.

### Advanced Options

Click "Show advanced options" to configure:

| Option | Default | Description |
|--------|---------|-------------|
| LoRA Rank | 16 | Higher = more trainable parameters, better capacity but more VRAM. Try 8 for quick experiments, 32 for production runs |
| Learning Rate | 5e-6 | Lower = more stable but slower convergence. Reduce if loss is unstable |
| Epochs | 3 | Number of passes over the dataset. More epochs = more training but risk of overfitting on small datasets |

---

## After Training: Convert & Deploy

Once a training run completes, two additional steps turn the adapter into a live model:

### Convert to Ollama Model

Click **"Convert to Ollama Model"** in the expanded run details. This:

1. **Merges** the LoRA adapter into the base model (~5–15 min depending on model size)
2. **Imports** into Ollama — uses GGUF quantization if llama.cpp is installed, otherwise imports safetensors directly
3. **Records** a model version with status "candidate" in the database

The conversion report shows:
- Timing breakdown (merge, convert, Ollama import) with a visual bar
- Import method used (GGUF vs safetensors direct)
- Ollama model name and verification status
- Warnings (e.g., llama.cpp not available, path issues)

**Optional**: Set a system prompt before converting. This gets baked into the Ollama Modelfile.

### Deploy for A/B Testing

After conversion, click **"Deploy for A/B Testing"**. Configure:

| Option | Default | Description |
|--------|---------|-------------|
| Template | (first available) | Which expertise template to test against (e.g., code_developer, technical_writer) |
| Traffic Split | 20% | Percentage of requests routed to the candidate model |
| Min Invocations | 100 | Minimum samples before the test can conclude |

The deploy report shows:
- Test configuration (candidate vs baseline model)
- Live scores updating every 15 seconds
- Progress bar toward minimum invocations
- Statistical significance (p-value via Welch's t-test)
- Winner determination when sufficient data is collected

The test runs passively as real chat requests come in — no manual intervention needed. Once enough samples are collected and a statistically significant winner emerges, the test concludes automatically.

### Full Workflow

```
Training Run (completed)
  → Convert to Ollama Model (merge LoRA + import)
    → Deploy for A/B Testing (candidate vs baseline)
      → Auto-evaluate (Welch's t-test, p < 0.05)
        → Promote winner to production
```

---

## Interpreting Results

### Overview Tab Metrics

- **Training Data count** — higher is generally better, but quality matters more than quantity. 500+ high-quality samples is a reasonable starting point
- **Last Run loss** — lower is better. Typical values range 0.5-2.0. If loss doesn't decrease across runs, try a lower learning rate or more diverse data
- **Model Versions** — after training, a new adapter appears as "candidate". It gets promoted to production through A/B testing

### Run History Details

When you expand a run:
- **train_loss** — final training loss
- **train_runtime** — wall-clock seconds the training phase took
- **trainable_params** — number of LoRA parameters (determined by rank)
- **budget_limited** — true if training stopped due to time budget rather than completing all epochs

---

## CLI Usage

All training features are also available via command line for scripting or automation.

### Export traces
```bash
python -m training.export_traces --output training_data/exported.jsonl
```

### Curated dataset download + security scan
```bash
# List available datasets
python -m training.dataset_curator list

# Download and convert (with security scanning)
python -m training.dataset_curator download \
  --datasets glaive-function-calling hermes-function-calling \
  --max-samples 5000

# Scan an existing dataset file
python -m training.dataset_curator scan training_data/curated_20260324.jsonl
```

### Synthetic generation
```bash
python -m training.synthetic_gen --target 200 --output training_data/synthetic.jsonl
```

### Training
```bash
# Train with time budget
python -m training.grpo_trainer \
  --dataset training_data/curated_20260324.jsonl \
  --time-budget 60 \
  --lora-rank 16 \
  --lr 5e-6

# Train without time limit
python -m training.grpo_trainer \
  --dataset training_data/exported.jsonl \
  --epochs 5
```

---

## API Endpoints

For programmatic access or integrating with external tools:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/training/status` | Current status, dataset sizes, model versions, active run |
| GET | `/v1/training/runs?limit=50` | Paginated run history |
| GET | `/v1/training/runs/{id}/report` | Structured post-training report |
| GET | `/v1/training/runs/{id}/convert-report` | Conversion report (timing, method, warnings) |
| GET | `/v1/training/runs/{id}/deploy-report` | Live A/B test report with scores and p-value |
| GET | `/v1/training/curated-datasets` | List available curated datasets |
| GET | `/v1/templates` | List expertise templates (for deploy form) |
| POST | `/v1/training/start` | Launch a training run (see body below) |
| POST | `/v1/training/convert` | Convert adapter to Ollama model (background task) |
| POST | `/v1/training/deploy` | Start A/B test for a converted model |
| POST | `/v1/training/scan?dataset_path=...` | Scan a dataset file for poisoning |

### POST /v1/training/start — Request Body

```json
{
  "run_type": "curated",
  "time_budget_minutes": 60,
  "curated_datasets": ["glaive-function-calling", "hermes-function-calling"],
  "max_samples": 5000,
  "lora_rank": 16,
  "learning_rate": 5e-6,
  "epochs": 3
}
```

Valid `run_type` values: `"full_pipeline"`, `"curated"`, `"synthetic"`, `"training"`, `"export"`

Additional fields by run type:
- **curated**: `curated_datasets` (list of keys), `max_samples` (int)
- **synthetic**: `synthetic_target` (int, default 552)
- **training**: `dataset_path` (string, optional — uses latest if omitted)

---

## Security Model

Every training data source passes through the security scanner before reaching the training pipeline:

```
  Langfuse Traces ──┐
  HuggingFace Hub ──┤──> Security Scanner ──> Clean GRPO JSONL ──> Training
  Ollama Synthetic ─┘         │
                              └──> Rejected samples (audit file)
```

The scanner is not optional for curated and synthetic runs — it runs automatically. For Train Only runs on pre-existing files, you can trigger a manual scan via the API (`POST /v1/training/scan`) or CLI (`python -m training.dataset_curator scan <file>`).

This protects against:
- **Training data poisoning** — adversarial samples designed to make the model behave badly
- **Prompt injection via training** — samples that embed "ignore instructions" patterns the model could internalize
- **Quality degradation** — degenerate, repetitive, or corrupted content that wastes training compute

---

## Troubleshooting

**"A training run is already in progress"**
Only one run can execute at a time. Wait for the current run to finish or check Run History — if a run is stuck as "running" but the process has ended, it may be a stale record (these can be cleaned up in the database).

**Curated dataset download fails**
The GPU node (Execution Node) needs internet access to reach HuggingFace Hub. Check network connectivity. If a specific dataset is unavailable, try a different one.

**Synthetic generation produces 0 trajectories**
The Ollama model must be running and accessible. Verify `OLLAMA_HOST` is correct and the Architect model is pulled. Check that the model generates responses >20 characters (very small models may produce empty output).

**Loss not decreasing**
Try reducing the learning rate (e.g., from 5e-6 to 1e-6), increasing epochs, or using a larger/more diverse dataset. If loss spikes, the learning rate is likely too high.

**Out of VRAM during training**
Reduce LoRA rank (try 8), reduce batch size (configured in `config.py`), or set a shorter sequence length. QLoRA 4-bit quantization is already enabled to minimize VRAM usage.

---

## Source References

<details>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|-----------|
| `training/grpo_trainer.py` | Implementation | GRPO training loop with QLoRA |
| `training/export_traces.py` | Implementation | Langfuse → JSONL trace export |
| `training/dataset_curator.py` | Implementation | HuggingFace download, format conversion, security scanning |
| `training/synthetic_gen.py` | Implementation | Synthetic trajectory generation via Ollama |
| `training/security_scanner.py` | Implementation | Poison/injection detection for training data |
| `training/model_converter.py` | Implementation | LoRA merge → GGUF → Ollama import |
| `training/ab_test_manager.py` | Implementation | A/B test deployment and statistical evaluation |
| `ui/src/app/training/page.tsx` | Implementation | Training UI page with Overview/History/Launch tabs |
| `ui/src/stores/trainingStore.ts` | Implementation | Client-side training state and polling |
| [GRPO (DeepSeek)](https://arxiv.org/abs/2402.03300) | Research | Group Relative Policy Optimization algorithm |
| [QLoRA](https://arxiv.org/abs/2305.14314) | Research | Quantized Low-Rank Adaptation for efficient fine-tuning |
| [ToolOrchestra](https://arxiv.org/abs/2407.04329) | Research | Minimum viable sample count for tool-use training |

</details>

---

<details>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|---------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-03-24 | AI-Copilot | Added curated datasets, synthetic generation, and A/B testing sections |
| 2026-03-10 | AI-Copilot | Initial training guide created |

</details>

---

## Maintenance & Update Guide

### Adding New Curated Datasets

1. Add the dataset key and HuggingFace path to `training/dataset_curator.py` in the `AVAILABLE_DATASETS` dict.
2. Add format conversion logic if the dataset uses a non-ShareGPT format.
3. Update the Available Datasets table in this guide.
4. Restart the agent runtime to pick up the new dataset list.

### Tuning Training Defaults

1. Default hyperparameters (LoRA rank, learning rate, epochs) are in `training/grpo_trainer.py` and `agents/config.py`.
2. The quality score threshold for training candidates (currently `0.80`) is in `training/export_traces.py`.
3. The A/B test significance threshold (currently `p < 0.05`) is in `training/ab_test_manager.py`.

### Updating Security Scanner Rules

1. Detection patterns are in `training/security_scanner.py`.
2. Add new patterns to the `PATTERNS` dict for new attack types.
3. Test with known-good and known-bad samples before deploying.

---

## Functionality Testing

### Automated Tests

| Test File | What It Covers |
|-----------|----------------|
| `tests/test_training.py` | Training API endpoints, run lifecycle, status polling |
| `tests/test_security_scanner.py` | Poison detection, injection patterns, quality filtering |

### Manual Verification

1. **Export Only**: Run an export → verify JSONL file is created with correct format.
2. **Curated pipeline**: Select a small dataset (max 100 samples) → verify download, scan, and training complete without errors.
3. **Security scanner**: Inject a known-bad sample into a dataset → verify it appears in the `_rejected.jsonl` file.
4. **Model conversion**: After training, click Convert → verify the model appears in `ollama list`.
5. **A/B Testing**: Deploy a candidate → verify traffic split in Langfuse traces → verify statistical test runs after min invocations.
