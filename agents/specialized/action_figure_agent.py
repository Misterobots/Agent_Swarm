"""
Action Figure Agent
====================

Image-to-3D-printable posable action figure pipeline.

Pipeline:
  1. Generate base 3D mesh from input image via ComfyUI (TripoSG)
  2. Segment mesh into body parts at joint locations
  3. Add ball-and-socket joint geometry at each cut plane
  4. Export individual parts as print-ready STL files

Joint system uses ball-socket design:
  - Ball (male): sphere protruding from the parent part
  - Socket (female): hollow hemisphere recessed into the child part
  - Clearance gap for FDM/resin tolerance
"""

import json
import os
import time
import uuid
import shutil
import logging
import math
import requests
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
MODEL_NAME = "qwen2.5-coder:14b"

# Directories (Mapped Volumes)
COMFY_INPUT_DIR = "/app/comfy_io/input"
COMFY_OUTPUT_DIR = "/app/comfy_io/output"
TEMPLATE_DIR = "/app/agents/templates"
ACTION_FIGURE_OUTPUT_DIR = "/app/comfy_io/output/action_figures"

# ============================================================================
# JOINT DEFINITIONS
# ============================================================================

# Default joint locations as normalized height ratios (0 = bottom, 1 = top)
# and the axis perpendicular to the cut plane.
# These are starting estimates; the LLM refines them per-model.

DEFAULT_JOINT_PLAN = {
    "neck":             {"height_ratio": 0.85, "axis": "z", "ball_radius": 3.5},
    "left_shoulder":    {"height_ratio": 0.78, "axis": "x", "ball_radius": 4.0, "side": "left"},
    "right_shoulder":   {"height_ratio": 0.78, "axis": "x", "ball_radius": 4.0, "side": "right"},
    "left_elbow":       {"height_ratio": 0.60, "axis": "x", "ball_radius": 3.0, "side": "left"},
    "right_elbow":      {"height_ratio": 0.60, "axis": "x", "ball_radius": 3.0, "side": "right"},
    "left_wrist":       {"height_ratio": 0.45, "axis": "x", "ball_radius": 2.5, "side": "left"},
    "right_wrist":      {"height_ratio": 0.45, "axis": "x", "ball_radius": 2.5, "side": "right"},
    "waist":            {"height_ratio": 0.52, "axis": "z", "ball_radius": 5.0},
    "left_hip":         {"height_ratio": 0.45, "axis": "z", "ball_radius": 4.5, "side": "left"},
    "right_hip":        {"height_ratio": 0.45, "axis": "z", "ball_radius": 4.5, "side": "right"},
    "left_knee":        {"height_ratio": 0.25, "axis": "x", "ball_radius": 3.5, "side": "left"},
    "right_knee":       {"height_ratio": 0.25, "axis": "x", "ball_radius": 3.5, "side": "right"},
}

# Print tolerance (mm gap between ball and socket for clearance)
JOINT_CLEARANCE_MM = 0.3

# Target figure height in mm (scales the mesh)
TARGET_HEIGHT_MM = 150.0


# ============================================================================
# MESH PROCESSING UTILITIES
# ============================================================================

def _ensure_output_dir():
    """Create output directory for action figure parts."""
    os.makedirs(ACTION_FIGURE_OUTPUT_DIR, exist_ok=True)


def _scale_mesh_to_height(mesh, target_height_mm: float):
    """Scale a trimesh object so its bounding box height matches target."""
    import trimesh
    bounds = mesh.bounds
    current_height = bounds[1][2] - bounds[0][2]  # Z-axis height
    if current_height <= 0:
        logger.warning("[ActionFigure] Mesh has zero height, skipping scale")
        return mesh
    scale_factor = target_height_mm / current_height
    mesh.apply_scale(scale_factor)
    logger.info(f"[ActionFigure] Scaled mesh by {scale_factor:.3f}x to {target_height_mm}mm height")
    return mesh


def _center_mesh(mesh):
    """Center mesh at origin on XY, with bottom at Z=0."""
    import trimesh
    bounds = mesh.bounds
    center_x = (bounds[0][0] + bounds[1][0]) / 2
    center_y = (bounds[0][1] + bounds[1][1]) / 2
    min_z = bounds[0][2]
    mesh.apply_translation([-center_x, -center_y, -min_z])
    return mesh


