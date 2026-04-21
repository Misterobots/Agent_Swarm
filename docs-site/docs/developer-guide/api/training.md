---
title: Training API
---

# Training API

GRPO training pipeline endpoints for model improvement.

## Start Training Run

```
POST /v1/training/start
```

### Body

```json
{
    "dataset": "comparisons/latest",
    "model": "{{ solver_model }}",
    "learning_rate": 1e-5,
    "batch_size": 4,
    "epochs": 3,
    "group_size": 4
}
```

### Response

```json
{
    "run_id": "train-abc123",
    "status": "started",
    "config": {
        "model": "{{ solver_model }}",
        "dataset_size": 1200,
        "estimated_steps": 900
    }
}
```

## Get Training Status

```
GET /v1/training/{run_id}
```

### Response

```json
{
    "run_id": "train-abc123",
    "status": "running",
    "progress": {
        "step": 450,
        "total_steps": 900,
        "epoch": 2,
        "loss": 0.342,
        "reward_mean": 0.78
    }
}
```

## Submit Comparison

```
POST /v1/training/compare
```

Human feedback for preference learning:

```json
{
    "prompt": "Write a sorting function",
    "response_a": "def sort(lst): return sorted(lst)",
    "response_b": "def sort(lst):\n    return sorted(lst, key=lambda x: x)",
    "preferred": "a",
    "session_id": "session-abc"
}
```

## List Training Runs

```
GET /v1/training/runs
```

## Training Data

Training data is stored in `training_data/`:

```
training_data/
├── comparisons/      # Human preference pairs
├── sessions/         # Session-based training data
└── rewards/          # Process-reward scores from MarsRL
```


