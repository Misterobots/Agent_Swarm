"""
Action Figure Agent  (v2 — skeleton-aware)
============================================

Image-to-3D-printable posable action figure pipeline.

Pipeline:
  1. Generate base 3D mesh from input image via ComfyUI (TripoSG)
  2. Repair mesh (fill holes, fix normals, merge vertices)
  3. Detect humanoid skeleton from cross-section analysis
  4. Cut mesh into 11 body parts at detected joint positions
  5. Attach parametric ball-socket joints to each cut surface
  6. Validate printability and export STL parts + manifest

Joint system:
  Ball-socket at every joint — sphere on a stem (parent side),
  hemispherical cavity with snap-fit retention lip (child side),
  reinforcement housing collar around each socket.
"""

import json
import os
import uuid
import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
MODEL_NAME = "qwen2.5-coder:14b"

# Directories
COMFY_INPUT_DIR = "/app/comfy_io/input"
COMFY_OUTPUT_DIR = "/app/comfy_io/output"
TEMPLATE_DIR = "/app/agents/templates"
ACTION_FIGURE_OUTPUT_DIR = "/app/comfy_io/output/action_figures"

# Defaults
TARGET_HEIGHT_MM = 150.0
JOINT_CLEARANCE_MM = 0.3


# ============================================================================
# BODY PART TOPOLOGY
# ============================================================================
#
# Each body part is defined by which joints bound it and the part's role
# at that joint:
#   'parent' → this part has the BALL, keeps the opposite side of joint normal
#   'child'  → this part has the SOCKET, keeps the same side as joint normal

BODY_PARTS: Dict[str, List[tuple]] = {
    "head":            [("neck", "child")],
    "torso":           [("neck", "parent"), ("waist", "parent"),
                        ("left_shoulder", "parent"), ("right_shoulder", "parent")],
    "pelvis":          [("waist", "child"),
                        ("left_hip", "parent"), ("right_hip", "parent")],
    "left_upper_arm":  [("left_shoulder", "child"), ("left_elbow", "parent")],
    "left_forearm":    [("left_elbow", "child")],
    "right_upper_arm": [("right_shoulder", "child"), ("right_elbow", "parent")],
    "right_forearm":   [("right_elbow", "child")],
    "left_upper_leg":  [("left_hip", "child"), ("left_knee", "parent")],
    "left_lower_leg":  [("left_knee", "child")],
    "right_upper_leg": [("right_hip", "child"), ("right_knee", "parent")],
    "right_lower_leg": [("right_knee", "child")],
}


# ============================================================================
# MESH HELPERS
# ============================================================================

def _ensure_output_dir():
    os.makedirs(ACTION_FIGURE_OUTPUT_DIR, exist_ok=True)


def _center_mesh(mesh):
    """Center on XY origin, bottom at Z=0."""
    bounds = mesh.bounds
    cx = (bounds[0][0] + bounds[1][0]) / 2
    cy = (bounds[0][1] + bounds[1][1]) / 2
    mesh.apply_translation([-cx, -cy, -bounds[0][2]])
    return mesh


def _scale_mesh_to_height(mesh, target_mm: float):
    """Scale mesh so bounding-box height = target_mm."""
    bounds = mesh.bounds
    h = bounds[1][2] - bounds[0][2]
    if h <= 0:
        return mesh
    factor = target_mm / h
    mesh.apply_scale(factor)
    logger.info(f"[ActionFigure] Scaled {factor:.3f}x → {target_mm}mm height")
    return mesh


def _load_mesh(mesh_path: str):
    """Load a GLB/OBJ and flatten to a single Trimesh."""
    import trimesh

    scene = trimesh.load(mesh_path, force="scene")
    if isinstance(scene, trimesh.Scene):
        meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No geometry in {mesh_path}")
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    elif isinstance(scene, trimesh.Trimesh):
        mesh = scene
    else:
        raise ValueError(f"Unexpected type from trimesh.load: {type(scene)}")

    return mesh


# ============================================================================
# SEGMENTATION — CUT MESH AT SKELETON JOINTS
# ============================================================================

def extract_body_part(mesh, part_name: str, skeleton: Dict):
    """
    Extract one body part by sequentially cutting at each adjacent joint.

    For each joint bounding this part:
      - parent role → keep opposite side of joint normal (toward body center)
      - child role  → keep same side as joint normal (away from body center)
    """
    joints = skeleton["joints"]
    result = mesh.copy()

    for joint_name, role in BODY_PARTS[part_name]:
        joint = joints[joint_name]
        pos = joint["position"]
        normal = joint["normal"]

        # Determine which side of the plane to keep
        if role == "parent":
            cut_normal = -normal  # keep opposite side
        else:
            cut_normal = normal   # keep same side

        try:
            sliced = result.slice_plane(pos, cut_normal, cap=True)
            if sliced is not None and len(sliced.faces) > 5:
                result = sliced
            else:
                logger.warning(
                    f"[Segment] {part_name}/{joint_name}: cut produced "
                    f"{len(sliced.faces) if sliced else 0} faces, skipping"
                )
        except Exception as e:
            logger.warning(f"[Segment] {part_name}/{joint_name} cut failed: {e}")

    return result


