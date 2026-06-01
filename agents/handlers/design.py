"""handlers/design.py — DESIGN Studio intent handler.

Architecture: HTML is generated locally via Ollama using per-skill system
prompts, then embedded directly in the design_artifact SSE event.  An OD
project is also created so the user gets an "Open Studio" deep link, but the
OD daemon does not do the generation (its BYOK proxy blocks RFC1918 and the
file-upload endpoint is not available in v0.5.0).
"""

import logging
import os
import time
import uuid

from phi.agent import Agent
from phi.model.ollama import Ollama

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model, pre_lock_status_events
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace, _langfuse_span

logger = logging.getLogger("Router")

_OD_WEB_URL = os.getenv("OPEN_DESIGN_WEB_URL", "http://192.168.2.101:17573")

# Internal skill name → OD daemon skill ID (where they differ)
_SKILL_ID_MAP: dict[str, str] = {
    "guizang-ppt": "html-ppt-pitch-deck",
}


def handle_design(user_input: str, ctx: dict):
    """Generator — generate HTML via Ollama, upload project to OD, stream artifact."""
    turn_id = ctx["turn_id"]
    history_context = ctx.get("history_context", "")
    extracted_context = ctx.get("extracted_context", "")
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    from config import CODER_MODEL, get_ollama_options
    from specialized.open_design_client import (
        detect_skill_from_prompt,
        get_skill_system_prompt,
        parse_artifact_html,
        create_project,
    )

    yield _emit_turn_metadata(turn_id, "Design Studio", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    AGENT_STATE.labels(agent_name="DesignStudio").set(2)

    # Skill detection — internal name used for system-prompt lookup
    internal_skill = detect_skill_from_prompt(user_input)
    od_skill_id = _SKILL_ID_MAP.get(internal_skill, internal_skill)
    yield {"type": "log", "content": f"[DesignStudio] Skill: {od_skill_id}"}

    # Create OD project for the "Open Studio" deep link (non-fatal if OD is down)
    project_id = str(uuid.uuid4())
    project_url: str | None = None
    yield {"type": "status", "content": "🎨 Design Studio: Setting up project..."}
    try:
        create_project(
            name=f"design-{int(time.time())}",
            skill_id=od_skill_id,
            project_id=project_id,
        )
        project_url = f"{_OD_WEB_URL}/#/projects/{project_id}"
        yield {"type": "log", "content": f"[DesignStudio] OD project: {project_id}"}
    except Exception as _e:
        logger.warning("[DesignStudio] OD project creation failed (non-fatal): %s", _e)

    # Generate HTML locally via Ollama
    skill_sys_prompt = get_skill_system_prompt(internal_skill)
    resolved_model = CODER_MODEL
    resolved_host = get_best_host_for_model(resolved_model)

    designer = Agent(
        name="Design Studio",
        model=Ollama(
            id=resolved_model,
            host=resolved_host,
            options=get_ollama_options(resolved_model),
        ),
        instructions=skill_sys_prompt,
        show_tool_calls=False,
    )

    # Build the final prompt: attached context doc first, then history, then user message.
    # Strip binary image data from extracted_context — the coder model is text-only;
    # images are referenced as [image attached] placeholders so the model knows they exist.
    import re as _re
    final_input = user_input
    if extracted_context:
        text_ctx = _re.sub(
            r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+',
            '[image attached — see description in prompt]',
            extracted_context,
        )
        final_input = f"[Attached context / reference material]\n{text_ctx}\n\n---\n\n{final_input}"
        yield {"type": "log", "content": f"[DesignStudio] Context injected ({len(text_ctx)} chars)"}
    if history_context:
        final_input = f"{history_context}\n\n{final_input}"

    full_output = ""
    try:
        yield {"type": "status", "content": "🎨 Design Studio: Generating design..."}
        yield from pre_lock_status_events("text", resolved_model)

        with _langfuse_span(
            "design_generation", "DesignStudio", resolved_model, final_input,
            langfuse=langfuse, use_langfuse=use_langfuse,
        ) as span_result:
            with request_lock(context="text"):
                yield _emit_stream_mode("responding")
                for chunk in designer.run(final_input, stream=True):
                    if chunk.content:
                        full_output += chunk.content
            span_result["output"] = full_output[:500]

    except Exception as e:
        AGENT_STATE.labels(agent_name="DesignStudio").set(1)
        WORKFLOW_STEPS.labels(status="error", agent_type="DesignStudio").inc()
        logger.error("[DesignStudio] Generation failed: %s", e, exc_info=True)
        yield {"type": "error", "content": f"Design Studio failed: {e}"}
        return

    html_content = parse_artifact_html(full_output)
    if not html_content:
        # parse_artifact_html already handles plain HTML as fallback; if we're
        # here the model produced something that isn't HTML at all.
        AGENT_STATE.labels(agent_name="DesignStudio").set(1)
        WORKFLOW_STEPS.labels(status="error", agent_type="DesignStudio").inc()
        yield {"type": "error", "content": "Design Studio: model did not produce an HTML artifact."}
        logger.error("[DesignStudio] No HTML extracted from output (len=%d)", len(full_output))
        return

    # Persist to workspace for future reference
    delivery_dir = "/workspace/delivered_artifacts"
    os.makedirs(delivery_dir, exist_ok=True)
    filename = f"design_{project_id}.html"
    try:
        with open(os.path.join(delivery_dir, filename), "w", encoding="utf-8") as fh:
            fh.write(html_content)
        yield {"type": "log", "content": f"[DesignStudio] Saved: {filename}"}
    except Exception as _fe:
        logger.warning("[DesignStudio] Could not save artifact file: %s", _fe)

    AGENT_STATE.labels(agent_name="DesignStudio").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="DesignStudio").inc()

    yield {
        "type": "design_artifact",
        "content": {
            "html": html_content,
            "project_id": project_id,
            "project_url": project_url,
            "filename": filename,
            "skill": od_skill_id,
        },
    }
    yield {"type": "response", "content": "✨ Design ready!"}
    _score_trace(
        lf_trace, langfuse, 0.9,
        output=f"design_artifact:{filename}",
        use_langfuse=use_langfuse,
    )
