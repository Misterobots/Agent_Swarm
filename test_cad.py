"""
test_cad.py — Standalone CAD pipeline smoke test
================================================
Tests the Ollama → OpenSCAD → STL pipeline independently of Memex.
Also supports reviewing, modifying, and integrating existing STL files.

Generate mode (default):
  python test_cad.py                            # medium-tier tests, localhost:11434
  python test_cad.py --fast                     # single easy test (quick sanity check)
  python test_cad.py --tier hard                # complex geometry tests
  python test_cad.py --tier all                 # every prompt
  python test_cad.py --test rpi4_case           # single named test
  python test_cad.py --list                     # show all available test names
  python test_cad.py --prompt "a 40mm cube"     # one-off custom prompt
  python test_cad.py --host 192.168.2.103       # target Turing's Ollama
  python test_cad.py --scad-only                # skip STL render
  python test_cad.py --view                     # open viewer after render

STL input mode (--input):
  python test_cad.py --input model.stl --mode review
  python test_cad.py --input model.stl --mode review --change "how would I make this lighter?"
  python test_cad.py --input model.stl --mode modify --change "add two M4 holes on the back face, 20mm apart"
  python test_cad.py --input model.stl --mode modify --change "extend the base by 10mm" --view
  python test_cad.py --input part.stl  --mode integrate --change "enclosure with 2mm clearance around this part"

Dependencies for STL analysis (optional, install for richer output):
  pip install trimesh numpy
"""

import argparse
import json
import os
import platform
import re
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL       = "qwen3-coder:30b"

_WIN_OPENSCAD = r"C:\Program Files\OpenSCAD (Nightly)\openscad.exe"
if platform.system() == "Windows" and Path(_WIN_OPENSCAD).exists():
    DEFAULT_OPENSCAD_BIN = _WIN_OPENSCAD
else:
    DEFAULT_OPENSCAD_BIN = os.getenv("OPENSCAD_BIN", "openscad")

OUTPUT_DIR = Path(__file__).parent / "test_cad_output"

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_BASE_SCAD_RULES = """\
CRITICAL OpenSCAD syntax rules:
- Variables hold NUMBERS only: `width = 20;` is valid, `shape = cube(20);` is INVALID
- NEVER write `x = union() { ... }` — this is not valid OpenSCAD and will cause a parse error
- To name a shape, use a module: `module x() { union() { ... } }` then call it with `x();`
- The final line must be a geometry call, e.g. `difference() { ... }` or `mypart();`
- Use for() loops for repeated features (bolt holes, fins, teeth, slots)
- Use $fn = 64 for smooth cylinders; add a `// $fn = 16 for preview` comment
- Position the model flat on the XY plane (Z = 0 at the bottom face)
"""

SYSTEM_PROMPT = f"""\
You are an expert OpenSCAD programmer specialising in FDM 3D-printing-optimised parametric models.
Convert the user's description into a complete, working OpenSCAD (.scad) script.

Hard rules:
- Output ONLY raw OpenSCAD code — no markdown fences, no explanations, no preamble
- Declare ALL configurable dimensions as named variables at the very top
- Include brief // inline comments on each major section and boolean operation
- The file must end with (or render) the complete assembled solid — never leave it headless
- Every measurement is in millimetres; all wall thicknesses ≥ 1.5 mm unless specified
- FDM tolerances: clearance fits 0.2 mm, press fits 0.1 mm, holes 0.2 mm oversize

{_BASE_SCAD_RULES}
If any dimension is underspecified, pick a sensible default and document it with a // comment.
"""

REVIEW_SYSTEM_PROMPT = """\
You are an expert in FDM 3D printing, mechanical design, and printability analysis.
You will receive a structured analysis report of a 3D model (STL file).

Provide a thorough review covering:

1. **Dimensions & Scale** — confirm the size makes sense, flag anything that looks off
2. **Printability** — overhangs requiring supports, flat bottom suitability, bridging spans
3. **Structural integrity** — thin walls, stress concentration points, joint geometry
4. **FDM optimisation** — wall count, layer adhesion direction, feature sizes vs nozzle
5. **Specific improvements** — concrete, actionable suggestions with estimated dimensions

Be specific. Reference actual dimensions from the report. Avoid vague advice.
"""

MODIFY_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert OpenSCAD programmer. The user has an existing 3D model (STL file) they want to modify.

The original STL is stored at:
  {stl_path}

To include it in OpenSCAD, use EXACTLY this import statement:
  import("{stl_path_fwd}");

Original model analysis:
{analysis_text}

Your job:
- Import the original model using the import() path above
- Apply ONLY the modifications the user requests — do not recreate geometry already in the STL
- Use difference() to cut into the model, union() to add material, intersection() for boolean crop
- Output ONLY raw OpenSCAD code — no markdown, no explanation

