---
title: Agent System
---

# Agent System

How Memex classifies user intent, selects the right agent, and orchestrates complex tasks.

## Semantic Router

The router is the "frontal cortex" of the system. It uses **qwen3:8b** (default, configurable via `ROUTER_MODEL` env var) to classify every user message into one of 15 intents. A keyword fast-path (`fast_classify`) handles 5 high-confidence patterns in < 1 ms before the LLM is invoked.

### Fast-Path Rules (keyword bypass)

Five intents match via regex before the LLM is called:

| Intent | Pattern examples | Confidence |
|--------|-----------------|------------|
| `VISION` | "what do you see", "describe this image", "analyze this image", "OCR" | 0.92 |
| `ACTION_FIGURE` | "action figure", "posable", "ball joint", "articulated figure" | 0.95 |
| `IOT_CONTROL` | "turn on/off", "lights on/off", "set temperature", "run scene" | 0.92 |
| `IOT_DEV` | "wokwi", "flash esp32", "compile firmware", "mqtt", "arduino" | 0.90 |
| `TRAIN` | "remember that", "learn this", "correction:", "from now on" | 0.92 |

All other intents (IMAGE, CODE, DEVOPS, DATA, CREATIVE, RESEARCH, COORDINATE, CONVERSATION, etc.) fall through to the LLM router so confidence scores are real.

### Intent Categories

| Intent | Description | Routes To |
|--------|-------------|-----------|
| `CONVERSATION` | Chat, questions, small talk | MarsRL Loop |
| `CODE` | Programming, debugging, scripts | Promoted to `COORDINATE` |
| `DEVOPS` | Docker, CI/CD, Linux | MarsRL Loop |
| `DATA` | SQL, analytics, CSV, stats | MarsRL Loop |
| `IMAGE` | 2D art, photos, illustrations | Image Agent → ComfyUI |
| `3D` | 3D models, meshes, geometry | 3D Pipeline |
| `ACTION_FIGURE` | Posable figure design | Action Figure Agent |
| `CREATIVE` | Fiction, stories, scene descriptions, lore | Creative Writer agent |
| `RESEARCH` | Deep analysis, comparison | Librarian agent |
| `DOCUMENTATION` | Writing, reformatting, summaries | Technical Writer agent |
| `TRAIN` | Teaching preferences / rules | Memory System |
| `IOT_CONTROL` | Smart home device control | IoT Agent → Home Assistant |
| `IOT_DEV` | Firmware, circuits, MQTT | IoT Dev Agent |
| `VISION` | Analyzing images | Vision Agent (Moondream) |
| `COORDINATE` | Complex multi-step tasks | Lamport Coordinator |

### Classification Flow

```mermaid
graph TD
    A[User Message] --> B{Fast-path regex?}
    B -->|"VISION / ACTION_FIGURE / IOT_CONTROL / IOT_DEV / TRAIN"| D[Accept Intent]
    B -->|"no match"| C[LLM Router — qwen3:8b]
    C --> E{Confidence}
    E -->|"≥ 0.75"| D
    E -->|"< 0.75"| F[Retry with stronger prompt]
    F --> E
    E -->|"Timeout/failure"| G[Fallback: CONVERSATION]
    D --> H{Confidence gate ≥ 0.80?}
    H -->|"yes or gate-exempt"| I[Dispatch to handler]
    H -->|"no"| J[clarification_card — ask user]
```

### Confidence Gate

After the router returns an intent, `chat_swarm()` applies a **confidence gate** at `_CONFIDENCE_GATE = 0.80`. If the intent is not in the exempt set and confidence is below 0.80, the system yields a `clarification_card` event asking the user to clarify rather than guessing.

Gate-exempt intents (low-risk or highly specific, skip the gate):
`CONVERSATION`, `TRAIN`, `VISION`, `ACTION_FIGURE`, `DOC_STANDARDS`, `AMBIGUOUS`

### Router Output

```json
{
    "intent": "CREATIVE",
    "confidence": 0.91,
    "reasoning": "User requested a vivid scene description for fiction",
    "disambiguation_question": null
}
```

## Agent Roles

### Core Agents

| Agent | File | Model | Purpose |
|-------|------|-------|---------|
| **Solver / Architect** | `architect_agent.py` | {{ solver_model }} | Primary response generation |
| **Verifier** | `verifier_agent.py` | Multi-layer | Output validation |
| **Corrector** | `corrector_agent.py` | {{ solver_model }} | Error correction |
| **Security Agent** | `security_agent.py` | — | Command safety, blocklist enforcement |

### Specialized Agents

