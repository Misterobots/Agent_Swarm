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

    # Skill detection — internal name used for system-prompt lookup.
    # If the user message alone doesn't match a specific skill (falls back to
    # web-prototype), also scan the first 2 KB of extracted_context so that
    # keywords inside an attached brief/document can upgrade the skill.
    internal_skill = detect_skill_from_prompt(user_input)
    if internal_skill == "web-prototype" and extracted_context:
        ctx_skill = detect_skill_from_prompt(extracted_context[:2000])
        if ctx_skill != "web-prototype":
            internal_skill = ctx_skill
            yield {"type": "log", "content": f"[DesignStudio] Skill upgraded via context: {internal_skill}"}
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

    # Generate HTML locally via Ollama (direct chat API with assistant prefill).
    # Prefilling the assistant turn with "<!DOCTYPE html>" forces the model to begin
    # generating HTML immediately — no preamble, no explanation, no wasted tokens.
    skill_sys_prompt = get_skill_system_prompt(internal_skill)
    resolved_model = CODER_MODEL
    resolved_host = get_best_host_for_model(resolved_model)

    # Session-scoped artifact cache — stores the most recent HTML for this session
    # so revision prompts can inject it and the model can make targeted edits
    # rather than generating from scratch every time.
    session_id = ctx.get("session_id", "default_session")
    _safe_sid = "".join(c if c.isalnum() or c in "_-" else "_" for c in session_id)
    _artifact_cache_path = f"/workspace/delivered_artifacts/latest_{_safe_sid}.html"

    # Build the final prompt: attached context doc first, then history, then user message.
    # Vision bridge: the coder model (qwen3-coder:30b) is text-only, so we pre-describe
    # any attached images using gemma4:31b (multimodal) before passing context to the
    # coder.  This gives the design model actual visual information — colours, layout,
    # typography, hierarchy — rather than the useless placeholder that stripping produces.
    import re as _re
    final_input = user_input
    if extracted_context:
        from config import COORDINATOR_MODEL as _VISION_MODEL

        # Extract all data-URI images from extracted_context
        _img_pattern = _re.compile(r'data:(image/[^;]+);base64,([A-Za-z0-9+/=]+)')
        _img_matches = _img_pattern.findall(extracted_context)

        if _img_matches:
            yield {"type": "status", "content": f"Design Studio: Analysing {len(_img_matches)} image(s)..."}
            _vision_host = get_best_host_for_model(_VISION_MODEL)
            _image_descriptions: list[str] = []

            for _idx, (_mime, _b64) in enumerate(_img_matches):
                try:
                    import requests as _vreq
                    _vision_resp = _vreq.post(
                        f"{_vision_host}/api/chat",
                        json={
                            "model": _VISION_MODEL,
                            "messages": [{
                                "role": "user",
                                "content": (
                                    "You are a UI/UX design analyst. Describe this image in detail "
                                    "for a front-end developer who will recreate or reference it:\n"
                                    "- Colour palette (list specific hex/CSS values if visible)\n"
                                    "- Layout and spatial structure\n"
                                    "- Typography (fonts, sizes, weights, hierarchy)\n"
                                    "- Visual elements (icons, images, shapes, borders, shadows)\n"
                                    "- Interactive states visible (hover, active, etc.)\n"
                                    "- Overall aesthetic and design language\n"
                                    "Be precise and technical."
                                ),
                                "images": [_b64],
                            }],
                            "stream": False,
                            "options": {"num_ctx": 8192, "temperature": 0.1},
                        },
                        timeout=120,
                    )
                    if _vision_resp.status_code == 200:
                        _desc = _vision_resp.json().get("message", {}).get("content", "")
                        if _desc:
                            _image_descriptions.append(f"[Image {_idx + 1} — {_mime}]\n{_desc}")
                            yield {"type": "log", "content": f"[DesignStudio] Vision bridge: image {_idx + 1} described ({len(_desc)} chars)"}
                        else:
                            _image_descriptions.append(f"[Image {_idx + 1}] (description unavailable)")
                    else:
                        _image_descriptions.append(f"[Image {_idx + 1}] (vision model returned {_vision_resp.status_code})")
                        logger.warning("[DesignStudio] Vision bridge HTTP %s for image %d", _vision_resp.status_code, _idx + 1)
                except Exception as _ve:
                    _image_descriptions.append(f"[Image {_idx + 1}] (vision analysis failed: {_ve})")
                    logger.warning("[DesignStudio] Vision bridge failed for image %d: %s", _idx + 1, _ve)

            # Replace base64 blobs with the generated descriptions
            _descriptions_block = "\n\n".join(_image_descriptions)
            text_ctx = _img_pattern.sub("", extracted_context).strip()
            if text_ctx:
                text_ctx = f"{text_ctx}\n\n[Visual Reference Analysis]\n{_descriptions_block}"
            else:
                text_ctx = f"[Visual Reference Analysis]\n{_descriptions_block}"
        else:
            # No images — strip any stray base64 just in case and pass text through
            text_ctx = _re.sub(
                r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+',
                '',
                extracted_context,
            ).strip()

        if text_ctx:
            final_input = f"[Attached context / reference material]\n{text_ctx}\n\n---\n\n{final_input}"
            yield {"type": "log", "content": f"[DesignStudio] Context injected ({len(text_ctx)} chars)"}

    # Revision mode: inject the previous HTML so the model edits in-place instead
    # of regenerating. Without this, the model only sees "Design ready." as prior
    # context and cold-starts a fresh design on every revision — causing design
    # system degradation (lost colours, typography, layout conventions).
    _is_revision = bool(history_context) and os.path.exists(_artifact_cache_path)
    if _is_revision:
        try:
            with open(_artifact_cache_path, "r", encoding="utf-8") as _fh:
                _prev_html = _fh.read()
            # Cap at ~32 KB (~8 K tokens at 4 chars/token).
            # qwen3-coder:30b has 32 K context; reserving ~8 K for input HTML
            # leaves ~24 K for system prompt + revision request + generated output.
            if len(_prev_html) > 32_000:
                _prev_html = _prev_html[:32_000] + "\n<!-- [truncated for context length] -->"
            final_input = (
                f"CURRENT DESIGN (modify this — do not start from scratch):\n"
                f"```html\n{_prev_html}\n```\n\n"
                f"REVISION REQUEST:\n{final_input}"
            )
            yield {"type": "log", "content": f"[DesignStudio] Revision mode — injecting previous artifact ({len(_prev_html)} chars)"}
        except Exception as _re_err:
            logger.warning("[DesignStudio] Could not load previous artifact for revision: %s", _re_err)
    elif history_context:
        # Fallback: no cached artifact but there is history — surface it so the model
        # at least knows what was requested before.
        final_input = f"{history_context}\n\n{final_input}"

    full_output = ""
    try:
        yield {"type": "status", "content": "🎨 Design Studio: Generating design..."}
        yield from pre_lock_status_events("text", resolved_model)

        import requests as _req
        from config import get_ollama_options

        _messages = [
            {"role": "system",    "content": skill_sys_prompt},
            {"role": "user",      "content": final_input},
            # ── Assistant prefill ──────────────────────────────────────────────
            # Injecting the start of the assistant turn forces the model to
            # continue from here rather than producing explanation text first.
            # The model cannot write preamble because the response has already
            # begun as valid HTML.
            {"role": "assistant", "content": "<!DOCTYPE html>\n<html lang=\"en\">"},
        ]
        _opts = get_ollama_options(resolved_model)

        with _langfuse_span(
            "design_generation", "DesignStudio", resolved_model, final_input,
            langfuse=langfuse, use_langfuse=use_langfuse,
        ) as span_result:
            with request_lock(context="text"):
                yield _emit_stream_mode("responding")
                _resp = _req.post(
                    f"{resolved_host}/api/chat",
                    json={
                        "model": resolved_model,
                        "messages": _messages,
                        "stream": True,
                        "options": _opts,
                    },
                    stream=True,
                    timeout=300,
                )
                _resp.raise_for_status()
                # Prepend the prefill we injected so parse_artifact_html sees a
                # complete document from the very first character.
                full_output = "<!DOCTYPE html>\n<html lang=\"en\">"
                import json as _json
                for _line in _resp.iter_lines():
                    if not _line:
                        continue
                    try:
                        _evt = _json.loads(_line)
                    except Exception:
                        continue
                    _token = _evt.get("message", {}).get("content", "")
                    if _token:
                        full_output += _token
                    if _evt.get("done"):
                        break
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

    # Update session artifact cache — subsequent revisions in this session will
    # read this file and inject it as the "current design to revise."
    try:
        with open(_artifact_cache_path, "w", encoding="utf-8") as _ch:
            _ch.write(html_content)
    except Exception as _ce:
        logger.warning("[DesignStudio] Could not update artifact cache: %s", _ce)

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
    yield {"type": "response", "content": "Design ready."}
    _score_trace(
        lf_trace, langfuse, 0.9,
        output=f"design_artifact:{filename}",
        use_langfuse=use_langfuse,
    )