{base_rules}
"""

INTEGRATE_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert OpenSCAD programmer designing a multi-part assembly.

An existing component (STL) is stored at:
  {stl_path}

To include it in OpenSCAD, use EXACTLY this import statement:
  import("{stl_path_fwd}");

Component analysis:
{analysis_text}

Your job:
- Import the existing component and use it as a reference for the new geometry
- Design the requested surrounding/assembly geometry around it (with appropriate clearances)
- Do NOT modify the imported component itself — create new parts that fit it
- Place all parts side-by-side on the XY plane for printing (or mark assembly separately)
- Output ONLY raw OpenSCAD code — no markdown, no explanation

{base_rules}
"""

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

def _c(code: str, text: str) -> str:
    if platform.system() == "Windows":
        return text
    return f"\033[{code}m{text}\033[0m"

OK   = lambda t: _c("32", t)
FAIL = lambda t: _c("31", t)
INFO = lambda t: _c("36", t)
WARN = lambda t: _c("33", t)
BOLD = lambda t: _c("1",  t)

# ---------------------------------------------------------------------------
# STL analysis
# ---------------------------------------------------------------------------

def _analyze_stl_trimesh(stl_path: Path) -> dict:
    """Rich STL analysis using trimesh + numpy."""
    import trimesh
    import numpy as np

    mesh = trimesh.load(str(stl_path), force="mesh")
    bounds   = mesh.bounds
    dims     = bounds[1] - bounds[0]
    normals  = mesh.face_normals
    n_tris   = len(mesh.faces)

    # Overhangs: faces pointing downward beyond 45°
    overhang_mask  = normals[:, 2] < -0.707
    n_overhangs    = int(np.sum(overhang_mask))

    # Flat bottom: faces nearly horizontal pointing down (suitable print bed face)
    bottom_mask    = normals[:, 2] < -0.98
    n_bottom_flat  = int(np.sum(bottom_mask))

    # Upward-facing flat faces (top surfaces)
    top_mask       = normals[:, 2] > 0.98
    n_top_flat     = int(np.sum(top_mask))

    # Thin-feature proxy: ratio of surface area to volume (high = thin/complex)
    try:
        volume        = float(mesh.volume)
        surface_area  = float(mesh.area)
        sa_vol_ratio  = surface_area / max(volume, 1)
    except Exception:
        volume = surface_area = sa_vol_ratio = None

    return {
        "source":         "trimesh",
        "file":           stl_path.name,
        "file_size_kb":   stl_path.stat().st_size // 1024,
        "triangle_count": n_tris,
        "is_watertight":  bool(mesh.is_watertight),
        "bounding_box": {
            "x_mm": round(float(dims[0]), 2),
            "y_mm": round(float(dims[1]), 2),
            "z_mm": round(float(dims[2]), 2),
        },
        "volume_mm3":      round(volume, 1)       if volume       is not None else None,
        "surface_area_mm2":round(surface_area, 1) if surface_area is not None else None,
        "sa_vol_ratio":    round(sa_vol_ratio, 4) if sa_vol_ratio is not None else None,
        "overhang_faces":  n_overhangs,
        "overhang_pct":    round(100 * n_overhangs / max(n_tris, 1), 1),
        "bottom_flat_faces": n_bottom_flat,
        "top_flat_faces":  n_top_flat,
    }


def _analyze_stl_basic(stl_path: Path) -> dict:
    """Stdlib-only STL parser. Extracts bounding box, triangle count, overhang estimate."""
    raw = stl_path.read_bytes()
    normals: list[tuple] = []
    vertices: list[tuple] = []

    # Detect binary vs ASCII
    is_ascii = raw[:5] == b"solid" and b"\n" in raw[:80]

    if is_ascii:
        text = raw.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("vertex "):
                p = s.split()
                vertices.append((float(p[1]), float(p[2]), float(p[3])))
            elif s.startswith("facet normal "):
                p = s.split()
                normals.append((float(p[2]), float(p[3]), float(p[4])))
    else:
        n_tris = struct.unpack("<I", raw[80:84])[0]
        off = 84
        for _ in range(n_tris):
            nx, ny, nz = struct.unpack("<fff", raw[off:off+12])
            v1 = struct.unpack("<fff", raw[off+12:off+24])
            v2 = struct.unpack("<fff", raw[off+24:off+36])
            v3 = struct.unpack("<fff", raw[off+36:off+48])
            normals.append((nx, ny, nz))
            vertices.extend([v1, v2, v3])
            off += 50

    if not vertices:
        return {"error": "Could not parse STL"}

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    n_over = sum(1 for n in normals if n[2] < -0.707)
    n_tris = len(normals)

    return {
        "source":         "stdlib",
        "file":           stl_path.name,
        "file_size_kb":   stl_path.stat().st_size // 1024,
        "triangle_count": n_tris,
        "is_watertight":  None,
        "bounding_box": {
            "x_mm": round(max(xs) - min(xs), 2),
            "y_mm": round(max(ys) - min(ys), 2),
            "z_mm": round(max(zs) - min(zs), 2),
        },
        "volume_mm3":      None,
        "surface_area_mm2":None,
        "sa_vol_ratio":    None,
        "overhang_faces":  n_over,
        "overhang_pct":    round(100 * n_over / max(n_tris, 1), 1),
        "bottom_flat_faces": None,
        "top_flat_faces":  None,
    }


