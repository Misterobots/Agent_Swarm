"""handlers/workshop.py — Product Workshop ("Grill Me") discovery handler.

Two-phase workflow
──────────────────
Phase 1  User says "grill me on X" or "workshop: X"
         → Asks 7 targeted discovery questions specific to the idea.

Phase 2  User replies with answers (detected via conversation history)
         → Generates a structured Product Brief including copy-paste-ready
           Design Mode and Swarm Mode prompts for the next pipeline phases.

The handler is purely conversational — no GPU lock contention beyond the
normal text inference slot.  It uses COORDINATOR_MODEL (Gemma4) because the
output is structured writing, not code generation.
"""

import logging

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model, pre_lock_status_events
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span

logger = logging.getLogger("Router")

# ---------------------------------------------------------------------------
# Phase 1 system prompt — discovery interview
# ---------------------------------------------------------------------------
_PHASE1_SYSTEM = """\
You are a senior product architect and startup advisor running a structured
product discovery interview.  Given a raw idea, you generate exactly 7
targeted questions that will yield a complete Product Brief when answered.

Each question must be specific to THIS idea — never generic.

Cover these angles (one per question):
1. Core value — what specific problem does it solve, and for whom exactly?
2. Primary user journey — describe the experience from first open to "task done"
3. MVP scope — what are the 3–5 must-have features vs. nice-to-haves?
4. Visual / aesthetic — what should it look and feel like?  Any reference points?
5. Platform & technical constraints — where does it run?  Offline?  Integrations needed?
6. Success criterion — what does "shipped and working" look like to you?
7. Hardest part — what's the riskiest or most uncertain aspect of building this?

REQUIRED FORMAT — follow exactly, one question per line:
1. **[Topic Label]**: Full question text here.
2. **[Topic Label]**: Full question text here.
... (continue for all 7)

Topic Labels must be short (2–4 words), e.g. "Target User", "Interaction Flow",
"MVP Scope", "Visual Style", "Platform & Offline", "Success Criterion", "Biggest Risk".

End with exactly this line:
"Answer any or all of these and I'll draft your Product Brief."
"""