# ============================================================================
# JOINT ATTACHMENT
# ============================================================================

def attach_joints(part_mesh, part_name: str, skeleton: Dict, clearance: float):
    """
    Add ball-socket joint geometry to a body part.

    Parent side → ball protrudes in joint-normal direction
    Child side  → socket cavity carved opposite to joint normal,
                  with reinforcement housing
    """
    import trimesh
    from specialized.joint_library import (
        BallSocketJoint, orient_joint_geometry, safe_boolean,
    )

    joints = skeleton["joints"]
    result = part_mesh

    for joint_name, role in BODY_PARTS[part_name]:
        joint = joints[joint_name]
        pos = np.array(joint["position"])
        normal = np.array(joint["normal"])
        radius = joint["radius"]

        bsj = BallSocketJoint(ball_radius=radius, clearance=clearance)

        if role == "parent":
            # Ball protrudes toward child (in joint normal direction)
            ball = bsj.create_ball_assembly()
            orient_joint_geometry(ball, pos, normal)
            result = safe_boolean("union", [result, ball], f"{part_name}/{joint_name}/ball")

        else:
            # Socket faces the parent (opposite to joint normal)
            socket_dir = -normal

            # Add reinforcement housing first
            housing = bsj.create_socket_housing()
            orient_joint_geometry(housing, pos, socket_dir)
            result = safe_boolean("union", [result, housing], f"{part_name}/{joint_name}/housing")

            # Carve socket cavity
            void = bsj.create_socket_void()
            orient_joint_geometry(void, pos, socket_dir)
            result = safe_boolean("difference", [result, void], f"{part_name}/{joint_name}/socket")

    return result


# ============================================================================
# MAIN SEGMENTATION PIPELINE
# ============================================================================

def segment_and_joint(
    mesh_path: str,
    output_prefix: str = "figure",
    target_height: float = TARGET_HEIGHT_MM,
    clearance: float = JOINT_CLEARANCE_MM,
) -> Dict[str, str]:
    """
    Full segmentation pipeline: load → repair → detect skeleton →
    cut into 11 parts → attach joints → validate → export STL.

    Returns dict mapping part names to output file paths.
    """
    import trimesh
    from specialized.mesh_utils import repair_mesh, detect_skeleton, validate_printability

    # ── 1. Load & prepare ──
    mesh = _load_mesh(mesh_path)
    mesh = repair_mesh(mesh)
    mesh = _center_mesh(mesh)
    mesh = _scale_mesh_to_height(mesh, target_height)

    logger.info(
        f"[ActionFigure] Prepared mesh: {len(mesh.vertices)} verts, "
        f"{len(mesh.faces)} faces, bounds {mesh.bounds.tolist()}"
    )

    # ── 2. Detect skeleton ──
    skeleton = detect_skeleton(mesh)
    confidence = skeleton["confidence"]
    features = skeleton.get("detected_features", {})
    logger.info(
        f"[ActionFigure] Skeleton confidence={confidence:.2f}, "
        f"features={features}"
    )

    # ── 3. Cut & joint each body part ──
    _ensure_output_dir()
    output_files: Dict[str, str] = {}
    part_meshes: Dict[str, trimesh.Trimesh] = {}
    skipped = []

    for part_name in BODY_PARTS:
        logger.info(f"[ActionFigure] Extracting: {part_name}")
        part = extract_body_part(mesh, part_name, skeleton)

        if len(part.faces) < 20:
            logger.warning(
                f"[ActionFigure] {part_name}: only {len(part.faces)} faces — skipping"
            )
            skipped.append(part_name)
            continue

        # Attach joint geometry
        part = attach_joints(part, part_name, skeleton, clearance)
        part_meshes[part_name] = part

        # Export STL
        out_path = os.path.join(
            ACTION_FIGURE_OUTPUT_DIR, f"{output_prefix}_{part_name}.stl"
        )
        part.export(out_path, file_type="stl")
        output_files[part_name] = out_path
        logger.info(f"[ActionFigure] Exported: {out_path} ({len(part.faces)} faces)")

    # ── 4. Validate printability ──
    warnings = validate_printability(part_meshes)
    for w in warnings:
        logger.warning(f"[PrintCheck] {w}")

    # ── 5. Write manifest ──
    manifest = {
        "figure_name": output_prefix,
        "target_height_mm": target_height,
        "joint_clearance_mm": clearance,
        "joint_type": "ball_socket",
        "skeleton_confidence": confidence,
        "skeleton_features": {k: float(v) if isinstance(v, (int, float, np.floating)) else v
                              for k, v in features.items()},
        "parts": {
            name: {
                "path": path,
                "faces": len(part_meshes[name].faces),
                "joints": [
                    {"name": jn, "role": jr}
                    for jn, jr in BODY_PARTS[name]
                ],
            }
            for name, path in output_files.items()
        },
        "skipped_parts": skipped,
        "print_warnings": warnings,
        "assembly_notes": (
            f"11-part posable action figure ({target_height}mm tall). "
            f"All joints are ball-socket with {clearance}mm clearance (FDM). "
            "Reduce clearance to 0.15mm for resin. "
            "Ball joints snap-fit into sockets — press firmly to seat."
        ),
    }
    manifest_path = os.path.join(
        ACTION_FIGURE_OUTPUT_DIR, f"{output_prefix}_manifest.json"
    )
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    output_files["_manifest"] = manifest_path

    return output_files