def analyze_stl(stl_path: Path) -> dict:
    """Analyze an STL file. Uses trimesh if available, falls back to stdlib parser."""
    try:
        result = _analyze_stl_trimesh(stl_path)
        print(INFO("  Analysis : trimesh (full)"))
        return result
    except ImportError:
        print(WARN("  Analysis : trimesh not installed — using basic parser"))
        print(WARN("             pip install trimesh numpy   for richer output"))
        return _analyze_stl_basic(stl_path)
    except Exception as e:
        print(WARN(f"  Analysis : trimesh failed ({e}), falling back to basic parser"))
        return _analyze_stl_basic(stl_path)


def format_analysis(a: dict) -> str:
    """Format analysis dict as an LLM-readable structured report."""
    bb = a.get("bounding_box", {})
    lines = [
        f"File: {a.get('file', 'unknown')}  ({a.get('file_size_kb', '?')} KB)",
        f"Triangles: {a.get('triangle_count', '?'):,}",
        f"Bounding box: {bb.get('x_mm', '?')} mm (W) × {bb.get('y_mm', '?')} mm (D) × {bb.get('z_mm', '?')} mm (H)",
    ]
    if a.get("volume_mm3") is not None:
        lines.append(f"Volume: {a['volume_mm3']:,.1f} mm³  ≈  {a['volume_mm3']/1000:.1f} cm³")
    if a.get("surface_area_mm2") is not None:
        lines.append(f"Surface area: {a['surface_area_mm2']:,.1f} mm²")
    if a.get("is_watertight") is not None:
        lines.append(f"Watertight/manifold: {'YES ✓' if a['is_watertight'] else 'NO ✗ (may not slice cleanly)'}")

    lines += [
        f"Overhang faces (>45°): {a.get('overhang_faces', '?')} ({a.get('overhang_pct', '?')}%)",
    ]
    if a.get("bottom_flat_faces") is not None:
        lines.append(f"Flat bottom faces: {a['bottom_flat_faces']}")
    if a.get("top_flat_faces") is not None:
        lines.append(f"Flat top faces: {a['top_flat_faces']}")
    if a.get("sa_vol_ratio") is not None:
        lines.append(f"Surface/volume ratio: {a['sa_vol_ratio']:.4f}  (higher = thinner/more complex)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCAD post-processor
# ---------------------------------------------------------------------------

_CSG_OPS = r'(?:union|difference|intersection|hull|minkowski|render)'
_ASSIGN_PATTERN = re.compile(
    r'^(\s*)(\w+)\s*=\s*' + _CSG_OPS + r'\s*\(\s*\)\s*\{',
    re.MULTILINE,
)

def fix_scad_syntax(scad: str) -> str:
    """Fix LLM hallucination: `name = union() {` → `module name() {` + call."""
    fixed_names: list[str] = []

    def _sub(m: re.Match) -> str:
        indent, name = m.group(1), m.group(2)
        fixed_names.append(name)
        orig_op = m.group(0).split("=", 1)[1].strip().rstrip("{").strip()
        return f"{indent}module {name}() {{ // (was: {name} = {orig_op})"

    result = _ASSIGN_PATTERN.sub(_sub, scad)
    for name in fixed_names:
        if not re.search(r'\b' + re.escape(name) + r'\s*\(\s*\)\s*;', result):
            result = result.rstrip() + f"\n\n{name}(); // auto-added call\n"
    return result

# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def check_ollama(host: str, model: str) -> tuple[bool, str]:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
            data = json.loads(r.read())
        available = [m["name"] for m in data.get("models", [])]
        if not any(m == model or m.startswith(model.split(":")[0]) for m in available):
            return False, f"Model '{model}' not found. Available: {', '.join(available[:6])}"
        return True, f"Ollama OK — {len(available)} models loaded"
    except Exception as e:
        return False, str(e)


def _stream_ollama(messages: list[dict], host: str, model: str,
                   timeout: int = 180) -> tuple[str, float]:
    """Core Ollama streaming call. Returns (raw_text, elapsed_seconds)."""
    import urllib.request
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.1, "num_predict": 8192},
    }).encode()
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                c = obj.get("message", {}).get("content", "")
                if c:
                    chunks.append(c)
                    sys.stdout.write(".")
                    sys.stdout.flush()
                if obj.get("done"):
                    break
            except Exception:
                pass
    print()
    raw = "".join(chunks).strip()
    for fence in ("```openscad", "```scad", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip(), time.time() - t0


def generate_scad(prompt: str, host: str, model: str) -> tuple[str, float]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    return _stream_ollama(messages, host, model)


def generate_scad_retry(prompt: str, prev_scad: str, error: str,
                        host: str, model: str) -> tuple[str, float]:
    fix_msg = (
        f"The OpenSCAD script above has this error:\n\n{error}\n\n"
        "Please fix it and return ONLY the corrected OpenSCAD code with no markdown fences.\n\n"
        "Reminder: in OpenSCAD, variables hold NUMBERS only — you cannot assign geometry "
        "to a variable. Replace any `name = union() {{ ... }}` with `module name() {{ ... }}` "
        "and add a `name();` call at the end of the file."
    )
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": prompt},
        {"role": "assistant", "content": prev_scad},
        {"role": "user",      "content": fix_msg},
    ]
    return _stream_ollama(messages, host, model)


