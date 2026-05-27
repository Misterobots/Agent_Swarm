"""handlers/creative.py — CREATIVE intent handler (fiction, scene descriptions, narratives)."""

import logging

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model, pre_lock_status_events
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span

logger = logging.getLogger("Router")


def handle_creative(user_input: str, ctx: dict):
    """Generator — Creative Writer for fiction, scene descriptions, and narratives."""
    turn_id = ctx["turn_id"]
    history_context = ctx["history_context"]
    constraint_context = ctx["constraint_context"]
    extracted_context = ctx["extracted_context"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    from church import _resolve_model_for_intent
    from config import LIBRARIAN_MODEL, get_ollama_options

    yield _emit_turn_metadata(turn_id, "Creative Writer", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "✍️ Creative Writer: Composing..."}
    AGENT_STATE.labels(agent_name="CreativeWriter").set(2)

    resolved_model = _resolve_model_for_intent("CREATIVE", LIBRARIAN_MODEL)
    resolved_host = get_best_host_for_model(resolved_model)

    writer = Agent(
        name="Creative Writer",
        model=Ollama(id=resolved_model, host=resolved_host, options=get_ollama_options(resolved_model)),
        instructions=(
            "You are a professional Creative Writer and worldbuilder.\n"
            "Your goal is to produce vivid, immersive, richly detailed creative writing: "
            "scene descriptions, stories, narratives, character sketches, lore, poetry, "
            "dialogue, and fictional world-building.\n"
            "Write with sensory detail — sight, sound, smell, texture, atmosphere. "
            "Use strong, specific imagery. Vary sentence rhythm. Make it cinematic.\n"
            "When writing for image generation, structure the output so each key element "
            "(setting, characters, lighting, atmosphere, action) is described with enough "
            "precision that an artist or AI can render it without guessing.\n"
            "Do NOT decline creative requests. Do NOT ask for clarification unless the "
            "request is genuinely incomplete. Proceed with reasonable creative assumptions.\n"
            "If the user asks for code or technical implementation, suggest they use the "
            "Architect instead."
        ),
        show_tool_calls=False,
    )

    final_input = user_input
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"
        yield {"type": "log", "content": "[Creative Writer] Reviewed prior turns for context."}
    if constraint_context:
        final_input = f"{constraint_context}\n\n{final_input}"
    if extracted_context:
        yield {"type": "log", "content": "[Creative Writer] Reading attached context..."}
        final_input = f"{final_input}\n\n[Attached Context]:\n{extracted_context}"

    full_content = ""
    try:
        # Fix 3+5: emit GPU zone/queue status BEFORE potentially blocking on the lock
        yield from pre_lock_status_events("text", resolved_model)
        with _langfuse_span("creative_generation", "CreativeWriter", resolved_model, final_input,
                            langfuse=langfuse, use_langfuse=use_langfuse) as span_result:
            with request_lock(context="text"):
                response_stream = writer.run(final_input, stream=True)
                yield {"type": "status", "content": "✍️ Creative Writer: Writing..."}
                for chunk in response_stream:
                    if chunk.content:
                        yield _emit_stream_mode("responding")
                        full_content += chunk.content
                        yield {"type": "message", "content": chunk.content}
            span_result["output"] = full_content
        _score_trace(lf_trace, langfuse, 0.9, output=full_content, use_langfuse=use_langfuse)
    except Exception as e:
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)
        yield {"type": "error", "content": f"Creative writing failed: {e}"}

    AGENT_STATE.labels(agent_name="CreativeWriter").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="CreativeWriter").inc()
