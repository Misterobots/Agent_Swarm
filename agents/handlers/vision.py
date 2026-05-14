"""handlers/vision.py — VISION intent handler (VLM image analysis via moondream)."""

import re
import requests

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import get_best_host_for_model
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace


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

    VISION_MODEL = "moondream:latest"
    VISION_HOST = get_best_host_for_model(VISION_MODEL)

    try:
        image_data = None
        if extracted_context:
            b64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', extracted_context)
            if b64_match:
                image_data = b64_match.group(1)
            elif extracted_context.startswith("/9j/") or extracted_context.startswith("iVBOR"):
                image_data = extracted_context

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

        payload = {
            "model": VISION_MODEL,
            "prompt": vlm_prompt,
            "images": [image_data],
            "stream": False,
        }

        yield _emit_stream_mode("responding")
        res = requests.post(f"{VISION_HOST}/api/generate", json=payload, timeout=120)
        if res.status_code == 200:
            analysis = res.json().get("response", "No analysis returned.")
            yield {"type": "response", "content": f"👁️ **Vision Analyst**\n\n{analysis}"}
            _score_trace(lf_trace, langfuse, 0.9, output=analysis, use_langfuse=use_langfuse)
        else:
            yield {"type": "error", "content": f"Vision model returned status {res.status_code}"}
            _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    except Exception as e:
        import logging
        logging.getLogger("Router").error("[Vision] Analysis failed: %s", e, exc_info=True)
        yield {"type": "error", "content": f"Vision analysis failed: {e}"}
        _score_trace(lf_trace, langfuse, 0.0, use_langfuse=use_langfuse)

    AGENT_STATE.labels(agent_name="VisionAnalyst").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="VisionAnalyst").inc()
