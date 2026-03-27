"""
Mesh Utilities for Action Figure Pipeline
==========================================

Repair, skeleton detection, and print validation for 3D meshes
from TripoSG and similar image-to-3D generators.
"""

import logging
import math
import numpy as np
from collections import deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Mesh Repair ────────────────────────────────────────────────────────────

def repair_mesh(mesh):
    """
    Comprehensive mesh repair for TripoSG output.

    Fixes non-manifold edges, holes, inconsistent normals,
    duplicate vertices, and degenerate faces.
    """
    import trimesh

    v0, f0 = len(mesh.vertices), len(mesh.faces)
    logger.info(f"[MeshRepair] Input: {v0} verts, {f0} faces, watertight={mesh.is_watertight}")

    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fill_holes(mesh)
    mesh.remove_unreferenced_vertices()

    logger.info(
        f"[MeshRepair] Output: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
        f"watertight={mesh.is_watertight}"
    )
    return mesh


# ── Cross-section Analysis ─────────────────────────────────────────────────

def _flood_fill_labels(grid: np.ndarray) -> Tuple[np.ndarray, int]:
    """Connected component labeling via BFS flood-fill (no scipy needed)."""
    rows, cols = grid.shape
    labeled = np.zeros((rows, cols), dtype=np.int32)
    n_labels = 0

    for r in range(rows):
        for c in range(cols):
            if grid[r, c] and labeled[r, c] == 0:
                n_labels += 1
                queue = deque([(r, c)])
                labeled[r, c] = n_labels
                while queue:
                    cr, cc = queue.popleft()
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr, nc] and labeled[nr, nc] == 0:
                                labeled[nr, nc] = n_labels
                                queue.append((nr, nc))

    return labeled, n_labels


