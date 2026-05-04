---
title: "Module: Config"
---

# Config

Configuration loading and runtime settings.

## Files

| File | Purpose |
|------|---------|
| `agents/config.py` | Configuration class — loads from env and files |

## Loading Order

1. Defaults (hardcoded)
2. `network.env` file
3. Environment variables (override file values)
4. Command-line arguments (highest priority)

## Key Configuration

```python
config = Config()

config.ollama_url       # http://localhost:{{ ollama_port }}
config.solver_model     # {{ solver_model }}
config.router_model     # {{ router_model }}
config.verifier_model   # {{ verifier_model }}
config.langfuse_host    # http://{{ hopper_ip }}:3000
config.spire_socket     # /var/run/spire/agent.sock
config.log_level        # INFO
config.dev_mode         # False
```

## Environment Variable Mapping

| Variable | Config Attribute | Default |
|----------|-----------------|---------|
| `OLLAMA_HOST` | `ollama_url` | `http://localhost:{{ ollama_port }}` |
| `SOLVER_MODEL` | `solver_model` | `{{ solver_model }}` |
| `ROUTER_MODEL` | `router_model` | `{{ router_model }}` |
| `VERIFIER_MODEL` | `verifier_model` | `{{ verifier_model }}` |
| `LANGFUSE_HOST` | `langfuse_host` | `http://{{ hopper_ip }}:3000` |
| `LOG_LEVEL` | `log_level` | `INFO` |
| `DEV_MODE` | `dev_mode` | `false` |

## Archetype Training Configs

`ARCHETYPE_TRAINING_CONFIGS` maps agent archetypes to their training parameters. Used by the Training Dispatcher to validate submitted jobs and resolve dataset/epoch defaults.

```python
ARCHETYPE_TRAINING_CONFIGS: dict = {
    "coder": {
        "datasets": ["glaive-code-assistant", "code-feedback"],
        "epochs": 3,
        "base_model": TRAINING_BASE_SOLVER,
        "description": "Code generation and review"
    },
    "coordinator": {
        "datasets": ["hermes-function-calling", "slim-orca"],
        "epochs": 2,
        "base_model": TRAINING_BASE_SOLVER,
        "description": "Tool use and task delegation"
    },
    "researcher": {
        "datasets": ["openhermes", "slim-orca"],
        "epochs": 2,
        "base_model": TRAINING_BASE_SOLVER,
        "description": "Multi-step reasoning"
    },
    "creative": {
        "datasets": ["openhermes"],
        "epochs": 2,
        "base_model": TRAINING_BASE_SOLVER,
        "description": "Creative writing and ideation"
    },
}
```

| Key | `datasets` | `epochs` |
|-----|-----------|---------|
| `coder` | `glaive-code-assistant`, `code-feedback` | 3 |
| `coordinator` | `hermes-function-calling`, `slim-orca` | 2 |
| `researcher` | `openhermes`, `slim-orca` | 2 |
| `creative` | `openhermes` | 2 |

The dispatcher exposes the available keys via `GET /health` as `available_archetypes`.

## Training Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAINING_BASE_SOLVER` | `Qwen/Qwen3-27B` | Base model for all GRPO fine-tunes |
| `TRAINING_NUM_EPOCHS` | `2` | Default epochs (per-archetype overrides this) |
| `DISPATCHER_SECRET` | *(set in `.env`)* | Shared secret for Training Dispatcher auth |
| `DISPATCHER_URL` | `http://{{ lovelace_ip }}:8001` | Dispatcher endpoint (read by `agent_runtime`) |
| `EXPORT_MIN_SCORE` | `0.85` | Minimum MarsRL score for trace export |

## Related

- [Admin: Environment Variables](../admin-guide/configuration/environment.md) — full reference
- [Module: Training Dispatcher](training-dispatcher.md)
- [Training API Reference](../developer-guide/api/training.md)

