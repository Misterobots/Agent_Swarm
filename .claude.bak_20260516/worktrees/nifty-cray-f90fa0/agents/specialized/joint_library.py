"""
Parametric Joint Library for Action Figures
============================================

Generates ball-and-socket joint geometry for 3D-printed
posable action figure assembly.

Joint anatomy:
  Ball side (male)  — sphere on a cylindrical stem, protruding from parent part
  Socket side (female) — hemispherical cavity with narrowed opening for snap retention
  Socket housing — reinforcement collar around socket to prevent cracking
"""

import logging
import math
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


# ── Boolean helper ─────────────────────────────────────────────────────────

def safe_boolean(op: str, meshes: list, label: str = ""):
    """
    Boolean operation with engine fallback chain.

    op: 'union', 'difference', or 'intersection'
    """
    import trimesh

    for engine in ("manifold", "blender"):
        try:
            fn = getattr(trimesh.boolean, op)
            return fn(meshes, engine=engine)
        except Exception:
            continue

    logger.warning(f"[Joint] Boolean {op} failed ({label}), using fallback")
    if op == "union":
        return trimesh.util.concatenate(meshes)
    return meshes[0]


# ── Ball-Socket Joint ──────────────────────────────────────────────────────

class BallSocketJoint:
    """
    Parametric ball-and-socket joint for 3D-printed action figures.

    Default dimensions are tuned for FDM at 0.2mm layer height.
    For resin, reduce clearance to 0.15mm.
    """

    def __init__(
        self,
        ball_radius: float = 4.0,
        clearance: float = 0.3,
        socket_wall: float = 2.0,
        retention: float = 0.85,
        stem_ratio: float = 0.4,
        subdivisions: int = 3,
    ):
        """
        Args:
            ball_radius: Ball sphere radius (mm)
            clearance: Gap between ball and socket inner wall (mm)
            socket_wall: Socket housing wall thickness (mm)
            retention: Socket opening as fraction of ball diameter
                       (0.85 = opening is 85% of ball → snap-fit)
            stem_ratio: Stem radius as fraction of ball radius
            subdivisions: Icosphere tessellation level
        """
        self.ball_r = ball_radius
        self.clearance = clearance
        self.socket_wall = socket_wall
        self.retention = retention
        self.stem_r = ball_radius * stem_ratio
        self.stem_length = ball_radius * 1.2
        self.subs = subdivisions

    def create_ball_assembly(self) -> "trimesh.Trimesh":
        """
        Create ball + stem geometry oriented along +Z.

        Stem base at Z=0, ball center above.
        """
        import trimesh

        stem = trimesh.creation.cylinder(
            radius=self.stem_r, height=self.stem_length, sections=32,
        )
        stem.apply_translation([0, 0, self.stem_length / 2])

        ball = trimesh.creation.icosphere(
            subdivisions=self.subs, radius=self.ball_r,
        )
        # Ball center slightly above stem top so it sits on the stem
        ball.apply_translation([0, 0, self.stem_length + self.ball_r * 0.2])

        return safe_boolean("union", [stem, ball], "ball_assembly")

    def create_socket_void(self) -> "trimesh.Trimesh":
        """
        Create the void to boolean-subtract from a body part.

        Oriented along +Z: socket opening at Z=0, cavity below.
        The cavity is a sphere whose opening is narrower than the ball
        equator, creating snap-fit retention.
        """
        import trimesh

        socket_r = self.ball_r + self.clearance

        # Hemispherical cavity — center embedded below surface
        cavity = trimesh.creation.icosphere(
            subdivisions=self.subs, radius=socket_r,
        )
        # Embed center so opening < ball diameter
        embed_depth = socket_r * 0.3
        cavity.apply_translation([0, 0, -embed_depth])

        # Cylindrical passage for the stem
        opening_r = self.ball_r * self.retention + self.clearance
        passage = trimesh.creation.cylinder(
            radius=opening_r,
            height=socket_r * 2,
            sections=32,
        )
        passage.apply_translation([0, 0, socket_r * 0.5])

        return safe_boolean("union", [cavity, passage], "socket_void")

    def create_socket_housing(self) -> "trimesh.Trimesh":
        """
        Create reinforcement collar around socket.

        Boolean-union this with the body part BEFORE subtracting the void.
        Prevents the thin socket walls from cracking under stress.
        """
        import trimesh

        outer_r = self.ball_r + self.clearance + self.socket_wall

        housing = trimesh.creation.icosphere(
            subdivisions=self.subs, radius=outer_r,
        )
        embed_depth = (self.ball_r + self.clearance) * 0.3
        housing.apply_translation([0, 0, -embed_depth])

        # Clip to just the embedded hemisphere + collar above surface
        clip = trimesh.creation.box(
            extents=[outer_r * 4, outer_r * 4, outer_r * 2],
        )
        clip.apply_translation([0, 0, -outer_r * 0.5])

        return safe_boolean("intersection", [housing, clip], "socket_housing")


# ── Orientation Helper ─────────────────────────────────────────────────────

def orient_joint_geometry(
    joint_mesh, position: np.ndarray, direction: np.ndarray,
):
    """
    Rotate joint geometry from default +Z orientation to target direction,
    then translate to target position.

    Args:
        joint_mesh: Trimesh object (modified in place and returned)
        position: World-space [x, y, z]
        direction: Unit direction vector the joint should point along
    """
    import trimesh

    direction = np.asarray(direction, dtype=float)
    norm = np.linalg.norm(direction)
    if norm < 1e-8:
        joint_mesh.apply_translation(position)
        return joint_mesh
    direction = direction / norm

    default = np.array([0, 0, 1.0])

    dot = float(np.clip(np.dot(default, direction), -1, 1))

    if dot > 0.9999:
        pass  # Already aligned
    elif dot < -0.9999:
        # 180° flip around X
        rot = trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0])
        joint_mesh.apply_transform(rot)
    else:
        axis = np.cross(default, direction)
        axis = axis / np.linalg.norm(axis)
        angle = math.acos(dot)
        rot = trimesh.transformations.rotation_matrix(angle, axis)
        joint_mesh.apply_transform(rot)

    joint_mesh.apply_translation(position)
    return joint_mesh
