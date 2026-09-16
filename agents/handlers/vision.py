"""VISION intent handler with opt-in Qwen 3.8 routing."""

import logging
import requests

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import get_best_host_for_model, request_lock
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace
from handlers.qwen_vision import (
    build_vision_payload,
    context_tokens,
    extract_image_data,
    select_vision_model,
)


def handle_vision(user_input: str, ctx: dict):
    """Generator — analyse an image via the moondream VLM."""
    turn_id = ctx["turn_id"]
    extracted_context = ctx["extracted_context"]
    history_context = ctx["history_context"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    yield _emit_turn_metadata(turn_id, "Vision Analyst", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "👁️ Vision Analyst: Analyzing image..."}
    AGENT_STATE.labels(agent_name="VisionAnalyst").set(2)

    requested_model = ctx.get("requested_model") or ctx.get("selected_model") or ctx.get("model")
    try:
        context_profile, context_budget = context_tokens(ctx.get("context_profile"))
    except ValueError as exc:
        yield {"type": "error", "content": f"Vision request rejected: {exc}"}
        AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
        return

    vision_host = get_best_host_for_model("qwen3.8:27b")
    vision_model, fallback, requested_qwen = select_vision_model(vision_host, ctx)
    if not vision_model:
        yield {"type": "response", "content": (
            "👁️ **Vision Analyst**\n\n"
            "No vision model is installed. Pull one first:\n"
            "```\nollama pull minicpm-v\n```\n"
            "or `ollama pull llava:7b` for a larger model."
        )}
        AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
        return

    requested_model = requested_qwen or requested_model
    yield {
        "type": "model_metadata",
        "requested_model": requested_model,
        "actual_model": vision_model,
        "provider": "ollama",
        "fallback": bool(fallback),
        "context_profile": context_profile,
        "effective_context_tokens": context_budget,
    }

    try:
        image_data = extract_image_data(extracted_context, ctx.get("attachments"))

        if not image_data:
            yield {"type": "response", "content": (
                "👁️ **Vision Analyst**\n\n"
                "I can analyze images, but I don't see one attached to your message. "
                "Please upload an image and ask your question again."
            )}
            _score_trace(lf_trace, langfuse, 0.5, use_langfuse=use_langfuse)
            AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
            return

        vlm_prompt = user_input
        if history_context:
            vlm_prompt = f"{history_context}\n\n{vlm_prompt}"

        payload = build_vision_payload(vision_model, vlm_prompt, image_data, context_budget)

        yield _emit_stream_mode("responding")
        with request_lock("vision"):
            res = requests.post(f"{vision_host}/api/generate", json=payload, timeout=120)
            if res.status_code == 200:
                analysis = res.json().get("response", "No analysis returned.")
                yield {"type": "response", "content": f"👁️ **Vision Analyst**\n\n{analysis}"}
                _score_trace(lf_trace, langfuse, 0.9, output=analysis, use_langfuse=use_langfuse)
            else:
                yield {"type": "error", "content": f"Vision model returned status {res.status_code}"}
                _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    except Exception as e:
        logging.getLogger("Router").error("[Vision] Analysis failed: %s", e, exc_info=True)
        yield {"type": "error", "content": f"Vision analysis failed: {e}"}
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="VisionAnalyst").inc()