def _create_ball_joint(center: list, radius: float, socket: bool = False) -> "trimesh.Trimesh":
    """
    Create a ball or socket joint primitive.

    Args:
        center: [x, y, z] position
        radius: Ball radius in mm
        socket: If True, creates a socket (hollow sphere) instead of a ball

    Returns:
        trimesh sphere primitive
    """
    import trimesh

    if socket:
        # Socket: slightly larger sphere (with clearance) to be subtracted
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=radius + JOINT_CLEARANCE_MM)
    else:
        # Ball: solid sphere at nominal radius
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=radius)

    sphere.apply_translation(center)
    return sphere


def _create_peg(center: list, radius: float, length: float, axis: str = "z") -> "trimesh.Trimesh":
    """Create a cylindrical peg for the ball stem."""
    import trimesh
    import numpy as np

    cylinder = trimesh.creation.cylinder(radius=radius * 0.4, height=length, sections=32)

    # Orient cylinder along the correct axis
    if axis == "x":
        rotation = trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0])
        cylinder.apply_transform(rotation)
    elif axis == "y":
        rotation = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
        cylinder.apply_transform(rotation)
    # z is default (no rotation needed)

    cylinder.apply_translation(center)
    return cylinder


def _split_mesh_at_plane(mesh, origin: list, normal: list) -> Tuple:
    """
    Split a mesh into two halves using a plane.

    Returns:
        (upper_half, lower_half) trimesh objects, either may be None if split fails
    """
    import trimesh
    import numpy as np

    try:
        # trimesh.intersections.slice_mesh_plane returns the portion ABOVE the plane
        upper = mesh.slice_plane(origin, normal)
        lower = mesh.slice_plane(origin, [-n for n in normal])
        return upper, lower
    except Exception as e:
        logger.warning(f"[ActionFigure] Plane split failed: {e}")
        return None, None


