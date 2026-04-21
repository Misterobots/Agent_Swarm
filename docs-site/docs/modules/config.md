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

## Related

- [Admin: Environment Variables](../admin-guide/configuration/environment.md) — full reference


