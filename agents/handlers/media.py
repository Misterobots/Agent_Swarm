"""handlers/media.py — 3D and ACTION_FIGURE intent handlers."""

import logging
import re

from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, pre_lock_status_events

logger = logging.getLogger("Router")


def handle_3d(user_input: str, ctx: dict):
    """Generator — concept art → 3D forge pipeline."""
    yield {"type": "status", "content": "🔮 Router: Detected 3D Generation Request."}
    yield {"type": "status", "content": "🎨 Creative Studio: Generating Concept Art..."}
    AGENT_STATE.labels(agent_name="CreativeStudio").set(2)

    from specialized.image_gen import generate_image

    concept_prompt = f"Concept art for 3d modeling, neutral background: {user_input}"
    yield {"type": "log", "content": f"[CreativeStudio] Prompt Optimized: '{concept_prompt}'"}

    try:
        # Fix 3+5: emit GPU zone/queue status BEFORE potentially blocking on the lock
        yield from pre_lock_status_events("image")
        with request_lock(context="image"):
            img_result = generate_image(concept_prompt)
        yield {"type": "status", "content": f"🖼️ {img_result}"}
        yield {"type": "log", "content": f"[CreativeStudio] Output: {img_result}"}
        AGENT_STATE.labels(agent_name="CreativeStudio").set(1)

        match = re.search(r"Generated Image: ([\w\.-]+)", img_result)

        if match:
            filename = match.group(1)
            full_image_path = f"/app/comfy_io/output/{filename}"

            yield {"type": "status", "content": "⚒️ Creature Forge: Hammering Geometry..."}
            AGENT_STATE.labels(agent_name="Forge").set(2)

            from specialized.forge_agent import generate_3d_model

            yield {"type": "log", "content": f"[Forge] Processing: {full_image_path} (High-Res Mode)"}
            with request_lock(context="image"):
                forge_result = generate_3d_model(full_image_path)
            AGENT_STATE.labels(agent_name="Forge").set(1)

            yield {
                "type": "artifact",
                "content": {
                    "type": "3d_model",
                    "path": f"{filename}.glb",
                    "name": f"Creature_{filename}",
                },
            }
            yield {"type": "response", "content": forge_result}
            WORKFLOW_STEPS.labels(status="success", agent_type="Forge").inc()
        else:
            yield {"type": "error", "content": f"Failed to parse image filename from: {img_result}"}
            WORKFLOW_STEPS.labels(status="error", agent_type="CreativeStudio").inc()

    except Exception as e:
        yield {"type": "error", "content": f"Concept Generation Failed: {e}"}
        yield {"type": "log", "content": f"[Exception] {e}"}


def handle_action_figure(user_input: str, ctx: dict):
    """Generator — T-pose concept art → action figure mesh pipeline."""
    yield {"type": "status", "content": "🦾 Router: Detected Action Figure Request."}
    yield {"type": "status", "content": "🎨 Action Figure Forge: Generating T-Pose Concept Art..."}
    AGENT_STATE.labels(agent_name="ActionFigureForge").set(2)

    from specialized.image_gen import generate_image

    concept_prompt = (
        f"T-pose character concept art for 3D action figure, "
        f"full body front view, neutral gray background, "
        f"arms extended to sides, symmetrical pose, "
        f"clean silhouette for 3D modeling: {user_input}"
    )
    yield {"type": "log", "content": f"[ActionFigureForge] Prompt: '{concept_prompt}'"}

    try:
        # Fix 3+5: emit GPU zone/queue status BEFORE potentially blocking on the lock
        yield from pre_lock_status_events("image")
        with request_lock(context="image"):
            img_result = generate_image(concept_prompt)
        yield {"type": "status", "content": f"🖼️ {img_result}"}
        yield {"type": "log", "content": f"[ActionFigureForge] Concept Art: {img_result}"}

        match = re.search(r"Generated Image: ([\w\.-]+)", img_result)

        if match:
            filename = match.group(1)
            full_image_path = f"/app/comfy_io/output/{filename}"

            yield {"type": "status", "content": "⚒️ Action Figure Forge: Generating mesh & adding ball-socket joints..."}

            from specialized.action_figure_agent import generate_action_figure

            yield {"type": "log", "content": f"[ActionFigureForge] Processing: {full_image_path}"}
            with request_lock(context="image"):
                figure_result = generate_action_figure(full_image_path)
            AGENT_STATE.labels(agent_name="ActionFigureForge").set(1)

            yield {
                "type": "artifact",
                "content": {
                    "type": "action_figure",
                    "path": "action_figures/",
                    "name": f"ActionFigure_{filename}",
                },
            }
            yield {"type": "response", "content": figure_result}
            WORKFLOW_STEPS.labels(status="success", agent_type="ActionFigureForge").inc()
        else:
            yield {"type": "error", "content": f"Failed to parse image filename from: {img_result}"}
            WORKFLOW_STEPS.labels(status="error", agent_type="ActionFigureForge").inc()

    except Exception as e:
        yield {"type": "error", "content": f"Action Figure Generation Failed: {e}"}
        yield {"type": "log", "content": f"[Exception] {e}"}
