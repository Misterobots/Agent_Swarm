"""handlers/cad.py — CAD Studio intent handler (OpenSCAD local pipeline).

Flow:
  1. Ollama (qwen3-coder or CODER_MODEL) generates OpenSCAD (.scad) source
     from natural language.
  2. openscad CLI renders the .scad to .stl (falls back gracefully if not installed).
  3. cad_artifact SSE event carries the source + download URLs for the UI card.

Install OpenSCAD on Turing/Lovelace:
  sudo apt install openscad          # Debian/Ubuntu
  # or headless nightly build for server use:
  # https://openscad.org/downloads.html#snapshots

ENV overrides:
  CAD_OUTPUT_DIR  — where .scad and .stl files are written (default /workspace/cad_artifacts)
  OPENSCAD_BIN    — path to openscad binary (default: openscad on $PATH)
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from handlers.base import _emit_stream_mode, _emit_turn_metadata
from metrics import AGENT_STATE, WORKFLOW_STEPS
from utils.gpu_queue import request_lock, get_best_host_for_model

logger = logging.getLogger("Router")

_CAD_OUTPUT_DIR = os.getenv("CAD_OUTPUT_DIR", "/workspace/cad_artifacts")
_OPENSCAD_BIN = os.getenv("OPENSCAD_BIN", "openscad")

_SYSTEM_PROMPT = """\
You are an expert OpenSCAD programmer specialising in FDM 3D-printing-optimised parametric models.
Convert the user's description into a complete, working OpenSCAD (.scad) script.

Hard rules:
- Output ONLY raw OpenSCAD code — no markdown fences, no explanations, no preamble
- Declare ALL configurable dimensions as named variables at the very top
- Include brief // inline comments on each major section and boolean operation
- The file must end with (or render) the complete assembled solid — never leave it headless
- Every measurement is in millimetres; all wall thicknesses ≥ 1.5 mm unless specified
- FDM tolerances: clearance fits 0.2 mm, press fits 0.1 mm, holes 0.2 mm oversize

CRITICAL OpenSCAD syntax rules:
- Variables hold NUMBERS only: `width = 20;` is valid, `shape = cube(20);` is INVALID
- NEVER write `x = union() { ... }` — this is not valid OpenSCAD and will cause a parse error
- To name a shape, use a module: `module x() { union() { ... } }` then call it with `x();`
- The final line must be a geometry call, e.g. `difference() { ... }` or `mypart();`
- Use for() loops for repeated features (bolt holes, fins, teeth, slots)
- Use $fn = 64 for smooth cylinders; add a `// $fn = 16 for preview` comment
- Position the model flat on the XY plane (Z = 0 at the bottom face)

