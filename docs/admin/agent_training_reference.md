# Admin: Agent Training Reference

> **Back to:** [Documentation Index](../INDEX.md)
> **See also:** [Technical Reference](technical_reference.md) · [Design Framework](design_framework.md)

**Version**: 3.3 · **Status**: Production · **Last Updated**: 2026-03-26

---

## 1. Agent Architecture Overview

The system uses a multi-layer routing architecture to classify user intent and dispatch to the correct specialized agent.

```
User Input
    │
    ▼
[Keyword Override Layer]
  Pre-checks for unambiguous keywords before LLM runs
  e.g., "action figure", "posable" → ACTION_FIGURE
    │
    ▼ (if no keyword match)
[Semantic Router — nemotron-orchestrator:8b on Gateway Ollama]
  LLM-based intent classification
    │
    ▼
[Dispatcher]
  Simple keyword classifier for GPU queue routing
    │
    ▼
[Intent Capabilities]
  Maps intent → agent, security level, template ID
    │
    ▼
[ExpertiseTemplate Registry]
  PostgreSQL-backed versioned templates with performance tracking
    │
    ▼
[Specialized Agent]
```

### Intent Categories

The semantic router classifies input into one of these categories:

| Intent | Description |
|--------|-------------|
| `CONVERSATION` | General chat, greetings, small talk |
| `CODE` | Code generation, debugging, architecture |
| `DEVOPS` | Infrastructure, Docker, CI/CD |
| `DATA` | Data analysis, SQL, visualization |
| `IMAGE` | Image generation, editing |
| `3D` | 3D model generation |
| `ACTION_FIGURE` | Posable action figure design |
| `RESEARCH` | Information lookup, summarization |
| `DOCUMENTATION` | Writing docs, README, guides |
| `TRAIN` | Model training, fine-tuning requests |
| `IOT_CONTROL` | Smart home device control |
| `IOT_DEV` | IoT development, firmware, sensors |

### Layer Responsibilities

**Keyword Override Layer**: Pre-checks input for unambiguous keywords before the LLM runs. This layer exists to support new intents that the LLM has not been fine-tuned to recognize yet. When the base model learns the intent (via fine-tuning), the keyword override can be removed.

**Semantic Router**: The primary classification engine. Runs `nemotron-orchestrator:8b` on the Gateway Node with a system prompt containing the full category list and example keywords. Classification accuracy depends on both the system prompt and any fine-tuning applied.

**Dispatcher**: Separate from the semantic router. Handles GPU queue assignment based on keyword detection in `detect_intent()`. Manages concurrency limits per queue.

**Intent Capabilities**: Static mapping from intent to agent capabilities, security level, and template ID. Defined in `intent_capabilities.py`.

**ExpertiseTemplate Registry**: PostgreSQL-backed (`swarm.expertise_templates`) versioned templates. Each template carries a system prompt, capability list, default model, and security level. Performance is tracked per-version.

---

## 2. Adding a New Agent (Step-by-Step)

To add a new specialized agent (as was done for Action Figure Forge), the following files must be updated:

| File | What to Add |
|------|-------------|
| `agents/specialized/<agent_name>.py` | Agent implementation with pipeline logic |
| `agents/semantic_router.py` | New category in the LLM prompt (categories list) |
| `agents/dispatcher.py` | Keyword detection in `detect_intent()` + queue config |
| `agents/intent_capabilities.py` | Capability mapping: agent_name, template_id, capabilities, security_level, expiry_hours |
| `agents/expertise/template_registry.py` | Seed template in `_SEED_TEMPLATES` list |
| `agents/router.py` | Route block in `chat_swarm()` + add intent to MarsRL exclusion list |
| `agents/ui.py` | Artifact renderer + workspace integration |

### Critical Notes

**MarsRL exclusion list**: The MarsRL catch-all at the bottom of `router.py` uses `if intent not in (...)`. New intents **must** be added to this exclusion tuple or they will fall through to the code architect agent.

**Keyword override bridge**: The semantic router LLM will not know about new intents until it has been fine-tuned. Use the keyword override layer as a bridge for immediate recognition. See Section 3 for details.

**Return statements**: Each route block in `chat_swarm()` must end with `return` to prevent fall-through into subsequent route blocks.

**Creative intents**: Intents classified as creative work (`IMAGE`, `3D`, `ACTION_FIGURE`) redirect to the Art Studio workspace instead of running inline in the chat stream.

---

## 3. Training the Semantic Router to Recognize New Intents

There are three approaches to teach the semantic router new intents, listed from fastest to most durable.

### Option A: Keyword Override (Immediate, No Training)

Add keyword patterns to the override block in `router.py`, after intent classification and before routing. This provides instant recognition for unambiguous phrases.

Example for ACTION_FIGURE:
- Keywords: "action figure", "posable", "ball joint"
- If any keyword matches, the intent is set directly without consulting the LLM

This is a bridge. Once the model has been fine-tuned, the keyword override should be removed to let the LLM handle classification natively.

### Option B: Fine-Tune via the Training Pipeline

This is the durable solution. It teaches `nemotron-orchestrator:8b` to classify the new intent without keyword assistance.

1. **Generate synthetic training data** with the new intent:
   - Create example prompts that should map to the new intent
   - Format as GRPO JSONL with the expected classification output
