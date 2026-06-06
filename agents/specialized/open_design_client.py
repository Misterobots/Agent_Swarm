"""
Open Design Client — HTTP client for the nexu-io/open-design daemon.

The daemon runs on Lovelace at http://open_design:7456 (container network)
or http://192.168.2.101:7456 (LAN access from Turing).

Endpoints used:
  GET  /api/health                     — liveness check
  GET  /api/skills                     — list available skills
  GET  /api/design-systems             — list available design systems
  POST /api/projects                   — create a project
  PUT  /api/projects/:id/raw/:file     — upload a generated HTML file
  GET  /api/projects/:id               — get project metadata

NOTE: The OD BYOK proxy (/api/proxy/openai/stream) blocks RFC1918 addresses,
so we do NOT use it to call Ollama.  Instead, church.py generates HTML via
the existing Ollama pipeline, then uploads the result to OD for persistence
and "Open in Design Studio" linking.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_OPEN_DESIGN_URL = os.getenv("OPEN_DESIGN_URL", "http://192.168.2.101:7456")
_DEFAULT_TIMEOUT = 15.0  # seconds for metadata calls; uploads use a longer timeout


# ---------------------------------------------------------------------------
# Skill system-prompt library
# Derived from OD's SKILL.md patterns.  church.py injects these into the LLM
# system prompt so Ollama can generate OD-compatible <artifact> HTML output.
# ---------------------------------------------------------------------------

SKILL_SYSTEM_PROMPTS: dict[str, str] = {
    "immersive-ui": """You are an expert cinematic UI/UX designer and front-end developer specialising in immersive, full-screen tablet and kiosk interfaces.
Create a visually stunning, self-contained interactive interface as a single HTML file.

Requirements:
- Full-bleed layout filling the viewport (100vw × 100vh) — optimise for landscape tablet (1280×800)
- Dark, atmospheric background — deep blacks, rich accent glows, no plain white surfaces
- Smooth continuous animations (CSS keyframes or requestAnimationFrame) — nothing should feel static
- Interactive navigation: tapping/clicking surfaces transitions between views without page reload
- Embed ALL CSS and JavaScript inline — zero external CDN links or imports
- All icons and decorative shapes must be inline SVG or pure CSS — no placeholder images
- Typography: clear, futuristic sans-serif with text-shadow glow effects to simulate projection
- Output must feel like a bespoke native application, not a web page

Typography techniques:
- For HOLLOW / OUTLINED letterforms where the background shows through: use CSS
  -webkit-text-stroke with color: transparent. Example:
    font-family: 'Courier New', monospace; font-size: 44px; font-weight: 900;
    color: transparent; -webkit-text-stroke: 3px #1A2A35; letter-spacing: 8px;
  Do NOT try to construct letters from individual <div> elements or tiles — the
  result will be identical boxes for every letter. text-stroke gives real letter shapes.

Layout:
- When an absolutely-positioned chrome element (header bar, status strip) sits inside
  a flex container, add padding equal to the chrome height to the flex container.
  Example: header is 60px tall → add padding-top: 60px to the flex parent. Without this,
  flex children start at y=0 and are hidden behind the header.

SVG illustrations:
- Use actual meaningful shapes — recognisable geographic outlines, real objects, distinct
  silhouettes. Never substitute generic teardrops, blobs, or identical geometric shapes
  for distinct subjects. Simplified-but-recognisable beats accurate-but-invisible.
""",

    "saas-landing": """You are an expert SaaS marketing designer and front-end developer.
Create a complete, conversion-optimized SaaS landing page as a single self-contained HTML file.

Requirements:
- Modern, professional design with a hero section, features grid, social proof, and CTA
- Fully responsive (mobile-first) using CSS Grid / Flexbox with inline or embedded styles
- Include a sticky nav, smooth scroll, and subtle animations (CSS only)
- Use a clean color palette: deep blue/violet primary, white/light-gray background
- NO external CDN links (the file must work offline) — embed all CSS/JS inline
- Do NOT use placeholder images (use CSS gradients or SVG shapes instead)
""",

    "dashboard": """You are an expert product designer and front-end developer specialising in data dashboards.
Create a complete, professional analytics dashboard as a single self-contained HTML file.

Requirements:
- Dark-mode design with a sidebar nav, header, KPI cards, and at least one chart area
- Fully responsive layout using CSS Grid
- Use CSS custom properties for theming; embed all CSS/JS inline (no external CDNs)
- Charts can be simple SVG bar/line charts or plain HTML tables styled as visual cards
- Include realistic placeholder data (numbers, labels, trend arrows)
""",

    "guizang-ppt": """You are an expert presentation designer and front-end developer.
