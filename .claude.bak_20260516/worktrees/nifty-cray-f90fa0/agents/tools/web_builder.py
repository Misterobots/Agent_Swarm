"""
Web application builder tool for Memex agents.

Agents use these tools to:
  - Scaffold a new project from a template
  - Write HTML/JS/CSS to user_projects/<name>/
  - Serve it immediately at the project URL

Security: writes are sandboxed to USER_PROJECTS_DIR only.
"""

import os
import re
from pathlib import Path

from logger_setup import setup_logger

logger = setup_logger("WebBuilder")

# ---------------------------------------------------------------------------
# Config — can be overridden via environment for testing
# ---------------------------------------------------------------------------
_WORKSPACE = Path(os.getenv("WORKSPACE_ROOT", "/workspace"))
USER_PROJECTS_DIR = _WORKSPACE / "user_projects"
TEMPLATES_DIR = USER_PROJECTS_DIR / "_templates"
PROJECT_BASE_URL = os.getenv(
    "PROJECT_BASE_URL", "http://192.168.2.103:8008/projects"
)

# Simple safeguard: project names may only contain alphanumeric, dash, underscore.
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def _safe_project_dir(project_name: str) -> Path:
    """Resolve and validate the project directory, guarding against traversal."""
    if not _SAFE_NAME_RE.match(project_name):
        raise ValueError(
            f"Invalid project name '{project_name}'. "
            "Use only letters, numbers, hyphens and underscores."
        )
    candidate = (USER_PROJECTS_DIR / project_name).resolve()
    if USER_PROJECTS_DIR.resolve() not in [candidate] + list(candidate.parents):
        raise PermissionError("Path traversal detected in project name.")
    return candidate


# ---------------------------------------------------------------------------
# Public tools (registered as agent tools)
# ---------------------------------------------------------------------------

def build_web_app(project_name: str, html_content: str) -> str:
    """
    Write a self-contained web app to user_projects/<project_name>/index.html.

    The file is served immediately via agent_runtime at:
      {PROJECT_BASE_URL}/<project_name>/

    Args:
        project_name: URL-safe name for the project (a-z, 0-9, hyphen, underscore).
        html_content: Full HTML content to write as index.html.

    Returns:
        A string containing the live URL and a success message, e.g.
        "PROJECT_URL: http://192.168.2.103:8008/projects/my-game/"
    """
    try:
        project_dir = _safe_project_dir(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        index_file = project_dir / "index.html"
        index_file.write_text(html_content, encoding="utf-8")
        url = f"{PROJECT_BASE_URL}/{project_name}/"
        logger.info(f"[WebBuilder] Built project '{project_name}' → {url}")
        # Write the URL to a temp file so Lamport can reliably pick it up
        # even when the LLM paraphrases the tool result in its response text.
        try:
            import pathlib as _pl
            _pl.Path("/tmp/web_builder_last_url.txt").write_text(url, encoding="utf-8")
        except Exception:
            pass
        return f"PROJECT_URL: {url}\nSuccessfully wrote {len(html_content)} bytes to {index_file}"
    except (ValueError, PermissionError) as e:
        logger.error(f"[WebBuilder] Security error building '{project_name}': {e}")
        return f"Error: {e}"
    except Exception as e:
        logger.error(f"[WebBuilder] Failed to build '{project_name}': {e}")
        return f"Error writing project files: {e}"


def get_project_template(template_type: str) -> str:
    """
    Return a scaffold template for the given type.

    Available types: game, dashboard, landing

    Returns the full HTML template content, or an empty scaffold if not found.
    """
    safe_type = re.sub(r"[^a-z0-9_-]", "", template_type.lower())
    template_path = TEMPLATES_DIR / safe_type / "index.html"
    if template_path.exists():
        logger.info(f"[WebBuilder] Loaded template '{safe_type}'")
        return template_path.read_text(encoding="utf-8")

    logger.warning(f"[WebBuilder] Template '{safe_type}' not found, returning minimal scaffold")
    return (
        f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        f"<meta charset=\"UTF-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>Project</title>\n</head>\n<body>\n"
        f"<!-- {safe_type} scaffold — replace this content -->\n"
        f"<h1>Project</h1>\n</body>\n</html>\n"
    )


def list_project_templates() -> str:
    """
    List all available web app scaffold templates.

    Returns a newline-separated list of template type names.
    """
    if not TEMPLATES_DIR.exists():
        return "No templates directory found."
    templates = [
        d.name for d in TEMPLATES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "index.html").exists()
    ]
    if not templates:
        return "No templates available."
    return "\n".join(templates)