If any dimension is underspecified, pick a sensible default and document it with a // comment.
"""


# ---------------------------------------------------------------------------
# SCAD post-processor
# ---------------------------------------------------------------------------

_CSG_OPS = r'(?:union|difference|intersection|hull|minkowski|render)'
_ASSIGN_PATTERN = re.compile(
    r'^(\s*)(\w+)\s*=\s*' + _CSG_OPS + r'\s*\(\s*\)\s*\{',
    re.MULTILINE,
)

def _fix_scad_syntax(scad: str) -> str:
    """
    Fix the common LLM hallucination of assigning CSG ops to variables:
        name = union() {  →  module name() {
    and appends `name();` if the module isn't called elsewhere.
    """
    fixed_names: list[str] = []

    def _sub(m: re.Match) -> str:
        indent, name = m.group(1), m.group(2)
        fixed_names.append(name)
        original_op = m.group(0).split("=", 1)[1].strip().rstrip("{").strip()
        return f"{indent}module {name}() {{ // (was: {name} = {original_op})"

    result = _ASSIGN_PATTERN.sub(_sub, scad)

    for name in fixed_names:
        if not re.search(r'\b' + re.escape(name) + r'\s*\(\s*\)\s*;', result):
            result = result.rstrip() + f"\n\n{name}(); // auto-added call\n"

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_scad(user_input: str, model: str, host: str, history: list | None) -> str:
    """Stream OpenSCAD source from Ollama chat API; return assembled string."""
    import requests as _req

    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for msg in (history or []):
        role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role in ("user", "assistant") and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_input})

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.15, "num_predict": 4096},
    }
    resp = _req.post(f"{host}/api/chat", json=payload, stream=True, timeout=120)
    resp.raise_for_status()

    chunks: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            obj = json.loads(line)
            content = obj.get("message", {}).get("content", "")
            if content:
                chunks.append(content)
            if obj.get("done"):
                break
        except Exception:
            pass

    raw = "".join(chunks).strip()
    # Strip accidental markdown fences the model might add despite instructions
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _generate_scad_retry(user_input: str, prev_scad: str, error: str,
                         model: str, host: str) -> str:
    """Re-generate by feeding the previous output + error back to the model."""
    import requests as _req
    fix_msg = (
        f"The OpenSCAD script above has this error:\n\n{error}\n\n"
        "Please fix it and return ONLY the corrected OpenSCAD code with no markdown fences.\n\n"
        "Reminder: in OpenSCAD, variables hold NUMBERS only — you cannot assign geometry "
        "to a variable. Replace any `name = union() { ... }` with `module name() { ... }` "
        "and add a `name();` call at the end of the file."
    )
    messages = [
        {"role": "system",    "content": _SYSTEM_PROMPT},
        {"role": "user",      "content": user_input},
        {"role": "assistant", "content": prev_scad},
        {"role": "user",      "content": fix_msg},
    ]
    payload = {
        "model":    model,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.1, "num_predict": 8192},
    }
    resp = _req.post(f"{host}/api/chat", json=payload, stream=True, timeout=120)
    resp.raise_for_status()
    chunks: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            obj = json.loads(line)
            content = obj.get("message", {}).get("content", "")
            if content:
                chunks.append(content)
            if obj.get("done"):
                break
        except Exception:
            pass
    raw = "".join(chunks).strip()
    for fence in ("```openscad", "```scad", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _render_stl(scad_source: str, output_path: str) -> tuple[bool, str]:
    """Write .scad to a temp file and shell out to openscad. Returns (ok, error_msg)."""
    with tempfile.NamedTemporaryFile(suffix=".scad", delete=False, mode="w") as tf:
        tf.write(scad_source)
        scad_tmp = tf.name
    try:
        result = subprocess.run(
            [_OPENSCAD_BIN, "-o", output_path, scad_tmp],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error")[:600]
            return False, err
        return True, ""
    except FileNotFoundError:
        return False, (
            f"openscad binary not found at '{_OPENSCAD_BIN}'. "
            "Install with: sudo apt install openscad"
        )
    except subprocess.TimeoutExpired:
        return False, "OpenSCAD render timed out (>90 s)"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(scad_tmp)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# STL analysis
# ---------------------------------------------------------------------------

def _analyze_stl_trimesh(stl_path: str) -> dict:
    import trimesh as _tm
    import numpy as _np
    mesh = _tm.load(stl_path, force="mesh")
    bb = [round(float(x), 2) for x in mesh.bounding_box.extents]
    n_faces = int(len(mesh.faces))
    sa = float(mesh.area)
    vol = float(mesh.volume) if mesh.is_watertight else 0.0
    normals_z = mesh.face_normals[:, 2]
    overhang     = int(_np.sum(normals_z < -0.707))
    flat_bottom  = int(_np.sum(normals_z < -0.990))
    flat_top     = int(_np.sum(normals_z >  0.990))
    return {
        "triangles": n_faces,
        "bbox_mm": bb,
        "volume_mm3": round(vol, 2),
        "surface_area_mm2": round(sa, 2),
        "is_watertight": bool(mesh.is_watertight),
        "overhang_faces": overhang,
        "overhang_pct": round(100 * overhang / max(n_faces, 1), 1),
        "flat_bottom_faces": flat_bottom,
        "flat_top_faces": flat_top,
        "sa_vol_ratio": round(sa / max(vol, 0.001), 4),
    }


def _analyze_stl_basic(stl_path: str) -> dict:
    """Stdlib struct-based binary STL parser — zero dependencies."""
    import struct
    with open(stl_path, "rb") as f:
        f.read(80)  # skip header
        raw_count = f.read(4)
        if len(raw_count) < 4:
            return {"error": "truncated STL"}
        n = struct.unpack("<I", raw_count)[0]
        bbox = [1e18, 1e18, 1e18, -1e18, -1e18, -1e18]
        overhang = 0
        for _ in range(n):
            tri = f.read(50)
            if len(tri) < 50:
                break
            nx, ny, nz = struct.unpack("<fff", tri[0:12])
            verts = struct.unpack("<9f", tri[12:48])
            xs = [verts[0], verts[3], verts[6]]
            ys = [verts[1], verts[4], verts[7]]
            zs = [verts[2], verts[5], verts[8]]
            bbox[0] = min(bbox[0], *xs); bbox[3] = max(bbox[3], *xs)
            bbox[1] = min(bbox[1], *ys); bbox[4] = max(bbox[4], *ys)
            bbox[2] = min(bbox[2], *zs); bbox[5] = max(bbox[5], *zs)
            if nz < -0.707:
                overhang += 1
    w, d, h = round(bbox[3]-bbox[0], 2), round(bbox[4]-bbox[1], 2), round(bbox[5]-bbox[2], 2)
    return {
        "triangles": n,
        "bbox_mm": [w, d, h],
        "volume_mm3": 0.0,
        "surface_area_mm2": 0.0,
        "is_watertight": None,
        "overhang_faces": overhang,
        "overhang_pct": round(100 * overhang / max(n, 1), 1),
        "flat_bottom_faces": 0,
        "flat_top_faces": 0,
        "sa_vol_ratio": 0.0,
    }


def _analyze_stl(stl_path: str) -> dict:
    try:
        return _analyze_stl_trimesh(stl_path)
    except Exception as _e:
        logger.info("[CAD] trimesh unavailable (%s), using basic parser", _e)
        return _analyze_stl_basic(stl_path)


def _format_analysis_md(stl_name: str, stats: dict) -> str:
    bb = stats.get("bbox_mm", [0, 0, 0])
    rows = [
        ("Triangles", f"{stats.get('triangles', '?'):,}"),
        ("Bounding box", f"{bb[0]:.1f} × {bb[1]:.1f} × {bb[2]:.1f} mm"),
    ]
    if stats.get("volume_mm3"):
        v = stats["volume_mm3"]
        rows.append(("Volume", f"{v:.1f} mm³  ≈  {v/1000:.2f} cm³"))
    if stats.get("surface_area_mm2"):
        rows.append(("Surface area", f"{stats['surface_area_mm2']:.1f} mm²"))
    if stats.get("is_watertight") is not None:
        rows.append(("Watertight/manifold", "YES ✓" if stats["is_watertight"] else "NO ✗ (open mesh)"))
    rows.append(("Overhang faces (>45°)", f"{stats.get('overhang_faces','?')} ({stats.get('overhang_pct','?')}%)"))
    if stats.get("flat_bottom_faces"):
        rows.append(("Flat bottom faces", str(stats["flat_bottom_faces"])))
    if stats.get("flat_top_faces"):
        rows.append(("Flat top faces", str(stats["flat_top_faces"])))
    if stats.get("sa_vol_ratio"):
        rows.append(("Surface/volume ratio", f"{stats['sa_vol_ratio']:.4f}  (higher = thinner/more complex)"))
    table = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return f"### Analysis: {stl_name}\n\n| Property | Value |\n|----------|-------|\n{table}"


# ---------------------------------------------------------------------------
# STL-aware system prompts
# ---------------------------------------------------------------------------

_REVIEW_SYSTEM_PROMPT = """\
You are an expert FDM 3D printing engineer reviewing an STL file for printability,
structural integrity, and design quality.

You will be given trimesh analysis statistics about the model. Use these numbers to
ground your review precisely — do NOT fabricate measurements or reference features
you cannot infer from the data.

Structure your review with these sections:
1. **Dimensions & Scale** — Is the size appropriate for typical FDM printers?
2. **Printability** — Overhangs, bridging risk, flat-bottom adhesion. Support requirements?
3. **Structural Integrity** — Watertight status, thin walls, stress concentration points.
4. **FDM Optimisation** — Print orientation, layer adhesion direction, wall count, nozzle size.
5. **Specific Improvements** — 3–5 concrete, actionable recommendations with estimated dimensions.
6. **Summary** — One-paragraph verdict.

Be concise and specific. If data is missing (volume=0, watertight=null), note the
limitation and reason from the data that IS available.
"""

_MODIFY_SYSTEM_PROMPT = """\
You are an expert OpenSCAD programmer specialising in FDM 3D-printing-optimised parametric models.

The user has provided an existing STL file. Write an OpenSCAD script that:
1. Imports the original STL unchanged: import("{stl_path}");
2. Applies the requested modification using boolean operations (difference, union, intersection)
3. Produces a complete, valid, renderable script

Hard rules:
- The FIRST non-comment line must be the import() statement with the EXACT path shown above
- Output ONLY raw OpenSCAD code — no markdown fences, no explanations
- CRITICAL syntax: variables hold NUMBERS only. NEVER write `name = union() {{ ... }}`.
  Always use: `module name() {{ ... }}` then call `name();`
- Declare any new dimensions as named variables at the top (below the import)
- All measurements in millimetres; clearance fits 0.2 mm
- The final assembled call must render the COMPLETE result (import + modifications)
"""

_INTEGRATE_SYSTEM_PROMPT = """\
You are an expert OpenSCAD programmer. The user has an existing component (imported as STL).
Design NEW parts that fit around, connect to, or complement the existing component.

1. Import the existing component: import("{stl_path}");
2. Design new geometry around it using the bounding-box dimensions as reference
3. Use difference() for cutouts, union() for additions, translate() for positioning

Hard rules:
- The FIRST non-comment line must be the import() statement with the EXACT path shown above
- Output ONLY raw OpenSCAD code — no markdown fences, no explanations
- CRITICAL syntax: variables hold NUMBERS only. NEVER write `name = union() {{ ... }}`.
  Always use: `module name() {{ ... }}` then call `name();`
- Declare new dimensions as named variables at the top
- The final call must render the complete assembly (imported part + new parts)
"""


# ---------------------------------------------------------------------------
# STL-aware Ollama helpers
# ---------------------------------------------------------------------------

def _stream_ollama(messages: list, model: str, host: str, temperature: float = 0.15,
                   num_predict: int = 4096) -> list:
    """Stream from Ollama /api/chat; return list of text chunks."""
    import requests as _req
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    resp = _req.post(f"{host}/api/chat", json=payload, stream=True, timeout=120)
    resp.raise_for_status()
    chunks: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            obj = json.loads(line)
            c = obj.get("message", {}).get("content", "")
            if c:
                chunks.append(c)
            if obj.get("done"):
                break
        except Exception:
            pass
    return chunks


def _stream_review(stl_name: str, stats: dict, user_input: str, model: str, host: str):
    """Generator: yields text chunks of the FDM review, streaming from Ollama."""
    import requests as _req
    analysis_text = _format_analysis_md(stl_name, stats)
    user_q = user_input.strip() or "Please review this STL for FDM printing."
    messages = [
        {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
        {"role": "user",   "content": f"{analysis_text}\n\nUser question: {user_q}"},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.2, "num_predict": 2048},
    }
    resp = _req.post(f"{host}/api/chat", json=payload, stream=True, timeout=120)
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            obj = json.loads(line)
            c = obj.get("message", {}).get("content", "")
            if c:
                yield c
            if obj.get("done"):
                break
        except Exception:
            pass


def _generate_scad_with_stl(stl_path: str, stl_name: str, user_input: str,
                              mode: str, model: str, host: str,
                              history: list | None, stats: dict) -> str:
    """Generate OpenSCAD that imports an existing STL (modify or integrate mode)."""
    # Forward slashes required for OpenSCAD import() on all platforms
    stl_fwd = str(Path(stl_path).resolve()).replace("\\", "/")
    if mode == "integrate":
        sys_tmpl = _INTEGRATE_SYSTEM_PROMPT
    else:
        sys_tmpl = _MODIFY_SYSTEM_PROMPT
    system = sys_tmpl.format(stl_path=stl_fwd)

    analysis_text = _format_analysis_md(stl_name, stats)
    bb = stats.get("bbox_mm", [0, 0, 0])
    context = (
        f"{analysis_text}\n\n"
        f"Approximate bounding box: {bb[0]:.1f} × {bb[1]:.1f} × {bb[2]:.1f} mm (W × D × H)\n\n"
        f"User request: {user_input}"
    )

    messages: list[dict] = [{"role": "system", "content": system}]
    for msg in (history or []):
        role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role in ("user", "assistant") and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": context})

    chunks = _stream_ollama(messages, model, host, temperature=0.15, num_predict=8192)
    raw = "".join(chunks).strip()
    # Strip markdown fences if model added them despite instructions
    for fence in ("```openscad", "```scad", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


# ---------------------------------------------------------------------------
# Mode-specific sub-handlers
# ---------------------------------------------------------------------------

def _handle_cad_review(user_input: str, stl_path: str, stl_name: str, ctx: dict):
    """Review mode: analyse STL + stream markdown critique as assistant text."""
    from config import CODER_MODEL
    model = ctx.get("model") or CODER_MODEL
    host = get_best_host_for_model(model)

    yield {"type": "status", "content": f"📐 CAD Studio: Analysing {stl_name}..."}
    stats = _analyze_stl(stl_path)
    analysis_md = _format_analysis_md(stl_name, stats)
    yield {"type": "log", "content": f"[CAD] STL stats: {stats}"}

    # Emit the analysis table as the first part of the assistant response
    yield {"type": "message", "content": analysis_md + "\n\n---\n\n"}

    yield {"type": "status", "content": f"🔍 CAD Studio: Generating FDM review..."}
    try:
        with request_lock(context="text"):
            for chunk in _stream_review(stl_name, stats, user_input, model, host):
                yield {"type": "message", "content": chunk}
    except Exception as e:
        logger.error("[CAD] Review generation failed: %s", e, exc_info=True)
        yield {"type": "message", "content": f"\n\n> ⚠️ Review generation error: {e}"}


def _handle_cad_modify(user_input: str, stl_path: str, stl_name: str,
                        mode: str, ctx: dict):
    """Modify/integrate mode: generate OpenSCAD with import(), render, emit cad_artifact."""
    turn_id = ctx["turn_id"]
    history  = ctx.get("history")
    from config import CODER_MODEL
    model = ctx.get("model") or CODER_MODEL
    host  = get_best_host_for_model(model)

    yield _emit_turn_metadata(turn_id, "CAD Studio", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    AGENT_STATE.labels(agent_name="CAD").set(2)

    mode_label = "Integrate" if mode == "integrate" else "Modify"
    yield {"type": "status", "content": f"📐 CAD Studio: Analysing {stl_name}..."}
    stats = _analyze_stl(stl_path)
    yield {"type": "log", "content": f"[CAD] STL stats ({mode_label}): {stats}"}

    yield {"type": "status", "content": f"📐 CAD Studio: Generating {mode_label} script..."}
    scad_source = ""
    try:
        with request_lock(context="text"):
            yield _emit_stream_mode("responding")
            scad_source = _generate_scad_with_stl(
                stl_path, stl_name, user_input, mode, model, host, history, stats
            )
    except Exception as e:
        logger.error("[CAD] %s SCAD generation failed: %s", mode_label, e, exc_info=True)
        yield {"type": "error", "content": f"CAD {mode_label} generation failed: {e}"}
        return

    if not scad_source:
        yield {"type": "error", "content": f"CAD {mode_label} returned empty output."}
        return

    scad_fixed = _fix_scad_syntax(scad_source)
    if scad_fixed != scad_source:
        logger.info("[CAD] Patched geometry variable assignments → modules (%s)", mode_label)
        scad_source = scad_fixed

    yield {"type": "log", "content": f"[CAD] Generated {len(scad_source)} chars of OpenSCAD ({mode_label})"}
    yield {"type": "status", "content": "🔧 CAD Studio: Rendering STL..."}

    Path(_CAD_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    artifact_id = str(uuid.uuid4())
    stl_out  = os.path.join(_CAD_OUTPUT_DIR, f"{artifact_id}.stl")
    scad_out = os.path.join(_CAD_OUTPUT_DIR, f"{artifact_id}.scad")

    try:
        Path(scad_out).write_text(scad_source, encoding="utf-8")
    except Exception as e:
        logger.warning("[CAD] Could not save .scad: %s", e)

    render_ok, render_err = _render_stl(scad_source, stl_out)

    # One retry on syntax error
    if not render_ok and "syntax error" in render_err.lower():
        yield {"type": "status", "content": "📐 CAD Studio: Fixing syntax error, retrying..."}
        try:
            retried = _generate_scad_retry(
                user_input, scad_source, render_err, model, host
            )
            retried = _fix_scad_syntax(retried)
            if retried:
                scad_source = retried
                Path(scad_out).write_text(scad_source, encoding="utf-8")
                render_ok, render_err = _render_stl(scad_source, stl_out)
        except Exception as re2:
            logger.warning("[CAD] %s retry failed: %s", mode_label, re2)

    stl_url: str | None = None
    if render_ok:
        stl_url = f"/files/cad/{artifact_id}.stl"
        yield {"type": "log", "content": f"[CAD] STL rendered → {stl_out}"}
    else:
        logger.warning("[CAD] STL render skipped (%s): %s", mode_label, render_err)
        yield {"type": "log", "content": f"[CAD] STL render skipped: {render_err}"}

    yield {
        "type": "cad_artifact",
        "cad_artifact": {
            "id": artifact_id,
            "prompt": f"[{mode_label}] {user_input}",
            "scad_source": scad_source,
            "scad_url": f"/files/cad/{artifact_id}.scad",
            "stl_url": stl_url,
            "render_ok": render_ok,
            "render_error": render_err if not render_ok else None,
            "source_stl": stl_path,
            "mode": mode,
        },
    }

    AGENT_STATE.labels(agent_name="CAD").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="CAD").inc()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handle_cad(user_input: str, ctx: dict):
    """Generator — dispatch by cad_mode: review / modify / integrate / generate."""
    # --- STL input mode dispatch ---
    uploaded_stl = ctx.get("uploaded_stl")
    if uploaded_stl:
        stl_name = ctx.get("uploaded_stl_name") or Path(uploaded_stl).name
        cad_mode = ctx.get("cad_mode", "review")
        if cad_mode == "review":
            yield from _handle_cad_review(user_input, uploaded_stl, stl_name, ctx)
        else:  # modify or integrate
            yield from _handle_cad_modify(user_input, uploaded_stl, stl_name, cad_mode, ctx)
        return

    # --- Generate mode (no uploaded STL) ---
    turn_id = ctx["turn_id"]
    history = ctx.get("history")
    extracted_context = ctx.get("extracted_context", "")

    from config import CODER_MODEL
    model = ctx.get("model") or CODER_MODEL
    host = get_best_host_for_model(model)

    yield _emit_turn_metadata(turn_id, "CAD Studio", ["thinking", "responding"])
    yield _emit_stream_mode("thinking")
    AGENT_STATE.labels(agent_name="CAD").set(2)

    # If the user attached a reference doc / image, append a note to the prompt
    prompt = user_input
    if extracted_context and not extracted_context.startswith("data:image"):
        prompt = f"{user_input}\n\n[Reference context]\n{extracted_context[:3000]}"

    yield {"type": "status", "content": "📐 CAD Studio: Generating OpenSCAD model..."}

    # ── Generate SCAD source ────────────────────────────────────────────────
    scad_source = ""
    try:
        with request_lock(context="text"):
            yield _emit_stream_mode("responding")
            scad_source = _generate_scad(prompt, model, host, history)
    except Exception as e:
        logger.error("[CAD] SCAD generation failed: %s", e, exc_info=True)
        yield {"type": "error", "content": f"CAD generation failed: {e}"}
        return

    if not scad_source:
        yield {"type": "error", "content": "CAD generation returned empty output."}
        return

    # Post-process: fix geometry-variable-assignment hallucination
    scad_fixed = _fix_scad_syntax(scad_source)
    if scad_fixed != scad_source:
        logger.info("[CAD] Patched geometry variable assignments → modules")
        scad_source = scad_fixed

    yield {"type": "log", "content": f"[CAD] Generated {len(scad_source)} chars of OpenSCAD"}

    # ── Persist .scad + render .stl ────────────────────────────────────────
    yield {"type": "status", "content": "🔧 CAD Studio: Rendering STL..."}
    Path(_CAD_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    artifact_id = str(uuid.uuid4())
    stl_path = os.path.join(_CAD_OUTPUT_DIR, f"{artifact_id}.stl")
    scad_path = os.path.join(_CAD_OUTPUT_DIR, f"{artifact_id}.scad")

    # Always save .scad so the user can iterate in OpenSCAD directly
    try:
        Path(scad_path).write_text(scad_source, encoding="utf-8")
    except Exception as e:
        logger.warning("[CAD] Could not save .scad file: %s", e)

    render_ok, render_err = _render_stl(scad_source, stl_path)

    # One retry on syntax errors — feed the error back to the model
    if not render_ok and "syntax error" in render_err.lower():
        logger.info("[CAD] Syntax error on first render — retrying with error feedback")
        yield {"type": "status", "content": "📐 CAD Studio: Fixing syntax error, retrying..."}
        try:
            retried = _generate_scad_retry(prompt, scad_source, render_err, model, host)
            retried = _fix_scad_syntax(retried)
            if retried:
                scad_source = retried
                Path(scad_path).write_text(scad_source, encoding="utf-8")
                render_ok, render_err = _render_stl(scad_source, stl_path)
                if render_ok:
                    logger.info("[CAD] Retry render succeeded")
        except Exception as retry_e:
            logger.warning("[CAD] Retry generation failed: %s", retry_e)

    stl_url: str | None = None

    if render_ok:
        stl_url = f"/files/cad/{artifact_id}.stl"
        yield {"type": "log", "content": f"[CAD] STL rendered → {stl_path}"}
    else:
        logger.warning("[CAD] STL render skipped: %s", render_err)
        yield {"type": "log", "content": f"[CAD] STL render skipped: {render_err}"}

    # ── Emit cad_artifact ──────────────────────────────────────────────────
    yield {
        "type": "cad_artifact",
        "cad_artifact": {
            "id": artifact_id,
            "prompt": user_input,
            "scad_source": scad_source,
            "scad_url": f"/files/cad/{artifact_id}.scad",
            "stl_url": stl_url,           # None when OpenSCAD not installed
            "render_ok": render_ok,
            "render_error": render_err if not render_ok else None,
        },
    }

    AGENT_STATE.labels(agent_name="CAD").set(1)
    WORKFLOW_STEPS.labels(status="success", agent_type="CAD").inc()
