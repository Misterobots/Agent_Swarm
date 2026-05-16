"""handlers/image.py — IMAGE intent handler (Art Director + QC + delivery)."""

import logging
import os
import re
import shutil

from metrics import AGENT_STATE, WORKFLOW_STEPS

from handlers.base import _score_trace

logger = logging.getLogger("Router")


def _deliver_image(filename: str, source_path: str, ctx: dict):
    """
    Copy an image from source_path to /workspace/delivered_artifacts and
    yield the appropriate events (QC → media_attachment → response).
    """
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]
    user_input = ctx.get("_image_user_input", "")

    # QC inspection (non-blocking)
    yield {"type": "status", "content": "🔍 Quality Control: Inspecting image..."}
    try:
        from specialized.quality_control_agent import inspect_generated_image
        qc_result = inspect_generated_image(source_path, user_input)
        overall_score = qc_result.get("overall_score", 0.0)
        passed = qc_result.get("passed", False)
        issues = qc_result.get("issues", [])
        logger.info("[QualityControl] Score: %.1f/10 | Passed: %s", overall_score, passed)
        if not passed:
            issue_text = (
                ", ".join(issues)
                if issues and issues[0].lower() != "none"
                else "Minor quality concerns"
            )
            yield {"type": "log", "content": f"⚠️ Quality Check: {overall_score:.1f}/10 - {issue_text}"}
        else:
            yield {"type": "log", "content": f"✓ Quality Check: {overall_score:.1f}/10 - Excellent!"}
    except Exception as qc_err:
        logger.warning("[QualityControl] Inspection failed, proceeding: %s", qc_err)
        yield {"type": "log", "content": "⚠️ Quality inspection unavailable, proceeding..."}

    # Delivery
    delivery_dir = "/workspace/delivered_artifacts"
    os.makedirs(delivery_dir, exist_ok=True)
    delivery_path = os.path.join(delivery_dir, filename)

    try:
        if os.path.exists(source_path):
            shutil.copy2(source_path, delivery_path)
            logger.info("[CreativeStudio] Copied image to delivered_artifacts: %s", filename)

            from utils.media_metadata import extract_media_metadata
            media_meta = extract_media_metadata(
                filename,
                base_path=delivery_dir,
                url_prefix="/api/backend/delivered_artifacts",
            )
            if media_meta:
                yield {"type": "media_attachment", "content": media_meta}
                yield {"type": "response", "content": f"✨ Image generated: {filename}"}
                WORKFLOW_STEPS.labels(status="success", agent_type="CreativeStudio").inc()
            else:
                yield {"type": "error", "content": "Failed to create media metadata"}
        else:
            logger.error("[CreativeStudio] Source image not found: %s", source_path)
            yield {"type": "error", "content": "Image file not found after generation"}
    except Exception as e:
        logger.error("[CreativeStudio] Failed to deliver image: %s", e)
        yield {"type": "error", "content": f"Image delivery failed: {e}"}


def handle_image(user_input: str, ctx: dict):
    """Generator — Art Director review then image generation with QC + delivery."""
    turn_id = ctx.get("turn_id", "")
    uid = ctx.get("uid")
    lf_trace = ctx["lf_trace"]
    langfuse = ctx["langfuse"]
    use_langfuse = ctx["use_langfuse"]

    from church import _resolve_model_for_intent
    from config import ARCHITECT_MODEL
    from role_model_resolver import get_model_for_role

    yield {"type": "status", "content": "🎨 Art Director: Reviewing your vision..."}
    AGENT_STATE.labels(agent_name="ArtDirector").set(2)

    MODEL_NAME = get_model_for_role(uid, "architect", default=ARCHITECT_MODEL)
    MODEL_NAME = _resolve_model_for_intent("IMAGE", MODEL_NAME)

    # Deterministic style/setting keyword check (no LLM needed)
    prompt_lower = user_input.lower()

    has_style = any(kw in prompt_lower for kw in [
        "photo", "photograph", "realistic", "hyperrealistic", "photorealistic",
        "painting", "oil painting", "watercolor", "acrylic", "gouache",
        "impressionist", "expressionist", "abstract",
        "digital art", "digital painting", "illustration", "concept art",
        "vector", "flat design", "isometric", "low poly", "pixel art",
        "sketch", "drawing", "pencil", "charcoal", "ink", "pastel", "crayon",
        "3d render", "3d", "render", "cgi", "blender", "octane", "unreal engine",
        "anime", "manga", "cartoon", "comic", "disney", "pixar", "chibi",
        "vintage", "retro", "noir", "cinematic", "fantasy", "surreal",
        "portrait", "landscape", "minimalist", "sticker",
    ])

    has_setting = any(kw in prompt_lower for kw in [
        "background", "setting", "location", "scene", "environment",
        "forest", "jungle", "woods", "park",
        "city", "urban", "street", "alley", "skyline",
        "ocean", "sea", "beach", "lake", "river", "waterfall",
        "mountain", "desert", "field", "meadow", "valley",
        "space", "galaxy", "cosmos", "planet",
        "studio", "indoors", "outdoors", "room", "kitchen", "bedroom",
        "castle", "temple", "library", "lab", "dungeon",
        "white background", "black background", "gradient",
        " in a ", " in the ", " on a ", " on the ",
        " at the ", " at a ", " inside ", " outside ",
        " under a ", " under the ", " above the ",
        " beside ", " near the ", " near a ",
        " surrounded by", " against a ", " against the ",
    ])

    if not has_style or not has_setting:
        yield {"type": "log", "content": "[Art Director] Applying cinematic defaults — generating now."}

    yield {"type": "log", "content": "[Art Director] Prompt approved for Execution."}
    AGENT_STATE.labels(agent_name="ArtDirector").set(1)

    yield {"type": "status", "content": "🎨 Creative Studio: Spinning up..."}
    AGENT_STATE.labels(agent_name="CreativeStudio").set(2)

    from agents.specialized.image_gen import generate_image
    yield {"type": "log", "content": f"[CreativeStudio] Generating: '{user_input}'"}
    response = generate_image(user_input, model_name="auto")

    image_match = re.search(r"Generated Image: ([\w\.-]+)", response)
    if image_match:
        filename = image_match.group(1)
        source_path = os.path.join("/tmp/comfyui_images", filename)
        # Thread _image_user_input into ctx for QC inspection
        ctx["_image_user_input"] = user_input
        yield from _deliver_image(filename, source_path, ctx)
    else:
        yield {"type": "error", "content": f"Could not extract filename from: {response}"}

    AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
    _score_trace(lf_trace, langfuse, 0.9, use_langfuse=use_langfuse)