def generate_review(stl_path: Path, analysis_text: str,
                    question: str | None, host: str, model: str) -> tuple[str, float]:
    """Ask the LLM to review/critique the STL based on its analysis stats."""
    user_content = f"Here is the analysis report for the STL file:\n\n{analysis_text}"
    if question:
        user_content += f"\n\nSpecific question from the user: {question}"
    else:
        user_content += "\n\nPlease provide a full critique covering printability, structure, and improvements."
    messages = [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]
    # Reviews are text, allow higher token budget
    import urllib.request
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.3, "num_predict": 4096},
    }).encode()
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                c = obj.get("message", {}).get("content", "")
                if c:
                    chunks.append(c)
                    sys.stdout.write(".")
                    sys.stdout.flush()
                if obj.get("done"):
                    break
            except Exception:
                pass
    print()
    return "".join(chunks).strip(), time.time() - t0


def generate_modification_scad(stl_path: Path, analysis_text: str,
                                change_request: str, mode: str,
                                host: str, model: str) -> tuple[str, float]:
    """Generate SCAD that imports the STL and applies the requested changes."""
    # OpenSCAD needs forward slashes even on Windows
    stl_fwd = str(stl_path.resolve()).replace("\\", "/")

    template = INTEGRATE_SYSTEM_PROMPT_TEMPLATE if mode == "integrate" else MODIFY_SYSTEM_PROMPT_TEMPLATE
    system = template.format(
        stl_path=stl_path.resolve(),
        stl_path_fwd=stl_fwd,
        analysis_text=analysis_text,
        base_rules=_BASE_SCAD_RULES,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": change_request},
    ]
    return _stream_ollama(messages, host, model)

# ---------------------------------------------------------------------------
# OpenSCAD render
# ---------------------------------------------------------------------------

def render_stl(scad_source: str, stl_path: Path, openscad_bin: str) -> tuple[bool, str, float]:
    with tempfile.NamedTemporaryFile(suffix=".scad", delete=False, mode="w",
                                     encoding="utf-8") as tf:
        tf.write(scad_source)
        scad_tmp = tf.name
    try:
        t0 = time.time()
        result = subprocess.run(
            [openscad_bin, "-o", str(stl_path), scad_tmp],
            capture_output=True, text=True, timeout=120,
        )
        elapsed = time.time() - t0
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error").strip()[:600]
            return False, err, elapsed
        warnings = [l for l in (result.stderr or "").splitlines()
                    if any(kw in l.lower() for kw in ("warning", "cgal", "manifold"))]
        if warnings:
            print(WARN("  ⚠ OpenSCAD warnings:\n    " + "\n    ".join(warnings[:5])))
        return True, "", elapsed
    except FileNotFoundError:
        return False, f"openscad binary not found: '{openscad_bin}'", 0.0
    except subprocess.TimeoutExpired:
        return False, "render timed out (>120s)", 120.0
    except Exception as e:
        return False, str(e), 0.0
    finally:
        try: os.unlink(scad_tmp)
        except Exception: pass

# ---------------------------------------------------------------------------
# STL input mode runner
# ---------------------------------------------------------------------------