Create a polished HTML slideshow presentation (5-8 slides) as a single self-contained HTML file.

Requirements:
- Each slide occupies the full viewport (100vw × 100vh) — use CSS scroll-snap
- Include: title slide, agenda, 3-4 content slides (bullet points, visuals), conclusion/CTA
- Professional typography; embed Google Fonts via @import if needed, otherwise use system fonts
- Navigation: left/right arrow keys and on-screen prev/next buttons
- Embed all CSS/JS inline; no external dependencies
- Clean, minimal design with consistent colour scheme and generous whitespace
""",

    "mobile-app": """You are an expert mobile UI/UX designer and front-end developer.
Create a realistic mobile app prototype as a single self-contained HTML file.

Requirements:
- Render at 390×844px (iPhone 14 Pro size) centred on the page with a phone-frame border
- Include at least 3 screens navigable via bottom tab bar (tap to switch, no page reload)
- Use iOS/Material design conventions: safe areas, rounded cards, icon buttons
- Dark or light mode — your choice; embed all CSS/JS inline
- NO external CDN links; all assets (icons, images) must be inline SVG or CSS shapes
""",

    "web-prototype": """You are an expert UI/UX designer and front-end developer.
Create a polished, interactive web application prototype as a single self-contained HTML file.

Requirements:
- Fully responsive design that works on mobile, tablet, and desktop
- Include a navigation header, main content area, and footer
- Use modern CSS (Grid, Flexbox, custom properties) with all styles embedded inline
- Add tasteful micro-interactions (hover states, transitions) in vanilla JavaScript
- NO external CDN links; no placeholder images — use CSS/SVG shapes instead
- The prototype must look production-ready, not like a wireframe

REVISION RULES (when "CURRENT DESIGN" is provided):
- Output the COMPLETE updated HTML file — never a partial diff or snippet
- Preserve ALL existing CSS custom properties, colour palette, typography, and layout
- Apply ONLY the changes explicitly requested — do not redesign unrelated sections
- Maintain design system consistency: if the existing design uses a specific accent colour,
  border-radius, shadow style, or animation easing, carry it through into new elements