# ---------------------------------------------------------------------------
# Phase 2 system prompt — Product Brief generation
# ---------------------------------------------------------------------------
_PHASE2_SYSTEM = """\
You are a senior product architect writing a structured Product Brief from a
discovery session.  Given the original idea and the user's answers, produce a
complete, actionable brief.

Use exactly these headers:

## Product Brief: [Product Name]

### Vision
[2–3 sentences — what it is, who it's for, core value proposition]

### MVP Feature Set
[Bulleted list.  Mark each item: **(MVP)** or **(V2)**]

### Technical Stack
[Specific, opinionated recommendations — framework, language, key libraries,
deployment target.  No "you could use X or Y" hedging — pick one.]

### Design Direction
[Visual style, aesthetic references, UI patterns, animation approach,
colour palette direction]

### Architecture Overview
[How the pieces connect — 4–6 bullet points, concrete enough to scaffold from]

---
### Design Mode Prompt
```
[A rich, copy-paste-ready prompt for Design Mode.  Must include: platform,
visual style, key screens/states, interaction patterns, colour/typography
direction.  Make it specific enough that the Design Studio generates
something immediately useful, not generic.]
```

### Swarm Mode Prompt
```
[A copy-paste-ready prompt for Swarm Mode, scoped to MVP only.
Must include: tech stack, 3–5 concrete deliverables, file structure hints,
success criterion, and one sentence on each of the trickiest parts.]
```

### Watch Points
[2–3 specific risks or hard problems worth tackling early — not generic
"make sure to test" advice, but actual project-specific concerns.]

Be concrete.  Avoid hedging language.  Write as if you'll be held accountable
for the outcome.
"""


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handle_workshop(user_input: str, ctx: dict):
    """Generator — two-phase product discovery workshop."""
    turn_id       = ctx["turn_id"]
    history_context = ctx.get("history_context", "")
    owner_id      = ctx.get("owner_id")
    lf_trace      = ctx["lf_trace"]
    langfuse      = ctx["langfuse"]
    use_langfuse  = ctx["use_langfuse"]

    from config import COORDINATOR_MODEL, get_ollama_options

    # ------------------------------------------------------------------
    # Phase detection — are we generating questions or a Product Brief?
    # ------------------------------------------------------------------
    _PHASE1_SENTINEL = "Answer any or all of these and I'll draft your Product Brief."
    _PHASE2_SENTINEL = "Design Mode Prompt"

    _in_answer_phase = bool(history_context) and (
        _PHASE1_SENTINEL in history_context
        or _PHASE2_SENTINEL in history_context
    )

    if _in_answer_phase:
        phase_label  = "Drafting Product Brief"
        system_prompt = _PHASE2_SYSTEM
        final_input  = (
            f"[Workshop discovery session — prior context]\n{history_context}\n\n"
            f"[User answers]\n{user_input}\n\n"
            "Generate the complete Product Brief now."
        )
        status_msg = "🎯 Workshop: Writing your Product Brief..."
    else:
        phase_label  = "Discovery Interview"
        system_prompt = _PHASE1_SYSTEM
        final_input  = f"Idea to explore: {user_input}"
        status_msg = "🎯 Workshop: Preparing your discovery session..."

    yield _emit_turn_metadata(turn_id, f"Workshop · {phase_label}", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": status_msg}
    AGENT_STATE.labels(agent_name="Workshop").set(2)

    resolved_model = COORDINATOR_MODEL
    resolved_host  = get_best_host_for_model(resolved_model)

    workshop_agent = Agent(
        name="Product Workshop",
        model=Ollama(
            id=resolved_model,
            host=resolved_host,
            options=get_ollama_options(resolved_model),
        ),
        instructions=system_prompt,
        show_tool_calls=False,
    )

    # Phase 1: emit loading skeleton immediately so the UI shows a placeholder
    # while the model is warming up and generating questions.
    if not _in_answer_phase:
        yield {
            "type": "workshop_questions",
            "content": {"questions": [], "loading": True},
        }

    full_content = ""
    try:
        yield from pre_lock_status_events("text", resolved_model)

        with _langfuse_span(
            "workshop_generation", "Workshop", resolved_model, final_input,
            langfuse=langfuse, use_langfuse=use_langfuse,
        ) as span_result:
            with request_lock(context="text"):
                yield _emit_stream_mode("responding")
                for chunk in workshop_agent.run(final_input, stream=True):
                    if chunk.content:
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
            span_result["output"] = full_content[:500]

    except Exception as exc:
        AGENT_STATE.labels(agent_name="Workshop").set(1)
        WORKFLOW_STEPS.labels(status="error", agent_type="Workshop").inc()
        logger.error("[Workshop] Generation failed: %s", exc, exc_info=True)
        yield {"type": "error", "content": f"Workshop failed: {exc}"}
        return

    AGENT_STATE.labels(agent_name="Workshop").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="Workshop").inc()
    _score_trace(
        lf_trace, langfuse, 0.9,
        output=full_content[:300],
        use_langfuse=use_langfuse,
    )

    import re as _re

    # Cross-session persistence ─────────────────────────────────────────────
    # Phase 1 complete: save output owner-scoped so any device/tab can resume.
    # Phase 2 complete: clear it — the workshop is done.
    if owner_id:
        from brooks import save_workshop_state, clear_workshop_state
        if not _in_answer_phase:
            save_workshop_state(full_content, user_input, owner_id)
        else:
            clear_workshop_state(owner_id)

    # Phase 1: parse questions into structured chips for the UI.
    if not _in_answer_phase:
        _questions = []
        for _m in _re.finditer(
            r'(\d+)\.\s+\*?\*?([^*:\n]+?)\*?\*?:\s*(.+?)(?=\n\d+\.\s+\*?\*?|\nAnswer any|$)',
            full_content,
            _re.DOTALL,
        ):
            _questions.append({
                "number": int(_m.group(1)),
                "topic": _m.group(2).strip(),
                "text":  _m.group(3).strip().replace("\n", " "),
            })
        if _questions:
            yield {
                "type": "workshop_questions",
                "content": {"questions": _questions},
            }

    # Phase 2: extract Design Mode and Swarm Mode prompts from the brief
    # and emit them as one-click next-step action buttons.
    if _in_answer_phase:
        _steps = []

        def _extract_prompt(heading_pat: str, stop_pat: str) -> str | None:
            """Extract a prompt block from the brief, with and without code fences."""
            # Primary: code-fenced block (as instructed in the system prompt)
            m = _re.search(
                heading_pat + r'[^\n]*\n+```[^\n]*\n(.*?)```',
                full_content, _re.DOTALL | _re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()
            # Fallback: grab section text until the next heading or document end
            m = _re.search(
                heading_pat + r'[^\n]*\n+(.*?)(?=' + stop_pat + r'|\Z)',
                full_content, _re.DOTALL | _re.IGNORECASE,
            )
            if m:
                # Strip any orphaned backticks left by a partial code fence
                text = m.group(1).strip().strip('`').strip()
                return text if text else None
            return None

        _design_prompt = _extract_prompt(
            r'Design Mode Prompt',
            r'\n#{1,4}\s|\n\*\*(?:Swarm|Build|⚙)',
        )
        if _design_prompt:
            _steps.append({
                "label": "Generate Mockup",
                "mode":  "design",
                "icon":  "palette",
                "prompt": _design_prompt,
            })

        _swarm_prompt = _extract_prompt(
            r'(?:Swarm|Build|Coordinator)[^\n]*Prompt',
            r'\n#{1,4}\s',
        )
        if _swarm_prompt:
            _steps.append({
                "label": "Start Build",
                "mode":  "swarm",
                "icon":  "code",
                "prompt": _swarm_prompt,
            })

        if _steps:
            yield {
                "type": "workflow_next_steps",
                "content": {"steps": _steps},
            }
        else:
            logger.warning("[Workshop] Phase 2 complete but could not parse next-step prompts from brief.")