def run_stl_input(stl_path: Path, mode: str, change: str | None,
                  host: str, model: str, openscad_bin: str,
                  scad_only: bool, out_dir: Path,
                  view: bool, port: int) -> bool:

    if not stl_path.exists():
        print(FAIL(f"File not found: {stl_path}"))
        return False

    mode_badge = {"review": "🔍", "modify": "✏️", "integrate": "🧩"}.get(mode, "")
    print(BOLD(f"\n── {mode_badge} STL {mode.upper()} ──────────────────────────────"))
    print(f"  File : {stl_path}")
    print(f"  Mode : {mode}")
    if change:
        print(f"  Task : {change[:100]}{'…' if len(change or '') > 100 else ''}")

    # ── Analyse ─────────────────────────────────────────────────────────────
    print(f"\n{INFO('Analysing STL...')}")
    analysis = analyze_stl(stl_path)
    if "error" in analysis:
        print(FAIL(f"  Analysis failed: {analysis['error']}"))
        return False

    analysis_text = format_analysis(analysis)
    print(f"\n{BOLD('Model report:')}")
    for line in analysis_text.splitlines():
        print(f"  {line}")

    # ── REVIEW mode ──────────────────────────────────────────────────────────
    if mode == "review":
        print(f"\n{INFO(f'Generating review ({model})...')} ", end="", flush=True)
        try:
            review, elapsed = generate_review(stl_path, analysis_text, change, host, model)
        except Exception as e:
            print(FAIL(f"  Review generation failed: {e}"))
            return False

        print(OK(f"  ✓ Review in {elapsed:.1f}s"))
        print()
        print(BOLD("=" * 60))
        print(review)
        print(BOLD("=" * 60))

        # Save review
        ts = int(time.time())
        review_path = out_dir / f"review_{stl_path.stem}_{ts}.md"
        review_path.write_text(
            f"# Review: {stl_path.name}\n\n## Analysis\n\n```\n{analysis_text}\n```\n\n## Review\n\n{review}\n",
            encoding="utf-8",
        )
        print(f"\n  Saved: {review_path}")
        return True

    # ── MODIFY / INTEGRATE mode ──────────────────────────────────────────────
    if not change:
        print(FAIL("  --change is required for modify/integrate mode."))
        print("  Example: --change \"add a 5mm hole centred on the top face\"")
        return False

    print(f"\n{INFO(f'Generating {mode} SCAD ({model})...')} ", end="", flush=True)
    try:
        scad, gen_elapsed = generate_modification_scad(
            stl_path, analysis_text, change, mode, host, model
        )
    except Exception as e:
        print(FAIL(f"  SCAD generation failed: {e}"))
        return False

    scad = fix_scad_syntax(scad)
    if not scad:
        print(FAIL("  Empty output from model."))
        return False

    ts = int(time.time())
    stem = f"{mode}_{stl_path.stem}_{ts}"
    scad_path = out_dir / f"{stem}.scad"
    scad_path.write_text(scad, encoding="utf-8")
    print(OK(f"  ✓ Generated {scad.count(chr(10))+1} lines in {gen_elapsed:.1f}s"))
    print(f"    → {scad_path}")

    # Check the import() reference made it in
    stl_fwd = str(stl_path.resolve()).replace("\\", "/")
    if "import(" not in scad:
        print(WARN("  ⚠ import() not found in generated SCAD — model may have ignored the STL"))

    if scad_only:
        return True

    # Render
    stl_out = out_dir / f"{stem}.stl"
    attempt = 0
    scad_current = scad

    while attempt < 2:
        attempt += 1
        label = "" if attempt == 1 else " (retry)"
        print(f"Rendering{label} ", end="", flush=True)
        ok, err, render_elapsed = render_stl(scad_current, stl_out, openscad_bin)
        if ok:
            size_kb = stl_out.stat().st_size // 1024
            print(OK(f"  ✓ {render_elapsed:.1f}s  ({size_kb} KB)"))
            print(f"    → {stl_out}")
            scad_path.write_text(scad_current, encoding="utf-8")
            if view:
                _launch_viewer([(stem, True)], port, custom_stl=stl_out)
            return True

        print(FAIL(f"\n  ✗ Render failed: {err[:200]}"))

        if attempt == 1 and "syntax error" in err.lower():
            print(WARN("  ↺ Retrying with error feedback..."))
            try:
                print(f"  Generating fix ({model}) ", end="", flush=True)
                fixed_scad, fix_elapsed = _stream_ollama([
                    {"role": "system",    "content": SYSTEM_PROMPT},
                    {"role": "user",      "content": change},
                    {"role": "assistant", "content": scad_current},
                    {"role": "user",      "content":
                        f"OpenSCAD error: {err}\n\nFix the syntax and return only corrected code."},
                ], host, model)
                fixed_scad = fix_scad_syntax(fixed_scad)
                if fixed_scad:
                    scad_current = fixed_scad
                    continue
            except Exception as retry_e:
                print(FAIL(f"  Retry failed: {retry_e}"))
        break

    # Print SCAD for debugging
    print(INFO("\n  --- Generated SCAD (first 40 lines) ---"))
    for i, line in enumerate(scad_current.splitlines()[:40], 1):
        print(f"  {i:3d}  {line}")
    return False

# ---------------------------------------------------------------------------
# Generate-mode test runner
# ---------------------------------------------------------------------------

