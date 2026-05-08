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
    """Heuristically map a user's design request to an OD skill ID."""
    lower = user_input.lower()

    ppt_keywords = [
        "deck", "slide", "presentation", "ppt", "pitch deck", "slideshow",
        "keynote", "powerpoint",
    ]
    dashboard_keywords = [
        "dashboard", "analytics", "data viz", "chart", "graph", "kpi",
        "monitoring", "report", "admin panel", "metrics",
    ]
    landing_keywords = [
        "landing page", "saas", "marketing site", "hero section",
        "conversion", "sign up page", "sales page", "product page",
    ]
    mobile_keywords = [
        "mobile app", "ios app", "android app", "mobile ui", "phone app",
        "smartphone", "app screen", "mobile design",
    ]

    if any(kw in lower for kw in ppt_keywords):
        return "guizang-ppt"
    if any(kw in lower for kw in dashboard_keywords):
        return "dashboard"
    if any(kw in lower for kw in landing_keywords):
        return "saas-landing"
    if any(kw in lower for kw in mobile_keywords):
        return "mobile-app"
    return "web-prototype"


# ---------------------------------------------------------------------------
# Artifact parser — extracts <artifact ...>HTML</artifact> from LLM output
# Mirrors the logic in nexu-io/open-design/apps/web/src/artifacts/parser.ts
# ---------------------------------------------------------------------------
def parse_artifact_html(text: str) -> Optional[str]:
    """
    Extract the first <artifact …>…</artifact> block from text.

    Returns the HTML content string, or None if no artifact tag is found.
    """
    import re

    pattern = re.compile(
        r'<artifact\s[^>]*>(.*?)</artifact>',
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    # Fallback: if the model output looks like a standalone HTML file
    # (starts with <!DOCTYPE or <html>) without wrapping artifact tags,
    # accept it directly so the design still reaches the user.
    stripped = text.strip()
    if stripped.lower().startswith("<!doctype html") or stripped.lower().startswith("<html"):
        return stripped

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


def create_project(name: str, skill_id: Optional[str] = None) -> Optional[str]:
    """
    Create a new OD project and return its ID.

    Returns the project ID string, or None on failure.
    """
    payload: dict = {"name": name}
    if skill_id:
        payload["skillId"] = skill_id
    try:
        with _client() as c:
            r = c.post("/api/projects", json=payload)
            r.raise_for_status()
            project = r.json().get("project") or r.json()
            project_id = project.get("id") if isinstance(project, dict) else None
            logger.info("[OpenDesign] Created project %r (id=%s)", name, project_id)
            return project_id
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