2. **Run training** via the Training interface (Curated Datasets or Train Only mode)
3. **Convert the adapter** and deploy via A/B testing
4. **Promote** the new model version once A/B results confirm accuracy
5. **Remove the keyword override** once the fine-tuned model is serving

See [Technical Reference — Section 8](technical_reference.md) for the full training pipeline commands.

### Option C: Update the System Prompt

The semantic router's system prompt in `semantic_router.py` contains the full category list with descriptive keywords. Adding a new category here makes the LLM aware of it immediately.

Accuracy depends on the base model's ability to generalize from the prompt alone. This works well for intents that are clearly distinct from existing categories, but may produce misclassifications for ambiguous or overlapping intents. Combine with Option A for reliability until Option B is completed.

---

## 4. ExpertiseTemplate System

Templates are stored in PostgreSQL (`swarm.expertise_templates`) with full versioning and performance tracking.

### Template Structure

Each template contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, e.g., `"coding-expert"` |
| `name` | string | Human-readable name |
| `description` | text | Template purpose and behavior summary |
| `intent` | string | Routed intent: `CODE`, `RESEARCH`, etc. |
| `system_prompt` | text | The agent's persona prompt |
| `capabilities` | string[] | Allowed tools: `["file_ops", "terminal"]` |
| `security_level` | string | See Section 5 |
| `default_model` | string | e.g., `"qwen3.5:9b"` |

### Versioning

Versions are tracked in `swarm.expertise_template_versions` with per-version performance metrics:
- `avg_score` — running average quality score
- `total_invocations` — total requests served by this version
- `successful_invocations` — requests that passed verification

### Lifecycle

1. Templates are seeded from `_SEED_TEMPLATES` in `template_registry.py` on first run
2. To create a new version: `registry.bump_version(template_id, changes)`
3. Performance is recorded after each invocation: `registry.record_performance(record)`
4. When a new version's `avg_score` exceeds the previous version by a configurable threshold, it is auto-promoted and `current_version` is bumped

---

## 5. Security Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `L1_PUBLIC` | Read-only, model generation only | Research, documentation |
| `L2_USER` | File read/write, image generation, API calls | Creative, IoT, training |
| `L3_ADMIN` | Terminal exec, git operations, full file access | Code, DevOps |
| `L4_SYSTEM` | Reserved for system-level operations | Internal only |

Security levels are enforced by the JWT-ACE capability gating layer. Each agent's template declares the minimum level required, and the runtime checks the issued token's capabilities against the template before execution.

---

## 6. GPU Queue Configuration

The dispatcher manages GPU-bound work via Redis queues with per-queue concurrency limits:

| Queue | Max Concurrent | Rationale |
|-------|----------------|-----------|
| `queue:3d` | 1 | Protects GPU — 3D generation is VRAM-intensive |
| `queue:action_figure` | 1 | GPU + heavy post-processing |
| `queue:image` | 2 | Diffusion image generation (ComfyUI / Klein / OmniGen) |
| `queue:vision` | 3 | VLM analysis of existing images (lighter than diffusion) |
| `queue:default` | 5 | Chat/code, lightweight (no GPU or minimal GPU) |

Queue assignment is handled by keyword detection in `dispatcher.py` via the `detect_intent()` method. When adding a new agent that requires GPU access, add a corresponding queue entry with an appropriate concurrency limit.

---

## 7. Context Manager

The context manager provides session-scoped persistence for multi-turn interactions where the router or an agent needs to carry state across requests.

### Storage

Each session writes to `agents/context_sessions/{session_id}.json`.

### Context Types

| Type | Trigger | Purpose |
|------|---------|---------|
| `image_clarification` | Art Director asked for more detail | Stores partial prompt for follow-up |
| `ambiguity_resolution` | Router could not classify intent | Stores candidates for user disambiguation |
| `art_studio_redirect` | Creative intent detected | Saves prompt for Art Studio workspace pickup |

### Lifecycle Rules

- Context is cleared after consumption (single-use)
- Contexts over 500 characters are discarded as stale — this prevents old, verbose contexts from polluting new sessions

---

## 8. Monitoring Training Quality

### Langfuse Scoring

All agent invocations are scored in Langfuse with `training_candidate` scores. Traces that score `>= 0.90` are tagged as `training_candidate=1.0` and become eligible for export into the training dataset.

### ExpertiseTemplate Performance

The template registry tracks per-version performance metrics. To check recent quality:

```python
summary = registry.get_performance_summary(template_id, window_hours=24)
# Returns: avg_score, total_invocations, successful_invocations, corrector_rate
```

### A/B Testing

When a new model version is converted and imported into Ollama, an A/B test starts automatically:
- Traffic is split between the candidate model and the current baseline
- Per-invocation scores and latency are recorded in `swarm.ab_test_results`
- The test runs until statistical significance is reached, then the winner is promoted (or the candidate is discarded)

### Grafana Dashboards

| Dashboard | What to Check |
|-----------|---------------|
| Training Pipeline | Training runs, dataset growth, model versions, A/B test status |
| Template Performance | Score trends per template version, corrector invocation rate, latency |
| Agent Activity | Live agent states, conversation quality, MarsRL thought process |

See [Technical Reference — Section 6](technical_reference.md) for dashboard UIDs and datasource configuration.

---

*See also: [Technical Reference](technical_reference.md) · [Design Framework](design_framework.md) · [Back to Index](../INDEX.md)*