TEST_LIBRARY = [
    # ── Easy ────────────────────────────────────────────────────────────────
    (
        "simple_cube", "easy",
        "A 30 mm × 30 mm × 30 mm cube with 2 mm chamfered edges on all top corners.",
    ),
    (
        "mounting_bracket", "easy",
        "A flat wall-mounting bracket: 60 mm wide, 40 mm tall, 4 mm thick. "
        "Two M4 bolt holes (4.2 mm dia) spaced 40 mm apart, centred vertically. "
        "A triangular gusset (40 mm wide × 30 mm tall × 4 mm thick) reinforces the back.",
    ),
    (
        "phone_stand", "easy",
        "A phone stand with a 15-degree lean-back angle, 80 mm wide × 60 mm deep base, "
        "3 mm wall thickness, 12 mm lip at the bottom front edge to cradle the phone, "
        "and a 10 mm wide × 4 mm tall cable pass-through slot centred in the base.",
    ),
    # ── Medium ──────────────────────────────────────────────────────────────
    (
        "heatsink", "medium",
        "A passive heatsink for a TO-220 package. "
        "Base: 40 mm × 25 mm × 3 mm. "
        "10 vertical fins, each 18 mm tall × 1.2 mm thick, evenly spaced across the 40 mm width. "
        "Two M3 mounting holes (3.2 mm dia, countersunk 6 mm × 1.5 mm) centred 30 mm apart on the base. "
        "Round all fin tips with a 0.6 mm radius.",
    ),
    (
        "snap_box", "medium",
        "A rectangular snap-lid storage box for small electronics. "
        "Inner cavity: 65 mm × 45 mm × 35 mm. Wall: 2 mm. Floor: 2 mm. "
        "The lid fits over a 1 mm raised rim with four snap tabs (2 mm wide × 3 mm tall, "
        "45-degree lead-in chamfer) centred on each wall. "
        "Parametric variables: inner_w, inner_d, inner_h, wall, snap_h. "
        "Place the box and lid side-by-side (10 mm gap) on the XY plane.",
    ),
    (
        "cable_clip", "medium",
        "A snap-fit cable management clip for 20 × 20 V-slot aluminium extrusion "
        "(T-slot width 6.2 mm, depth 5.6 mm). "
        "Clip body: 32 mm wide, holds cable bundle up to 14 mm dia. "
        "1.5 mm flex hinge on one side. T-nut foot: 6 mm wide × 5.4 mm tall × 8 mm long. "
        "Parametric: cable_dia, slot_w, slot_d, body_w.",
    ),
    (
        "vslot_bracket", "medium",
        "A 90-degree corner bracket for 20 × 20 V-slot extrusions. "
        "Each arm: 40 mm long × 20 mm wide × 4 mm thick. "
        "Each arm: centred 5 mm × 28 mm slot + M5 T-nut counterbores at each end. "
        "Inside corner fillet R5 mm. Prints flat.",
    ),
    # ── Hard ────────────────────────────────────────────────────────────────
    (
        "rpi4_case", "hard",
        "Minimal open-top enclosure for Raspberry Pi 4 Model B. "
        "Board: 85 mm × 56 mm. Standoff height: 3 mm. M2.5 hole pattern: 58 mm × 49 mm. "
        "Wall: 2 mm. Floor: 2 mm. Outer corner R3 mm. No lid. "
        "Port cutouts: GPIO 58 mm wide slot left wall; USB-C 10×4.5 mm left short wall; "
        "micro-HDMI ×2 8×4 mm left short wall; USB-A ×2 16×16 mm right short wall; "
        "Ethernet 18×14 mm right short wall; 3.5 mm audio 7 mm dia right short wall. "
        "Parametric board_w, board_d, wall, standoff_h.",
    ),
    (
        "gt2_pulley", "hard",
        "A GT2 timing belt pulley with 20 teeth. "
        "Belt pitch: 2 mm. Tooth height: 0.75 mm. Tooth width at base: 1.2 mm (trapezoidal). "
        "Pitch diameter: 20 × 2 / PI ≈ 12.73 mm. "
        "Two flanges: 1.5 mm thick, 1.5 mm proud of tooth OD. "
        "Hub: 15 mm long, 12 mm OD. Bore: 5 mm with 1.8 mm keyway. "
        "One M3 grub-screw hole (3.2 mm dia, radial, hub midpoint). "
        "Use for() loop over 20 tooth slots. "
        "Define inside a module named 'gt2_pulley' and call it at the end. "
        "Parametric: teeth, pitch, bore_d, hub_od, hub_len, flange_t.",
    ),
    (
        "parametric_enclosure", "hard",
        "Fully parametric electronics enclosure with lid. "
        "Default inner cavity: 100 mm × 70 mm × 30 mm. Wall: 2.5 mm. Floor/lid: 2 mm. "
        "Four M3 insert bosses (OD 6 mm, 5 mm tall) at inner corners. "
        "Lid clips via four snap hooks (3 mm wide, 4 mm tall, 1 mm barb) on long walls. "
        "Vented lid: 3×3 grid of 4 mm dia holes. "
        "One 22 mm dia power cutout and one 10×8 mm data port cutout on opposite short walls. "
        "Both parts print flat. Define box and lid as separate modules, render side-by-side. "
        "Parametric: inner_w, inner_d, inner_h, wall, lid_h.",
    ),
]