def _dilate_grid(grid: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Simple binary dilation without scipy."""
    result = grid.copy()
    rows, cols = grid.shape
    for _ in range(iterations):
        new = result.copy()
        for r in range(rows):
            for c in range(cols):
                if result[r, c]:
                    if r > 0:     new[r - 1, c] = True
                    if r < rows - 1: new[r + 1, c] = True
                    if c > 0:     new[r, c - 1] = True
                    if c < cols - 1: new[r, c + 1] = True
        result = new
    return result


def _label_components(grid: np.ndarray) -> Tuple[np.ndarray, int]:
    """Label connected components, using scipy if available."""
    try:
        from scipy.ndimage import binary_dilation, label as scipy_label
        dilated = binary_dilation(grid, iterations=2)
        return scipy_label(dilated)
    except ImportError:
        dilated = _dilate_grid(grid, iterations=2)
        return _flood_fill_labels(dilated)


def analyze_cross_section(
    mesh, z_height: float, band: float = 2.0, grid_res: float = 0.5,
) -> Optional[Dict]:
    """
    Analyze mesh cross-section at a given Z height.

    Projects vertices within a thin horizontal band onto a 2D occupancy
    grid and finds connected components.

    Returns:
        Dict with z, n_components, centroids (list of [x,y]),
        bboxes (list of dicts), areas, total_area, width.
        None if the slice is empty.
    """
    verts = mesh.vertices
    mask = np.abs(verts[:, 2] - z_height) < band / 2
    pts = verts[mask][:, :2]

    if len(pts) < 3:
        return None

    xy_min = pts.min(axis=0) - grid_res
    xy_max = pts.max(axis=0) + grid_res
    grid_shape = ((xy_max - xy_min) / grid_res + 1).astype(int)

    if grid_shape[0] < 1 or grid_shape[1] < 1 or grid_shape.max() > 500:
        return None

    grid = np.zeros((grid_shape[1], grid_shape[0]), dtype=bool)  # rows=Y, cols=X
    ix = np.clip(((pts[:, 0] - xy_min[0]) / grid_res).astype(int), 0, grid_shape[0] - 1)
    iy = np.clip(((pts[:, 1] - xy_min[1]) / grid_res).astype(int), 0, grid_shape[1] - 1)
    grid[iy, ix] = True

    labeled, n_comp = _label_components(grid)

    if n_comp == 0:
        return None

    centroids, areas, bboxes = [], [], []
    for i in range(1, n_comp + 1):
        comp_mask = labeled == i
        ys, xs = np.where(comp_mask)
        if len(xs) == 0:
            continue
        cx = xy_min[0] + xs.mean() * grid_res
        cy = xy_min[1] + ys.mean() * grid_res
        area = comp_mask.sum() * grid_res ** 2
        centroids.append(np.array([cx, cy]))
        areas.append(area)
        bboxes.append({
            "x_min": xy_min[0] + xs.min() * grid_res,
            "x_max": xy_min[0] + xs.max() * grid_res,
            "y_min": xy_min[1] + ys.min() * grid_res,
            "y_max": xy_min[1] + ys.max() * grid_res,
        })

    # Filter tiny components (< 5% of largest)
    if areas:
        max_area = max(areas)
        keep = [(c, a, b) for c, a, b in zip(centroids, areas, bboxes) if a > 0.05 * max_area]
        if keep:
            centroids = [k[0] for k in keep]
            areas = [k[1] for k in keep]
            bboxes = [k[2] for k in keep]

    return {
        "z": z_height,
        "n_components": len(centroids),
        "centroids": centroids,
        "areas": areas,
        "bboxes": bboxes,
        "total_area": sum(areas),
        "width": pts[:, 0].ptp(),
    }


# ── Skeleton Detection ─────────────────────────────────────────────────────

def detect_skeleton(mesh, n_slices: int = 80) -> Dict:
    """
    Detect humanoid skeleton from mesh cross-section analysis.

    Scans horizontal slices bottom-to-top, looking for:
      - Hip split  : 2 components (legs) → 1 (torso)
      - Waist      : narrowest torso width
      - Shoulders  : widest upper-body width / component split
      - Neck       : narrowest point above shoulders

    Returns dict with 'joints', 'confidence', 'detected_features'.
    Each joint has position (ndarray), normal (ndarray), radius (float).
    """
    bounds = mesh.bounds
    z_min, z_max = float(bounds[0][2]), float(bounds[1][2])
    height = z_max - z_min
    cx = float((bounds[0][0] + bounds[1][0]) / 2)

    if height <= 0:
        logger.warning("[Skeleton] Mesh has zero height")
        return _default_skeleton(mesh)

    band = height / n_slices * 1.5
    grid_res = max(0.5, height / 300)

    slices = []
    for i in range(n_slices):
        z = z_min + (i + 0.5) * height / n_slices
        cs = analyze_cross_section(mesh, z, band=band, grid_res=grid_res)
        slices.append(cs)

    valid = [(i, s) for i, s in enumerate(slices) if s is not None]
    if len(valid) < 10:
        logger.warning("[Skeleton] Too few valid cross-sections, using defaults")
        return _default_skeleton(mesh)

    z_vals  = np.array([s["z"] for _, s in valid])
    n_comps = np.array([s["n_components"] for _, s in valid])
    areas   = np.array([s["total_area"] for _, s in valid])
    widths  = np.array([s["width"] for _, s in valid])

    # Helper: interpolate width at any Z
    def _width_at(z):
        idx = np.clip(np.searchsorted(z_vals, z), 0, len(widths) - 1)
        return float(widths[idx])

    def _radius(z, frac=0.25):
        return max(2.0, min(6.0, _width_at(z) * frac))

    confidence = 0.7

    # ── Hip split: 2→1 components going upward ──
    hip_z = None
    for j in range(1, len(n_comps)):
        if n_comps[j - 1] >= 2 and n_comps[j] == 1:
            hip_z = float(z_vals[j])
            break
    if hip_z is None:
        lower = z_vals < z_min + 0.4 * height
        if lower.any():
            hip_z = float(z_vals[lower][np.argmin(areas[lower])])
        else:
            hip_z = z_min + 0.45 * height
        confidence -= 0.15

    # ── Shoulder region: widest point in upper 40% ──
    upper = z_vals > z_min + 0.6 * height
    if upper.any():
        idx = np.argmax(widths[upper])
        shoulder_z = float(z_vals[upper][idx])
        shoulder_width = float(widths[upper][idx])
    else:
        shoulder_z = z_min + 0.78 * height
        shoulder_width = float(widths.max()) if len(widths) else height * 0.3
        confidence -= 0.15

    # ── Neck: narrowest above shoulders (lower 2/3 of head region) ──
    above_sh = z_vals > shoulder_z
    if above_sh.sum() > 2:
        neck_w = widths[above_sh]
        neck_z_arr = z_vals[above_sh]
        search_len = max(1, len(neck_w) * 2 // 3)
        neck_z = float(neck_z_arr[np.argmin(neck_w[:search_len])])
    else:
        neck_z = shoulder_z + 0.05 * height

    # ── Waist: narrowest between hip and shoulder ──
    torso_mask = (z_vals > hip_z) & (z_vals < shoulder_z)
    if torso_mask.any():
        waist_z = float(z_vals[torso_mask][np.argmin(widths[torso_mask])])
    else:
        waist_z = (hip_z + shoulder_z) / 2

    # ── Arm X positions from cross-section at shoulder height ──
    shoulder_cs = None
    for _, s in valid:
        if abs(s["z"] - shoulder_z) < band * 1.5:
            shoulder_cs = s
            break

    left_sh_x = cx - shoulder_width * 0.35
    right_sh_x = cx + shoulder_width * 0.35

    if shoulder_cs and shoulder_cs["n_components"] >= 3:
        # Sort components by centroid X
        sorted_c = sorted(
            zip(shoulder_cs["centroids"], shoulder_cs["bboxes"]),
            key=lambda x: x[0][0],
        )
        left_sh_x = float(sorted_c[0][1]["x_max"])   # right edge of left arm comp
        right_sh_x = float(sorted_c[-1][1]["x_min"])  # left edge of right arm comp
    elif shoulder_cs and shoulder_cs["n_components"] == 1 and shoulder_cs["bboxes"]:
        # Single component — estimate shoulders at ±35% of width
        bb = shoulder_cs["bboxes"][0]
        w = bb["x_max"] - bb["x_min"]
        left_sh_x = bb["x_min"] + w * 0.2
        right_sh_x = bb["x_max"] - w * 0.2

    # ── Elbow X: midpoint of arm span ──
    left_elbow_x = (left_sh_x + float(bounds[0][0])) / 2
    right_elbow_x = (right_sh_x + float(bounds[1][0])) / 2

    # ── Knee Z: midpoint of leg length ──
    knee_z = z_min + (hip_z - z_min) * 0.45

    # ── Hip X offset from center ──
    hip_offset = _width_at(hip_z) * 0.2

    # ── Build joint dict ──
    joints = {
        "neck": {
            "position": np.array([cx, 0, neck_z]),
            "normal": np.array([0, 0, 1.0]),
            "radius": _radius(neck_z, 0.3),
        },
        "waist": {
            "position": np.array([cx, 0, waist_z]),
            "normal": np.array([0, 0, 1.0]),
            "radius": _radius(waist_z, 0.2),
        },
        "left_shoulder": {
            "position": np.array([left_sh_x, 0, shoulder_z]),
            "normal": np.array([-1, 0, 0.0]),
            "radius": _radius(shoulder_z, 0.12),
        },
        "right_shoulder": {
            "position": np.array([right_sh_x, 0, shoulder_z]),
            "normal": np.array([1, 0, 0.0]),
            "radius": _radius(shoulder_z, 0.12),
        },
        "left_elbow": {
            "position": np.array([left_elbow_x, 0, shoulder_z]),
            "normal": np.array([-1, 0, 0.0]),
            "radius": _radius(shoulder_z, 0.10),
        },
        "right_elbow": {
            "position": np.array([right_elbow_x, 0, shoulder_z]),
            "normal": np.array([1, 0, 0.0]),
            "radius": _radius(shoulder_z, 0.10),
        },
        "left_hip": {
            "position": np.array([cx - hip_offset, 0, hip_z]),
            "normal": np.array([0, 0, -1.0]),
            "radius": _radius(hip_z, 0.18),
        },
        "right_hip": {
            "position": np.array([cx + hip_offset, 0, hip_z]),
            "normal": np.array([0, 0, -1.0]),
            "radius": _radius(hip_z, 0.18),
        },
        "left_knee": {
            "position": np.array([cx - hip_offset * 0.8, 0, knee_z]),
            "normal": np.array([0, 0, -1.0]),
            "radius": _radius(knee_z, 0.15),
        },
        "right_knee": {
            "position": np.array([cx + hip_offset * 0.8, 0, knee_z]),
            "normal": np.array([0, 0, -1.0]),
            "radius": _radius(knee_z, 0.15),
        },
    }

    return {
        "joints": joints,
        "confidence": confidence,
        "detected_features": {
            "hip_z": hip_z,
            "waist_z": waist_z,
            "shoulder_z": shoulder_z,
            "neck_z": neck_z,
            "shoulder_width": shoulder_width,
        },
    }


def _default_skeleton(mesh) -> Dict:
    """Fallback skeleton using standard humanoid proportions."""
    bounds = mesh.bounds
    z_min, z_max = float(bounds[0][2]), float(bounds[1][2])
    h = z_max - z_min
    cx = float((bounds[0][0] + bounds[1][0]) / 2)
    w = float(bounds[1][0] - bounds[0][0])

    def r(frac):
        return max(2.0, min(6.0, w * frac))

    joints = {
        "neck":            {"position": np.array([cx, 0, z_min + 0.85 * h]), "normal": np.array([0, 0, 1.0]),  "radius": r(0.15)},
        "waist":           {"position": np.array([cx, 0, z_min + 0.55 * h]), "normal": np.array([0, 0, 1.0]),  "radius": r(0.20)},
        "left_shoulder":   {"position": np.array([cx - w * 0.35, 0, z_min + 0.78 * h]), "normal": np.array([-1, 0, 0.0]), "radius": r(0.12)},
        "right_shoulder":  {"position": np.array([cx + w * 0.35, 0, z_min + 0.78 * h]), "normal": np.array([1, 0, 0.0]),  "radius": r(0.12)},
        "left_elbow":      {"position": np.array([bounds[0][0] + w * 0.15, 0, z_min + 0.78 * h]), "normal": np.array([-1, 0, 0.0]), "radius": r(0.10)},
        "right_elbow":     {"position": np.array([bounds[1][0] - w * 0.15, 0, z_min + 0.78 * h]), "normal": np.array([1, 0, 0.0]),  "radius": r(0.10)},
        "left_hip":        {"position": np.array([cx - w * 0.10, 0, z_min + 0.45 * h]), "normal": np.array([0, 0, -1.0]), "radius": r(0.15)},
        "right_hip":       {"position": np.array([cx + w * 0.10, 0, z_min + 0.45 * h]), "normal": np.array([0, 0, -1.0]), "radius": r(0.15)},
        "left_knee":       {"position": np.array([cx - w * 0.08, 0, z_min + 0.25 * h]), "normal": np.array([0, 0, -1.0]), "radius": r(0.12)},
        "right_knee":      {"position": np.array([cx + w * 0.08, 0, z_min + 0.25 * h]), "normal": np.array([0, 0, -1.0]), "radius": r(0.12)},
    }

    return {"joints": joints, "confidence": 0.3, "detected_features": {}}


# ── Print Validation ───────────────────────────────────────────────────────

def validate_printability(
    parts: Dict[str, "trimesh.Trimesh"], min_wall_mm: float = 1.0,
) -> List[str]:
    """
    Check body parts for common 3D-printing issues.

    Returns list of warning strings (empty = all clear).
    """
    warnings = []
    for name, part in parts.items():
        if name.startswith("_"):
            continue

        if not part.is_watertight:
            warnings.append(f"{name}: not watertight (may cause slicer artifacts)")

        dims = part.bounding_box.extents
        if min(dims) < min_wall_mm:
            warnings.append(f"{name}: thinnest dimension {min(dims):.1f}mm < {min_wall_mm}mm")

        if len(part.faces) < 20:
            warnings.append(f"{name}: only {len(part.faces)} faces (degenerate cut?)")

        try:
            if part.is_watertight and part.volume < 1.0:
                warnings.append(f"{name}: volume only {part.volume:.1f}mm³")
        except Exception:
            pass

    return warnings
