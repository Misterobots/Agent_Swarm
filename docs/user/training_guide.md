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

- Full metrics (loss, runtime, trainable params, budget info)
- Error messages (for failed runs)
- Duration, dataset size, target model

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
| GET | `/v1/training/curated-datasets` | List available curated datasets |
| POST | `/v1/training/start` | Launch a training run (see body below) |
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