def segment_and_joint(mesh_path: str, joint_plan: Optional[Dict] = None,
                      output_prefix: str = "figure") -> Dict[str, str]:
    """
    Main segmentation pipeline.

    Takes a monolithic 3D mesh and produces individual STL parts
    with ball-socket joints for posable assembly.

    Args:
        mesh_path: Path to input GLB/OBJ mesh
        joint_plan: Joint definitions (uses DEFAULT_JOINT_PLAN if None)
        output_prefix: Filename prefix for output parts

    Returns:
        Dict mapping part names to output file paths
    """
    import trimesh
    import numpy as np

    _ensure_output_dir()

    if joint_plan is None:
        joint_plan = DEFAULT_JOINT_PLAN

    # Load and prepare mesh
    scene = trimesh.load(mesh_path, force="scene")
    if isinstance(scene, trimesh.Scene):
        mesh = scene.to_geometry()
        if isinstance(mesh, trimesh.Scene):
            # Flatten all geometries into one mesh
            meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                raise ValueError(f"No valid geometry found in {mesh_path}")
            mesh = trimesh.util.concatenate(meshes)
    else:
        mesh = scene

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Could not extract mesh from {mesh_path}")

    # Center and scale
    mesh = _center_mesh(mesh)
    mesh = _scale_mesh_to_height(mesh, TARGET_HEIGHT_MM)

    bounds = mesh.bounds
    mesh_height = bounds[1][2] - bounds[0][2]
    mesh_width = bounds[1][0] - bounds[0][0]
    mesh_center_x = (bounds[0][0] + bounds[1][0]) / 2

    output_files = {}

    # Sort joints by height ratio (process from top to bottom)
    sorted_joints = sorted(joint_plan.items(), key=lambda x: x[1]["height_ratio"], reverse=True)

    # Track remaining mesh regions for progressive cutting
    # We'll use a simpler approach: cut the full mesh at each joint plane
    # and collect the segments between consecutive cuts.

    # Compute absolute Z heights for horizontal cuts
    z_cuts = []
    for joint_name, joint_def in sorted_joints:
        z = bounds[0][2] + joint_def["height_ratio"] * mesh_height
        z_cuts.append((joint_name, z, joint_def))

    # Sort cuts by Z ascending for sequential slicing
    z_cuts.sort(key=lambda x: x[1])

    # Sequential horizontal slicing to create body segments
    remaining = mesh.copy()
    segments = []

    for i, (joint_name, z_height, joint_def) in enumerate(z_cuts):
        origin = [0, 0, z_height]
        normal = [0, 0, 1]  # Cut plane faces up

        try:
            # below = portion under the cut plane
            below = remaining.slice_plane(origin, [0, 0, -1])
            above = remaining.slice_plane(origin, [0, 0, 1])

            if below is not None and len(below.faces) > 0:
                # For side-specific joints (left/right), further split on X axis
                side = joint_def.get("side")
                if side == "left":
                    left_part = below.slice_plane([mesh_center_x, 0, 0], [-1, 0, 0])
                    if left_part is not None and len(left_part.faces) > 0:
                        segments.append((f"{joint_name}_part", left_part, joint_def))
                    # Keep right side in remaining
                    right_remain = below.slice_plane([mesh_center_x, 0, 0], [1, 0, 0])
                    if right_remain is not None and above is not None:
                        remaining = trimesh.util.concatenate([right_remain, above])
                    elif above is not None:
                        remaining = above
                    continue
                elif side == "right":
                    right_part = below.slice_plane([mesh_center_x, 0, 0], [1, 0, 0])
                    if right_part is not None and len(right_part.faces) > 0:
                        segments.append((f"{joint_name}_part", right_part, joint_def))
                    left_remain = below.slice_plane([mesh_center_x, 0, 0], [-1, 0, 0])
                    if left_remain is not None and above is not None:
                        remaining = trimesh.util.concatenate([left_remain, above])
                    elif above is not None:
                        remaining = above
                    continue

                segments.append((f"{joint_name}_part", below, joint_def))

            if above is not None and len(above.faces) > 0:
                remaining = above
            else:
                break

        except Exception as e:
            logger.warning(f"[ActionFigure] Failed to cut at {joint_name} (z={z_height:.1f}): {e}")
            continue

    # Add the final remaining piece (top of head typically)
    if remaining is not None and len(remaining.faces) > 0:
        segments.append(("head_top", remaining, {"ball_radius": 3.5, "axis": "z"}))

    # Process each segment: add joint geometry and export
    for part_name, part_mesh, joint_def in segments:
        ball_radius = joint_def.get("ball_radius", 3.5)
        part_bounds = part_mesh.bounds

        try:
            # Add ball joint peg on top face of each segment
            top_center = [
                (part_bounds[0][0] + part_bounds[1][0]) / 2,
                (part_bounds[0][1] + part_bounds[1][1]) / 2,
                part_bounds[1][2]
            ]
            ball = _create_ball_joint(top_center, ball_radius, socket=False)
            peg = _create_peg(top_center, ball_radius, ball_radius * 1.5, axis="z")

            # Add socket recess on bottom face
            bottom_center = [
                (part_bounds[0][0] + part_bounds[1][0]) / 2,
                (part_bounds[0][1] + part_bounds[1][1]) / 2,
                part_bounds[0][2]
            ]
            socket = _create_ball_joint(bottom_center, ball_radius, socket=True)

            # Boolean operations: union ball+peg onto top, subtract socket from bottom
            try:
                part_with_ball = trimesh.boolean.union([part_mesh, ball, peg], engine="blender")
                final_part = trimesh.boolean.difference([part_with_ball, socket], engine="blender")
            except Exception:
                # Fallback: try manifold engine or skip booleans
                try:
                    part_with_ball = trimesh.boolean.union([part_mesh, ball, peg], engine="manifold")
                    final_part = trimesh.boolean.difference([part_with_ball, socket], engine="manifold")
                except Exception as bool_err:
                    logger.warning(f"[ActionFigure] Boolean ops failed for {part_name}: {bool_err}, exporting raw segment")
                    final_part = part_mesh

        except Exception as e:
            logger.warning(f"[ActionFigure] Joint geometry failed for {part_name}: {e}")
            final_part = part_mesh

        # Export as STL
        out_path = os.path.join(ACTION_FIGURE_OUTPUT_DIR, f"{output_prefix}_{part_name}.stl")
        final_part.export(out_path, file_type="stl")
        output_files[part_name] = out_path
        logger.info(f"[ActionFigure] Exported: {out_path} ({len(final_part.faces)} faces)")

    # Also export a manifest JSON for the slicer / assembly reference
    manifest = {
        "figure_name": output_prefix,
        "target_height_mm": TARGET_HEIGHT_MM,
        "joint_clearance_mm": JOINT_CLEARANCE_MM,
        "parts": {name: {"path": path, "joint_type": "ball_socket"}
                  for name, path in output_files.items()},
        "assembly_notes": (
            "Print all parts individually. "
            "Ball joints should press-fit into sockets. "
            f"Designed with {JOINT_CLEARANCE_MM}mm clearance for FDM printers. "
            "Reduce clearance to 0.15mm for resin printers."
        )
    }
    manifest_path = os.path.join(ACTION_FIGURE_OUTPUT_DIR, f"{output_prefix}_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    output_files["_manifest"] = manifest_path

    return output_files


# ============================================================================
# COMFYUI 3D GENERATION (reuses forge pipeline)
# ============================================================================

def _generate_base_mesh(image_path: str, workflow_name: str = "workflow_triposg.json") -> str:
    """
    Generate base 3D mesh from image via ComfyUI.
    Thin wrapper around the forge pipeline logic.

    Returns:
        Path to generated GLB/OBJ file, or error string.
    """
    from specialized.forge_agent import generate_3d_model
    return generate_3d_model(image_path, workflow_name)


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def generate_action_figure(image_path: str,
                           workflow_name: str = "workflow_triposg.json",
                           figure_name: Optional[str] = None) -> str:
    """
    Full image-to-action-figure pipeline.

    1. Generate base 3D mesh from input image
    2. Segment into body parts
    3. Add ball-socket joints
    4. Export individual STL parts

    Args:
        image_path: Path to source 2D image
        workflow_name: ComfyUI workflow template for base mesh generation
        figure_name: Name prefix for output files (auto-generated if None)

    Returns:
        Summary string with output paths, or error message.
    """
    if figure_name is None:
        figure_name = f"action_fig_{uuid.uuid4().hex[:8]}"

    logger.info(f"[ActionFigure] Starting pipeline for: {image_path}")
    logger.info(f"[ActionFigure] Figure name: {figure_name}")

    # Step 1: Generate base mesh
    logger.info("[ActionFigure] Step 1/3: Generating base 3D mesh...")
    mesh_result = _generate_base_mesh(image_path, workflow_name)

    if mesh_result.startswith("Error"):
        return f"Action Figure Generation Failed (mesh step): {mesh_result}"

    # Extract mesh path from result string
    # Format: "3D Model Generated Successfully: /path/to/file.glb"
    if ":" in mesh_result:
        mesh_path = mesh_result.split(":", 1)[1].strip()
    else:
        return f"Action Figure Generation Failed: Could not parse mesh path from: {mesh_result}"

    if not os.path.exists(mesh_path):
        return f"Action Figure Generation Failed: Generated mesh not found at {mesh_path}"

    # Step 2 & 3: Segment and add joints
    logger.info("[ActionFigure] Step 2/3: Segmenting mesh and adding ball-socket joints...")
    try:
        output_files = segment_and_joint(mesh_path, output_prefix=figure_name)
    except Exception as e:
        return f"Action Figure Generation Failed (segmentation step): {e}"

    # Step 3: Summary
    part_count = len([k for k in output_files if not k.startswith("_")])
    manifest_path = output_files.get("_manifest", "unknown")

    logger.info(f"[ActionFigure] Pipeline complete: {part_count} parts generated")

    return (
        f"Action Figure Generated Successfully: {part_count} posable parts with ball-socket joints.\n"
        f"Parts directory: {ACTION_FIGURE_OUTPUT_DIR}\n"
        f"Manifest: {manifest_path}\n"
        f"Figure name: {figure_name}"
    )


# ============================================================================
# PHIDATA AGENT WRAPPER
# ============================================================================

def get_action_figure_agent():
    """Create the Action Figure Generator agent."""
    from phi.agent import Agent
    from phi.model.ollama import Ollama

    return Agent(
        name="Action Figure Forge",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description=(
            "I convert images into 3D-printable posable action figures. "
            "I generate a base 3D mesh, then segment it into body parts "
            "connected by ball-and-socket joints for full poseability."
        ),
        instructions=(
            "Use `generate_action_figure` to convert a 2D image into a set of "
            "3D-printable STL files representing a posable action figure with "
            "ball-socket joints at neck, shoulders, elbows, wrists, waist, "
            "hips, and knees. You need a source image path first."
        ),
        tools=[generate_action_figure],
        show_tool_calls=True,
    )


if __name__ == "__main__":
    agent = get_action_figure_agent()
    agent.print_response("Status check")