PRIMITIVES = (
    "cube", "sphere", "cylinder", "polyhedron", "import",
    "linear_extrude", "rotate_extrude", "hull", "minkowski",
    "union", "difference", "intersection", "for", "module",
)

def run_test(name: str, tier: str, prompt: str, host: str, model: str,
             openscad_bin: str, scad_only: bool, out_dir: Path) -> bool:
    badge = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(tier, "")
    print(BOLD(f"\n── {badge} {name}  [{tier}] ──────────────────────────────"))
    print(INFO(f"Prompt: {prompt[:120]}{'…' if len(prompt) > 120 else ''}"))

    print(f"Generating ({model}) ", end="", flush=True)
    try:
        scad, gen_elapsed = generate_scad(prompt, host, model)
    except Exception as e:
        print(FAIL(f"  GENERATION FAILED: {e}"))
        return False

    if not scad:
        print(FAIL("  GENERATION FAILED: empty output"))
        return False

    fixed = fix_scad_syntax(scad)
    if fixed != scad:
        print(WARN("  ⚙ Patched geometry variable assignments → modules"))
        scad = fixed

    scad_path = out_dir / f"{name}.scad"
    scad_path.write_text(scad, encoding="utf-8")

    lines = scad.count("\n") + 1
    print(OK(f"  ✓ Generated {lines} lines in {gen_elapsed:.1f}s"))
    print(f"    → {scad_path}")

    found = [p for p in PRIMITIVES if p in scad]
    print(INFO(f"  Primitives : {', '.join(found) if found else 'NONE (suspicious)'}"))

    if scad_only:
        return True

    stl_path = out_dir / f"{name}.stl"
    attempt = 0
    scad_for_render = scad

    while attempt < 2:
        attempt += 1
        label = "" if attempt == 1 else " (retry)"
        print(f"Rendering STL{label} ", end="", flush=True)
        ok, err, render_elapsed = render_stl(scad_for_render, stl_path, openscad_bin)
        if ok:
            size_kb = stl_path.stat().st_size // 1024
            print(OK(f"  ✓ {render_elapsed:.1f}s  ({size_kb} KB)"))
            print(f"    → {stl_path}")
            scad_path.write_text(scad_for_render, encoding="utf-8")
            return True

        print(FAIL(f"\n  ✗ Render failed: {err[:200]}"))

        if attempt == 1 and "syntax error" in err.lower():
            print(WARN("  ↺ Retrying with error feedback..."))
            try:
                print(f"  Generating fix ({model}) ", end="", flush=True)
                retried, _ = generate_scad_retry(prompt, scad_for_render, err, host, model)
                retried = fix_scad_syntax(retried)
                if retried:
                    scad_for_render = retried
                    (out_dir / f"{name}_retry.scad").write_text(retried, encoding="utf-8")
                    continue
            except Exception as retry_e:
                print(FAIL(f"  Retry failed: {retry_e}"))
        break

    print(INFO("\n  --- Generated SCAD (first 40 lines) ---"))
    for i, line in enumerate(scad_for_render.splitlines()[:40], 1):
        print(f"  {i:3d}  {line}")
    return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CAD pipeline smoke test + STL reviewer/modifier")
    parser.add_argument("--host",         default=DEFAULT_OLLAMA_HOST,   help="Ollama base URL")
    parser.add_argument("--model",        default=DEFAULT_MODEL,         help="Ollama model tag")
    parser.add_argument("--openscad-bin", default=DEFAULT_OPENSCAD_BIN,  help="Path to openscad binary")
    parser.add_argument("--view",         action="store_true",           help="Open viewer after render")
    parser.add_argument("--port",         type=int, default=0,           help="HTTP port for --view")

    # Generate mode args
    parser.add_argument("--prompt",    default=None,  help="One-off generate prompt")
    parser.add_argument("--scad-only", action="store_true", help="Skip STL render")
    parser.add_argument("--fast",      action="store_true", help="One quick easy test")
    parser.add_argument("--tier",      default="medium",
                        choices=["easy", "medium", "hard", "all"],
                        help="Difficulty tier (default: medium)")
    parser.add_argument("--test",  default=None, help="Run a single named test (see --list)")
    parser.add_argument("--list",  action="store_true", help="Print all test names and exit")

    # STL input mode args
    parser.add_argument("--input",  default=None, metavar="STL",
                        help="Path to an existing STL file to review or modify")
    parser.add_argument("--mode",   default="modify",
                        choices=["review", "modify", "integrate"],
                        help="What to do with --input (default: modify)")
    parser.add_argument("--change", default=None,
                        help="Modification/integration request for --mode modify|integrate, "
                             "or a focused question for --mode review")

    args = parser.parse_args()

    # ── --list ───────────────────────────────────────────────────────────────
    if args.list:
        print(BOLD("\nAvailable tests:\n"))
        for name, tier, prompt in TEST_LIBRARY:
            badge = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(tier, "")
            print(f"  {badge}  {name:<26}  [{tier}]")
            print(f"       {prompt[:90]}{'…' if len(prompt) > 90 else ''}\n")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    print(BOLD("\n=== CAD Pipeline ==="))
    print(f"Ollama   : {args.host}")
    print(f"Model    : {args.model}")
    print(f"OpenSCAD : {args.openscad_bin}")
    print(f"Output   : {OUTPUT_DIR}")

    # ── Pre-flight ───────────────────────────────────────────────────────────
    print(BOLD("\nPre-flight checks"))
    ok, msg = check_ollama(args.host, args.model)
    print(f"  Ollama   : {OK(msg) if ok else FAIL(msg)}")
    if not ok:
        sys.exit(1)

    needs_openscad = not args.scad_only and args.mode != "review"
    if needs_openscad:
        try:
            r = subprocess.run([args.openscad_bin, "--version"],
                               capture_output=True, text=True, timeout=10)
            ver = (r.stdout or r.stderr or "").strip().splitlines()[0]
            print(f"  OpenSCAD : {OK(ver)}")
        except FileNotFoundError:
            print(FAIL(f"  OpenSCAD : NOT FOUND at '{args.openscad_bin}'"))
            sys.exit(1)
        except Exception as e:
            print(FAIL(f"  OpenSCAD : {e}"))
            sys.exit(1)

    # ── STL input mode ───────────────────────────────────────────────────────
    if args.input:
        stl_path = Path(args.input).resolve()
        success = run_stl_input(
            stl_path=stl_path,
            mode=args.mode,
            change=args.change,
            host=args.host,
            model=args.model,
            openscad_bin=args.openscad_bin,
            scad_only=args.scad_only,
            out_dir=OUTPUT_DIR,
            view=args.view,
            port=args.port,
        )
        sys.exit(0 if success else 1)

    # ── Generate mode ────────────────────────────────────────────────────────
    if args.prompt:
        prompts = [("custom", "easy", args.prompt)]
    elif args.fast:
        prompts = [TEST_LIBRARY[0]]
    elif args.test:
        match = [(n, t, p) for n, t, p in TEST_LIBRARY if n == args.test]
        if not match:
            print(FAIL(f"Unknown test '{args.test}'. Run --list to see available tests."))
            sys.exit(1)
        prompts = match
    elif args.tier == "all":
        prompts = TEST_LIBRARY
    else:
        prompts = [(n, t, p) for n, t, p in TEST_LIBRARY if t == args.tier]

    print(f"\nRunning {len(prompts)} test(s):")
    for n, t, _ in prompts:
        badge = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(t, "")
        print(f"  {badge} {n}")

    results = []
    for name, tier, prompt in prompts:
        passed = run_test(
            name, tier, prompt,
            host=args.host, model=args.model,
            openscad_bin=args.openscad_bin,
            scad_only=args.scad_only,
            out_dir=OUTPUT_DIR,
        )
        results.append((name, passed))

    print(BOLD("\n=== Results ==="))
    passed_count = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  [{OK('PASS') if ok else FAIL('FAIL')}] {name}")
    print(f"\n{passed_count}/{len(results)} passed")

    if args.view and not args.scad_only:
        _launch_viewer(results, args.port)

    if passed_count < len(results):
        sys.exit(1)


def _launch_viewer(results: list, port: int, custom_stl: Path | None = None):
    import http.server, socketserver, threading, webbrowser, socket, shutil

    repo_root  = Path(__file__).parent
    viewer_src = repo_root / "viewer.html"
    if not viewer_src.exists():
        print(FAIL("  viewer.html not found — skipping viewer launch"))
        return

    viewer_dst = OUTPUT_DIR / "viewer.html"
    shutil.copy2(viewer_src, viewer_dst)

    if port == 0:
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    os.chdir(OUTPUT_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None
    httpd = socketserver.TCPServer(("", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    if custom_stl:
        stl_name = custom_stl.name
    else:
        successful = [n for n, ok in results if ok]
        stl_name = f"{successful[-1]}.stl" if successful else None

    url = (f"http://localhost:{port}/viewer.html?file={stl_name}"
           if stl_name else f"http://localhost:{port}/viewer.html")

    print(INFO(f"\n  Viewer : {url}"))
    print("  Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        httpd.shutdown()
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
