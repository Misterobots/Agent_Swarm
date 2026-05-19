"""handlers/design.py — DESIGN Studio intent handler (OpenDesign client)."""

import logging
import os
import time

from metrics import AGENT_STATE, WORKFLOW_STEPS
from handlers.base import _emit_stream_mode, _emit_turn_metadata, _score_trace

logger = logging.getLogger("Router")


def handle_design(user_input: str, ctx: dict):
    """Generator — route to OpenDesign client and stream back HTML artifact."""
    turn_id = ctx["turn_id"]
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    yield _emit_turn_metadata(turn_id, "Design Studio", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    yield {"type": "status", "content": "🎨 Design Studio: Preparing..."}
    AGENT_STATE.labels(agent_name="DesignStudio").set(2)

    try:
        from specialized.open_design_client import OpenDesignClient

        od = OpenDesignClient()

        _dl = user_input.lower()
        if any(kw in _dl for kw in ["deck", "slide", "ppt", "presentation"]):
            skill_id = "guizang-ppt"
        elif any(kw in _dl for kw in ["dashboard", "analytics", "metrics"]):
            skill_id = "dashboard"
        elif any(kw in _dl for kw in ["landing", "saas", "marketing page"]):
            skill_id = "saas-landing"
        elif any(kw in _dl for kw in ["mobile", "ios", "android", "app screen"]):
            skill_id = "mobile-app"
        else:
            skill_id = "web-prototype"

        yield {"type": "log", "content": f"[DesignStudio] Skill: {skill_id}"}

        yield {"type": "status", "content": "🎨 Design Studio: Creating project..."}
        project = od.create_project(
            name=f"design-{int(time.time())}",
            skill_id=skill_id,
        )
        project_id = project["project"]["id"]
        yield {"type": "log", "content": f"[DesignStudio] Project: {project_id}"}

        yield {"type": "status", "content": "🎨 Design Studio: Running design agent..."}
        run_resp = od.start_run(
            project_id=project_id,
            message=user_input,
            skill_id=skill_id,
        )
        run_id = run_resp["runId"]
        yield {"type": "log", "content": f"[DesignStudio] Run: {run_id}"}

        html_content = None
        artifact_id = None
        for art_event in od.stream_run(run_id):
            if art_event["type"] == "artifact:end":
                html_content = art_event["fullContent"]
                artifact_id = art_event["identifier"]

        if not html_content:
            yield {"type": "error", "content": "Design Studio: No artifact generated."}
            logger.error("[DesignStudio] No artifact generated for run %s", run_id)
            return

        delivery_dir = "/workspace/delivered_artifacts"
        os.makedirs(delivery_dir, exist_ok=True)
        filename = f"design_{project_id}.html"
        delivery_path = os.path.join(delivery_dir, filename)
        with open(delivery_path, "w", encoding="utf-8") as fh:
            fh.write(html_content)
        yield {"type": "log", "content": f"[DesignStudio] Saved: {filename}"}

        AGENT_STATE.labels(agent_name="DesignStudio").set(1)
        WORKFLOW_STEPS.labels(status="success", agent_type="DesignStudio").inc()

        yield {
            "type": "design_artifact",
            "content": {
                "html": html_content,
                "project_id": project_id,
                "project_url": "http://192.168.2.101:17573",
                "filename": filename,
                "skill": skill_id,
            },
        }
        yield {"type": "response", "content": f"✨ Design created! [Open in Design Studio](http://192.168.2.101:17573)"}
        _score_trace(lf_trace, langfuse, 0.9, output=f"design_artifact:{filename}", use_langfuse=use_langfuse)

    except Exception as e:
        AGENT_STATE.labels(agent_name="DesignStudio").set(1)
        WORKFLOW_STEPS.labels(status="error", agent_type="DesignStudio").inc()
        logger.error("[DesignStudio] Exception: %s", e, exc_info=True)
        yield {"type": "error", "content": f"Design Studio failed: {e}"}
        yield {"type": "log", "content": f"[DesignStudio] Exception: {e}"}