# ============================================================================
# COMFYUI 3D GENERATION (reuses forge pipeline)
# ============================================================================

def _generate_base_mesh(
    image_path: str, workflow_name: str = "workflow_triposg.json",
) -> str:
    """
    Generate base 3D mesh from image via ComfyUI / TripoSG.
    Returns path to generated GLB, or error string.
    """
    from specialized.forge_agent import generate_3d_model
    return generate_3d_model(image_path, workflow_name)


# ============================================================================
# FULL PIPELINE ENTRY POINT
# ============================================================================

def generate_action_figure(
    image_path: str,
    workflow_name: str = "workflow_triposg.json",
    figure_name: Optional[str] = None,
    target_height: float = TARGET_HEIGHT_MM,
    clearance: float = JOINT_CLEARANCE_MM,
) -> str:
    """
    Full image → posable action figure pipeline.

    1. Generate base 3D mesh from concept art via TripoSG
    2. Detect skeleton, segment into body parts
    3. Attach ball-socket joints
    4. Export print-ready STL parts

    Args:
        image_path: Path to source 2D image
        workflow_name: ComfyUI workflow template name
        figure_name: Filename prefix (auto-generated if None)
        target_height: Figure height in mm
        clearance: Joint clearance in mm

    Returns:
        Summary string with part counts and paths, or error message.
    """
    if figure_name is None:
        figure_name = f"action_fig_{uuid.uuid4().hex[:8]}"

    logger.info(f"[ActionFigure] Pipeline start: {image_path}")

    # Step 1: Generate base mesh
    logger.info("[ActionFigure] Step 1/3: Generating base 3D mesh via TripoSG...")
    mesh_result = _generate_base_mesh(image_path, workflow_name)

    if mesh_result.startswith("Error"):
        return f"Action Figure Generation Failed (mesh step): {mesh_result}"

    # Extract path from "3D Model Generated Successfully: /path/to/file.glb"
    if ":" in mesh_result:
        mesh_path = mesh_result.split(":", 1)[1].strip()
    else:
        return f"Action Figure Generation Failed: could not parse mesh path from: {mesh_result}"

    if not os.path.exists(mesh_path):
        return f"Action Figure Generation Failed: mesh not found at {mesh_path}"

    # Step 2 & 3: Segment, joint, export
    logger.info("[ActionFigure] Step 2/3: Skeleton detection, segmentation, joint attachment...")
    try:
        output_files = segment_and_joint(
            mesh_path,
            output_prefix=figure_name,
            target_height=target_height,
            clearance=clearance,
        )
    except Exception as e:
        logger.error(f"[ActionFigure] Segmentation failed: {e}", exc_info=True)
        return f"Action Figure Generation Failed (segmentation): {e}"

    part_count = len([k for k in output_files if not k.startswith("_")])
    manifest = output_files.get("_manifest", "unknown")

    logger.info(f"[ActionFigure] Pipeline complete: {part_count} parts")

    return (
        f"Action Figure Generated Successfully: {part_count} posable parts "
        f"with ball-socket joints.\n"
        f"Parts directory: {ACTION_FIGURE_OUTPUT_DIR}\n"
        f"Manifest: {manifest}\n"
        f"Figure name: {figure_name}"
    )


# ============================================================================
# PHIDATA AGENT WRAPPER
# ============================================================================

def get_action_figure_agent():
    from phi.agent import Agent
    from phi.model.ollama import Ollama

    return Agent(
        name="Action Figure Forge",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description=(
            "I convert images into 3D-printable posable action figures. "
            "I generate a base 3D mesh, detect the skeleton, segment into "
            "body parts, and add ball-socket joints for full poseability."
        ),
        instructions=(
            "Use `generate_action_figure` to convert a 2D image into print-ready STL files. "
            "CRITICAL: 3D generation will FAIL and create distorted monsters if the input image "
            "contains multiple characters (e.g., a character sheet) or complex backgrounds. "
            "BEFORE calling `generate_action_figure`, you MUST show the image path or display "
            "the image to the user and ask them to confirm it contains exactly ONE character in "
            "a neutral standing pose on a clean background. Proceed ONLY after the user confirms.\n"
            "The pipeline auto-detects the humanoid skeleton and places ball-socket joints. You can "
            "specify `workflow_name` as `workflow_hunyuan_paint.json` for higher accuracy if desired."
        ),
        tools=[generate_action_figure],
        show_tool_calls=True,
    )


if __name__ == "__main__":
    agent = get_action_figure_agent()
    agent.print_response("Status check")