| Agent | File | Purpose |
|-------|------|---------|
| **Image Gen** | `specialized/image_gen.py` | ComfyUI pipeline orchestration |
| **BMO Agent** | `specialized/bmo_agent.py` | BMO character voice personality |
| **IoT Agent** | `specialized/iot_agent.py` | Home Assistant device control |
| **Voice Assistant** | `specialized/voice_assistant.py` | Voice interaction handler |
| **Action Figure** | `specialized/action_figure_agent.py` | Articulated figure design |
| **Forge Agent** | `specialized/forge_agent.py` | 3D model reconstruction |

## Coordinator

The Coordinator handles `COORDINATE` and `RESEARCH` intents by orchestrating multiple agents in parallel.

### Phases

```mermaid
graph LR
    A[User Task] --> B[Decompose]
    B --> C[Research · Parallel]
    C --> D[Synthesize]
    D --> E[Implement]
    E --> F[Verify]
```

| Phase | Description |
|-------|-------------|
| **Decompose** | LLM breaks the task into subtasks |
| **Research** | Parallel workers investigate unknowns |
| **Synthesize** | Merge findings into a coherent plan |
| **Implement** | Execute the plan with appropriate agents |
| **Verify** | Fresh worker validates the results |

### Worker Roles

```python
# Role → Agent mapping
"architect" → Architect Agent
"coder"     → Architect Agent  
"devops"    → Architect Agent
"analyst"   → Data Analyst Agent
"researcher"→ Research Worker
"verifier"  → Verification Worker
```

Workers communicate via a shared scratchpad (filesystem-based) for intermediate artifacts.

## ExpertiseTemplate System

The template registry controls which model, parameters, and tools are used for each intent:

```mermaid
graph LR
    A[Intent: CODE] --> B[Template Registry]
    B --> C[Model: qwen3.5:9b]
    B --> D[Tools: file_ops, terminal]
    B --> E[Params: temp=0.7, top_p=0.9]
    B --> F[A/B Variant: 10% traffic]
```

Templates support:

- **Default models** per intent
- **A/B testing** with percentage-based traffic splitting
- **Version tracking** for rollback
- **Parameter overrides** per template

## Router Architecture

`church.py` is the main dispatch generator called by the API layer. It was refactored from a 3,173-line monolith into a **thin wrapper (~500 lines) + handler package** in May 2026. See [ADR-005](decisions/adr-005-church-handlers.md) for the full rationale.

```
agents/
├── church.py                  # Thin wrapper — session init, routing, dispatch
├── semantic_router.py         # Intent classification (qwen3:8b LLM + 5-rule fast-path)
├── intent_capabilities.py     # Intent → JWT-ACE capability mapping
├── handlers/
│   ├── base.py                # Shared emitters, Langfuse helpers, RAG utilities
│   ├── architect.py           # Default code/arch — fast-pass or MarsRL
│   ├── conversation.py        # CONVERSATION — 3-tier access
│   ├── coordinate.py          # COORDINATE — Lamport multi-agent
│   ├── creative.py            # CREATIVE — fiction, scene descriptions, narratives
│   ├── devops.py              # DEVOPS, DATA, AMBIGUOUS
│   ├── image.py               # IMAGE — Art Director + QC delivery
│   ├── media.py               # 3D, ACTION_FIGURE
│   ├── research.py            # RESEARCH, DOCUMENTATION, DOC_STANDARDS
│   ├── design.py              # DESIGN — OpenDesign client
│   ├── train.py               # TRAIN, IOT_CONTROL
│   └── vision.py              # VISION — Moondream VLM
└── routing/
    └── gates.py               # Pending-context dispatch (9 multi-turn types)
```

Each handler is a **generator function** `handle_X(user_input: str, ctx: dict)` that yields SSE events. Shared state flows through the `ctx` dict built by `chat_swarm()`.

## Key Files

| File | Purpose |
|------|---------|
| `agents/church.py` | Request handling, token issuance, intent dispatch |
| `agents/handlers/` | One module per intent group |
| `agents/routing/gates.py` | Multi-turn pending-context gates |
| `agents/semantic_router.py` | Intent classification using qwen3:8b (LLM) + 5-rule keyword fast-path |
| `agents/coordination/` | Multi-worker orchestration (Lamport) |
| `agents/mars_loop.py` | MarsRL verification pipeline |
| `agents/expertise/template_registry.py` | Model/parameter resolution |
| `agents/intent_capabilities.py` | Intent → capability mapping |

## Related

- [ADR-005: church.py Handler Package](decisions/adr-005-church-handlers.md) — router refactor rationale
- [Architecture: Data Flow](data-flow.md) — full request lifecycle
- [Architecture: MarsRL](marsrl-deep-dive.md) — quality verification details
- [Module: Router](../modules/router.md) — implementation reference
- [Module: Coordinator](../modules/coordinator.md) — orchestration details
- [Developer Guide: Adding Agents](../developer-guide/adding-agents.md) — create new agents