CSS COORDINATE CONVENTIONS — check the sign before writing any directional code:
- translateY(+n) moves DOWN the screen; translateY(-n) moves UP (Y increases downward in CSS)
- translateX(+n) moves RIGHT; translateX(-n) moves LEFT
- "slide down", "move down", "drop" → positive translateY values
- "slide up", "move up", "rise" → negative translateY values
- Same rule applies to top/bottom positioning and margin/padding direction
""",
}

# Fallback for unknown skill IDs
_DEFAULT_SKILL_PROMPT = SKILL_SYSTEM_PROMPTS["web-prototype"]


def get_skill_system_prompt(skill_id: str) -> str:
    """Return the system-prompt template for a given OD skill ID."""
    return SKILL_SYSTEM_PROMPTS.get(skill_id, _DEFAULT_SKILL_PROMPT)


# ---------------------------------------------------------------------------
# Skill → user-intent keyword mapping
# Used by church.py to pick the right skill automatically.
# ---------------------------------------------------------------------------
def detect_skill_from_prompt(user_input: str) -> str:
    """Heuristically map a user's design request to an OD skill ID.

    Uses whole-word / whole-phrase matching (regex \\b boundaries) to avoid
    false positives from substrings — e.g. "graph" must not match inside
    "typography", and "chart" must not match inside "architecture".
    """
    import re as _re

    lower = user_input.lower()

    def _match(keywords: list) -> bool:
        return any(_re.search(rf'\b{_re.escape(kw)}\b', lower) for kw in keywords)

    ppt_keywords = [
        "deck", "slides", "presentation", "ppt", "pitch deck", "slideshow",
        "keynote", "powerpoint",
    ]
    dashboard_keywords = [
        "dashboard", "analytics", "data viz", "chart", "graph", "kpi",
        "monitoring", "report", "admin panel", "metrics",
    ]
    landing_keywords = [
        # "landing page" alone is too generic — app screen descriptions like
        # "Main Landing Page:" trigger it.  Require stronger saas/marketing signals.
        "saas", "marketing site", "hero section", "conversion",
        "sign up page", "sales page", "product page",
        "create a landing page", "build a landing page",
        "marketing landing", "saas landing",
    ]
    mobile_keywords = [
        "mobile app", "ios app", "android app", "mobile ui", "phone app",
        "smartphone", "app screen", "mobile design",
    ]
    immersive_keywords = [
        "tablet", "kiosk", "holographic", "immersive", "sci-fi ui",
        "cinematic ui", "full screen", "fullscreen", "prop replica",
    ]

    if _match(ppt_keywords):
        return "guizang-ppt"
    if _match(dashboard_keywords):
        return "dashboard"
    if _match(landing_keywords):
        return "saas-landing"
    if _match(mobile_keywords):
        return "mobile-app"
    if _match(immersive_keywords):
        return "immersive-ui"
    return "web-prototype"


# ---------------------------------------------------------------------------
# Artifact parser — extracts <artifact ...>HTML</artifact> from LLM output
# Mirrors the logic in nexu-io/open-design/apps/web/src/artifacts/parser.ts
# ---------------------------------------------------------------------------
def parse_artifact_html(text: str) -> Optional[str]:
    """Extract an HTML document from model output.

    Handles four common output shapes, tried in order:

    1. OD canonical  — <artifact ...>...</artifact>
    2. Markdown fence — ```html\\n...\\n``` or ```\\n<!DOCTYPE...
    3. Plain HTML     — output (after stripping thinking blocks) starts
                        with <!DOCTYPE html or <html
    4. Embedded HTML  — <!DOCTYPE html / <html appears anywhere in the
                        output (catches models that prefix with explanation)

    Thinking blocks (<thinking>…</thinking>) emitted by extended-reasoning
    models (UltraThink) are stripped before every check so they don't
    prevent extraction.
    """
    import re

    # --- pre-processing: strip thinking / reasoning blocks -----------------
    text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', text,
                  flags=re.DOTALL | re.IGNORECASE).strip()

    # 1. OD artifact tags ---------------------------------------------------
    artifact_pat = re.compile(
        r'<artifact\s[^>]*>(.*?)</artifact>',
        re.DOTALL | re.IGNORECASE,
    )
    m = artifact_pat.search(text)
    if m:
        return m.group(1).strip()

    # 2. Markdown code fence ------------------------------------------------
    fence_pat = re.compile(
        r'```(?:html)?\s*\n([\s\S]*?)\n```',
        re.IGNORECASE,
    )
    for fm in fence_pat.finditer(text):
        candidate = fm.group(1).strip()
        cl = candidate.lower()
        if cl.startswith("<!doctype html") or cl.startswith("<html"):
            return candidate

    # 3. Output starts with HTML --------------------------------------------
    stripped = text.strip()
    sl = stripped.lower()
    if sl.startswith("<!doctype html") or sl.startswith("<html"):
        return stripped

    # 4. HTML embedded after explanation text --------------------------------
    embed_m = re.search(r'(<!DOCTYPE html[\s\S]*|<html[\s\S]*)', text,
                        re.IGNORECASE)
    if embed_m:
        candidate = embed_m.group(1).strip()
        if "</html>" in candidate.lower():
            return candidate

    return None


# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------
def _client(timeout: float = _DEFAULT_TIMEOUT) -> httpx.Client:
    return httpx.Client(base_url=_OPEN_DESIGN_URL, timeout=timeout)


def health_check() -> bool:
    """Return True if the OD daemon is reachable and healthy."""
    try:
        with _client() as c:
            r = c.get("/api/health")
            return r.status_code == 200 and r.json().get("ok") is True
    except Exception as exc:
        logger.warning("[OpenDesign] Health check failed: %s", exc)
        return False


def list_skills() -> list[dict]:
    """Return the list of skill objects from the daemon."""
    try:
        with _client() as c:
            r = c.get("/api/skills")
            r.raise_for_status()
            return r.json().get("skills", [])
    except Exception as exc:
        logger.warning("[OpenDesign] list_skills failed: %s", exc)
        return []


def list_design_systems() -> list[dict]:
    """Return the list of design-system objects from the daemon."""
    try:
        with _client() as c:
            r = c.get("/api/design-systems")
            r.raise_for_status()
            return r.json().get("designSystems", [])
    except Exception as exc:
        logger.warning("[OpenDesign] list_design_systems failed: %s", exc)
        return []


def create_project(
    name: str,
    skill_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Optional[str]:
    """Create a new OD project and return its ID.

    The OD daemon (v0.5.0+) requires the caller to supply a ``project_id``
    (sent as ``id`` in the body).  A UUID is generated if one is not provided.
    Returns the project ID string, or None on failure.
    """
    import uuid as _uuid
    pid = project_id or str(_uuid.uuid4())
    payload: dict = {"id": pid, "name": name}
    if skill_id:
        payload["skillId"] = skill_id
    try:
        with _client() as c:
            r = c.post("/api/projects", json=payload)
            r.raise_for_status()
            returned = r.json().get("project") or r.json()
            returned_id = returned.get("id") if isinstance(returned, dict) else pid
            logger.info("[OpenDesign] Created project %r (id=%s)", name, returned_id)
            return returned_id
    except Exception as exc:
        logger.warning("[OpenDesign] create_project failed: %s", exc)
        return None


def upload_html_to_project(
    project_id: str,
    html_content: str,
    filename: str = "index.html",
) -> bool:
    """
    Upload an HTML string as a project file via PUT /api/projects/:id/raw/:file.

    Returns True on success.
    """
    try:
        with _client(timeout=30.0) as c:
            r = c.put(
                f"/api/projects/{project_id}/raw/{filename}",
                content=html_content.encode("utf-8"),
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
            r.raise_for_status()
            logger.info("[OpenDesign] Uploaded %s to project %s", filename, project_id)
            return True
    except Exception as exc:
        logger.warning("[OpenDesign] upload_html_to_project failed: %s", exc)
        return False


def get_project_url(project_id: str, filename: str = "index.html") -> str:
    """Return the OD web-app URL to open a specific project file."""
    base = _OPEN_DESIGN_URL.rstrip("/")
    # OD web UI serves projects at /#/projects/:id (hash routing)
    return f"{base}/#/projects/{project_id}"


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def _parse_sse_event(block: str) -> Optional[dict]:
    """Parse one SSE event block (text between double newlines) into a dict."""
    import json as _json

    data_lines: list[str] = []
    event_type: Optional[str] = None
    for line in block.splitlines():
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        return None
    raw = "\n".join(data_lines)
    try:
        payload = _json.loads(raw)
    except Exception:
        payload = {"content": raw}
    if event_type:
        payload.setdefault("type", event_type)
    return payload


# ---------------------------------------------------------------------------
# Class-based client
# Wraps the module-level helpers and adds run management (start_run /
# stream_run) for the DESIGN Studio handler in handlers/design.py.
# ---------------------------------------------------------------------------

class OpenDesignClient:
    """HTTP client for the nexu-io/open-design daemon."""

    def __init__(self, base_url: str = _OPEN_DESIGN_URL):
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        skill_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> dict:
        """Create a project. Returns {"project": {"id": str, ...}}.

        The OD daemon requires the caller to supply ``id`` in the request body.
        A UUID is generated automatically if ``project_id`` is not given.
        """
        import uuid as _uuid
        pid = project_id or str(_uuid.uuid4())
        payload: dict = {"id": pid, "name": name}
        if skill_id:
            payload["skillId"] = skill_id
        with httpx.Client(base_url=self._base_url, timeout=_DEFAULT_TIMEOUT) as c:
            r = c.post("/api/projects", json=payload)
            r.raise_for_status()
            data = r.json()
        if "project" not in data:
            data = {"project": data}
        if "id" not in data["project"]:
            raise ValueError(f"[OpenDesignClient] create_project: no 'id' in response: {data}")
        logger.info("[OpenDesignClient] Created project %r id=%s", name, data["project"]["id"])
        return data

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    def start_run(
        self,
        project_id: str,
        message: str,
        skill_id: Optional[str] = None,
    ) -> dict:
        """Start an agent run for a project. Returns {"runId": str}."""
        payload: dict = {"message": message}
        if skill_id:
            payload["skillId"] = skill_id
        with httpx.Client(base_url=self._base_url, timeout=_DEFAULT_TIMEOUT) as c:
            r = c.post(f"/api/projects/{project_id}/runs", json=payload)
            r.raise_for_status()
            data = r.json()
        if "runId" not in data:
            run_id = data.get("id") or data.get("run_id")
            if not run_id:
                raise ValueError(f"[OpenDesignClient] start_run: no runId in response: {data}")
            data = {"runId": run_id}
        logger.info("[OpenDesignClient] Started run %s on project %s", data["runId"], project_id)
        return data

    def stream_run(self, run_id: str):
        """Stream events for a run via SSE.

        Yields dicts with at least a 'type' key.  Relevant types:
          {"type": "text",         "content": str}
          {"type": "artifact:end", "identifier": str, "fullContent": str}
          {"type": "done"}
        """
        url = f"{self._base_url}/api/runs/{run_id}/stream"
        try:
            with httpx.Client(timeout=120.0) as c:
                with c.stream("GET", url) as response:
                    response.raise_for_status()
                    buffer = ""
                    for chunk in response.iter_text():
                        buffer += chunk
                        while "\n\n" in buffer:
                            event_block, buffer = buffer.split("\n\n", 1)
                            event = _parse_sse_event(event_block)
                            if event:
                                yield event
        except Exception as exc:
            logger.error("[OpenDesignClient] stream_run error for run %s: %s", run_id, exc)
            raise
