"""
Documentation Standards Agent
==============================

Hybrid agent that enforces Hive DocSite standards on documentation files.
Combines deterministic structure analysis with LLM-powered content generation.

Trigger:
  - Router keyword: ``/standardize-doc <path_or_url>``
  - Admin-only (requires L3_ADMIN security level)

Capabilities:
  - Analyze local .md files or fetch external URLs
  - Detect missing sections vs. the DocSite standard template
  - Generate missing content (citations, changelogs, usage guides, etc.)
  - Apply glightbox attributes to all images for zoom/expand
  - Assign and maintain Document IDs (DOC-CATEGORY-NNNN)
  - Output a fully standardized document
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger("DocStandardsAgent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("ARCHITECT_MODEL", "qwen2.5-coder:14b-instruct-q4_k_m")
DOCS_ROOT = Path(os.getenv("DOCS_ROOT", "/workspace/docs-site/docs"))
DOCS_SOURCE_ROOT = Path(os.getenv("DOCS_SOURCE_ROOT", "/workspace/docs"))
DOC_ID_REGISTRY_PATH = Path(os.getenv("DOC_ID_REGISTRY", "/workspace/docs-site/doc_id_registry.json"))

# Standard sections that every DocSite page must contain
REQUIRED_SECTIONS = [
    "source citations & references",
    "changelog",
    "overview",
    "usage in the hive",
    "maintenance & updates",
    "functionality testing",
    "ui, screenshots & examples",
    "related documentation",
]

# Category detection keywords → DOC-CATEGORY prefix
CATEGORY_MAP = {
    "architecture": "ARCH",
    "module": "MOD",
    "procedure": "PROC",
    "tutorial": "TUT",
    "admin": "ADM",
    "developer": "DEV",
    "user guide": "USR",
    "troubleshooting": "TSH",
    "reference": "REF",
    "service": "SVC",
    "tool": "TOOL",
    "faq": "FAQ",
    "security": "SEC",
}

# Category code → human-readable domain name
DOMAIN_MAP = {
    "ARCH": "Architecture",
    "MOD": "Module",
    "PROC": "Procedures",
    "TUT": "Tutorial",
    "ADM": "Admin Guide",
    "DEV": "Developer Guide",
    "USR": "User Guide",
    "TSH": "Troubleshooting",
    "REF": "Reference",
    "SVC": "Service",
    "TOOL": "Tool",
    "FAQ": "FAQ",
    "SEC": "Security",
}

# Category code → default owner team
OWNER_MAP = {
    "ARCH": "Core Platform",
    "SEC": "Security Team",
    "ADM": "Platform Ops",
    "DEV": "Developer Experience",
    "USR": "User Experience",
    "SVC": "Service Team",
}
DEFAULT_OWNER = "Core Platform"

# Image patterns that need lightbox treatment
IMAGE_PATTERN = re.compile(
    r'!\[([^\]]*)\]\(([^)]+)\)(?!\{.*loading)', re.MULTILINE
)
FIGURE_PATTERN = re.compile(
    r'<figure[^>]*>.*?</figure>', re.DOTALL | re.MULTILINE
)


# ---------------------------------------------------------------------------
# Document ID Management
# ---------------------------------------------------------------------------
def _load_doc_id_registry() -> dict:
    """Load the persistent document ID registry."""
    if DOC_ID_REGISTRY_PATH.exists():
        try:
            return json.loads(DOC_ID_REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"[DocStandards] Failed to load registry: {exc}")
    return {"next_ids": {}, "assignments": {}}


def _save_doc_id_registry(registry: dict) -> None:
    """Persist the document ID registry."""
    DOC_ID_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_ID_REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def assign_doc_id(filepath: str, category: str = "MOD") -> str:
    """Assign or retrieve a persistent Document ID for a file."""
    registry = _load_doc_id_registry()
    normalized = str(filepath).replace("\\", "/")

    # Return existing assignment
    if normalized in registry.get("assignments", {}):
        return registry["assignments"][normalized]

    # Allocate new ID
    next_ids = registry.setdefault("next_ids", {})
    seq = next_ids.get(category, 1)
    doc_id = f"DOC-{category}-{seq:04d}"
    next_ids[category] = seq + 1
    registry.setdefault("assignments", {})[normalized] = doc_id
    _save_doc_id_registry(registry)
    return doc_id


def detect_category(filepath: str, content: str) -> str:
    """Detect document category from filepath and content."""
    fp_lower = filepath.lower().replace("\\", "/")
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in fp_lower:
            return cat
    # Fallback: hash-based — inspect content for clues
    content_lower = content[:2000].lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in content_lower:
            return cat
    return "MOD"


# ---------------------------------------------------------------------------
# Structural Analysis (Deterministic)
# ---------------------------------------------------------------------------
def analyze_structure(content: str) -> dict:
    """
    Deterministic analysis: check which standard sections exist,
    which are missing, and identify images needing lightbox.
    """
    headings = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
    headings_lower = [h.strip().lower() for h in headings]

    # Check frontmatter
    has_frontmatter = content.strip().startswith("---")
    frontmatter_fields = {}
    if has_frontmatter:
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    frontmatter_fields[key.strip()] = val.strip().strip('"\'')

    # Detect present/missing sections
    sections_present = []
    sections_missing = []
    for section in REQUIRED_SECTIONS:
        # Fuzzy match: check if any heading contains the key phrase
        found = any(section in h or h in section for h in headings_lower)
        if found:
            sections_present.append(section)
        else:
            sections_missing.append(section)

    # Detect images needing lightbox
    images = IMAGE_PATTERN.findall(content)
    figures = FIGURE_PATTERN.findall(content)
    images_without_lightbox = [
        img for img in images
        if "loading=lazy" not in content[content.find(f"({img[1]})"):content.find(f"({img[1]})") + 100]
    ]

    # Detect existing citations/URLs
    urls = re.findall(r'https?://[^\s\)>\]]+', content)
    project_refs = re.findall(r'(?:based on|forked from|adapted from|see|ref:?)\s+([A-Za-z][\w\-/]+)', content, re.IGNORECASE)

    compliance = len(sections_present) / max(len(REQUIRED_SECTIONS), 1) * 100
    # Bonus for frontmatter completeness
    fm_required = {"title", "doc_id", "last_updated", "source_ref"}
    fm_present = fm_required & set(frontmatter_fields.keys())
    fm_compliance = len(fm_present) / len(fm_required) * 100
    overall = (compliance * 0.7 + fm_compliance * 0.3)

    return {
        "has_frontmatter": has_frontmatter,
        "frontmatter_fields": frontmatter_fields,
        "frontmatter_missing": list(fm_required - set(frontmatter_fields.keys())),
        "headings": headings,
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "image_count": len(images),
        "images_without_lightbox": len(images_without_lightbox),
        "figure_count": len(figures),
        "detected_urls": urls[:20],
        "detected_refs": project_refs[:10],
        "overall_compliance_pct": round(overall, 1),
    }


# ---------------------------------------------------------------------------
# Image Lightbox Enforcement (Deterministic)
# ---------------------------------------------------------------------------
def enforce_lightbox(content: str) -> str:
    """Add glightbox attributes to all images missing them."""
    def _add_lightbox(match):
        alt = match.group(1)
        path = match.group(2)
        full_match = match.group(0)
        # Check if already has attr_list
        end_pos = match.end()
        remaining = content[end_pos:end_pos + 30]
        if remaining.strip().startswith("{"):
            return full_match  # Already has attributes
        return f'![{alt}]({path}){{ loading=lazy }}'

    result = IMAGE_PATTERN.sub(_add_lightbox, content)
    return result


# ---------------------------------------------------------------------------
# Frontmatter Enforcement (Deterministic)
# ---------------------------------------------------------------------------
def enforce_frontmatter(
    content: str,
    doc_id: str,
    title: str = "",
    source_ref: str = "Internal",
) -> str:
    """Ensure YAML frontmatter has all required fields."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not title:
        # Extract from first heading
        h1 = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = h1.group(1).strip() if h1 else "Untitled Document"

    required = {
        "title": f'"{title}"',
        "doc_id": f'"{doc_id}"',
        "last_updated": f'"{now}"',
        "source_ref": f'"{source_ref}"',
    }

    if content.strip().startswith("---"):
        # Update existing frontmatter
        fm_match = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
        if fm_match:
            fm_body = fm_match.group(2)
            for key, val in required.items():
                if re.search(rf'^{key}\s*:', fm_body, re.MULTILINE):
                    # Update existing field
                    fm_body = re.sub(
                        rf'^({key}\s*:).*$', rf'\1 {val}', fm_body, flags=re.MULTILINE
                    )
                else:
                    fm_body += f"\n{key}: {val}"
            return f"---\n{fm_body.strip()}\n---{content[fm_match.end():]}"
    else:
        # Prepend new frontmatter
        fm = "---\n"
        for key, val in required.items():
            fm += f"{key}: {val}\n"
        fm += "---\n\n"
        return fm + content

    return content


# ---------------------------------------------------------------------------
# Document ID Badge Injection
# ---------------------------------------------------------------------------
def inject_doc_id_badge(content: str, doc_id: str, source_ref: str, category: str = "MOD") -> str:
    """Add a Document ID metadata block after the first H1, matching Mempalace deep dive format."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    domain = DOMAIN_MAP.get(category, "Module")
    owner = OWNER_MAP.get(category, DEFAULT_OWNER)
    badge = (
        f"\n```\n"
        f"Document ID: {doc_id}\n"
        f"Domain: {domain}\n"
        f"Owner: {owner}\n"
        f"Status: Active\n"
        f"Version: 1.0\n"
        f"Last Updated: {now}\n"
        f"```\n"
    )

    # Find first H1
    h1_match = re.search(r'^(#\s+.+)$', content, re.MULTILINE)
    if h1_match:
        insert_pos = h1_match.end()
        # Check if badge already exists (code-block or legacy blockquote format)
        next_lines = content[insert_pos:insert_pos + 300]
        if "Document ID:" in next_lines:
            # Replace existing badge — handle both code-block and blockquote styles
            # Code-block style: ```\n...Document ID...\n```
            cb_pattern = re.compile(r'\n```\n(?:.*?Document ID:.*?)```\n', re.DOTALL)
            after = content[insert_pos:]
            if cb_pattern.search(after):
                after = cb_pattern.sub(badge, after, count=1)
                return content[:insert_pos] + after
            # Legacy blockquote style: > **Document ID:**...
            bq_pattern = re.compile(r'\n>.*?Document ID:.*?\n')
            if bq_pattern.search(after):
                after = bq_pattern.sub(badge, after, count=1)
                return content[:insert_pos] + after
        return content[:insert_pos] + badge + content[insert_pos:]

    return content


# ---------------------------------------------------------------------------
# External URL Fetcher
# ---------------------------------------------------------------------------
def fetch_external_content(url: str) -> Optional[str]:
    """Fetch content from an external URL for citation enrichment."""
    try:
        import httpx
    except ImportError:
        logger.warning("[DocStandards] httpx not available, skipping URL fetch")
        return None

    from tools.web_browser import validate_url

    is_valid, reason = validate_url(url)
    if not is_valid:
        logger.warning(f"[DocStandards] URL blocked: {url} — {reason}")
        return None

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "HiveDocAgent/1.0"})
            resp.raise_for_status()
            # Basic HTML → text extraction
            text = resp.text
            # Strip HTML tags for rough text extraction
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:10000]  # Limit size
    except Exception as exc:
        logger.error(f"[DocStandards] Fetch failed for {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# LLM Content Generation
# ---------------------------------------------------------------------------
def _call_llm(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """Call the Ollama LLM for content generation."""
    resolved_model = model or DEFAULT_MODEL
    try:
        from utils.gpu_queue import get_best_host_for_model
        host = get_best_host_for_model(resolved_model)
    except ImportError:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    try:
        import httpx
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 4096},
        }
        with httpx.Client(timeout=300) as client:
            resp = client.post(f"{host}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
    except Exception as exc:
        logger.error(f"[DocStandards] LLM call failed: {exc}")
        return f"<!-- LLM generation failed: {exc} -->"


def generate_section(section_name: str, content: str, model: str | None = None) -> str:
    """Generate a specific missing section using the LLM."""
    from prompts.doc_standards_prompt import (
        SECTION_GEN_SYSTEM_PROMPT,
        GENERATE_CITATIONS_PROMPT,
        GENERATE_CHANGELOG_PROMPT,
        GENERATE_USAGE_PROMPT,
        GENERATE_MAINTENANCE_PROMPT,
        GENERATE_TESTING_PROMPT,
        GENERATE_UI_EXAMPLES_PROMPT,
        GENERATE_RELATED_PROMPT,
    )

    prompt_map = {
        "source citations & references": GENERATE_CITATIONS_PROMPT,
        "changelog": GENERATE_CHANGELOG_PROMPT,
        "usage in the hive": GENERATE_USAGE_PROMPT,
        "maintenance & updates": GENERATE_MAINTENANCE_PROMPT,
        "functionality testing": GENERATE_TESTING_PROMPT,
        "ui, screenshots & examples": GENERATE_UI_EXAMPLES_PROMPT,
        "related documentation": GENERATE_RELATED_PROMPT,
    }

    user_prompt = prompt_map.get(section_name, "")
    if not user_prompt:
        return f"<!-- Section '{section_name}' generation not implemented -->"

    result = _call_llm(
        SECTION_GEN_SYSTEM_PROMPT,
        user_prompt.format(content=content[:6000]),
        model=model,
    )
    return result


# ---------------------------------------------------------------------------
# Main Pipeline — Streaming Generator
# ---------------------------------------------------------------------------
def standardize_document(
    filepath: str,
    *,
    model: str | None = None,
    source_ref: str = "",
    external_urls: list[str] | None = None,
    full_rewrite: bool = False,
    dry_run: bool = False,
) -> Generator[dict[str, Any], None, None]:
    """
    Main standardization pipeline. Yields streaming status updates.

    Args:
        filepath: Path to the document to standardize.
        model: Override LLM model for generation.
        source_ref: Original source reference (project URL, etc.).
        external_urls: External URLs to fetch for citation enrichment.
        full_rewrite: If True, do a one-shot LLM rewrite instead of incremental.
        dry_run: If True, only analyze — don't write changes.

    Yields:
        dict events: {"type": "status|thought|log|response|error", "content": "..."}
    """
    yield {"type": "status", "content": "📄 Doc Standards Agent: Starting analysis..."}

    # --- Step 1: Read the document ---
    try:
        doc_path = Path(filepath)
        if not doc_path.exists():
            # Try relative to workspace roots
            for root in [DOCS_ROOT, DOCS_SOURCE_ROOT, Path("/workspace")]:
                candidate = root / filepath
                if candidate.exists():
                    doc_path = candidate
                    break
            else:
                yield {"type": "error", "content": f"File not found: {filepath}"}
                return

        content = doc_path.read_text(encoding="utf-8")
        yield {"type": "log", "content": f"[DocStandards] Read {len(content)} chars from {doc_path}"}
    except Exception as exc:
        yield {"type": "error", "content": f"Failed to read {filepath}: {exc}"}
        return

    # --- Step 2: Structural Analysis ---
    yield {"type": "status", "content": "🔍 Analyzing document structure..."}
    analysis = analyze_structure(content)
    yield {"type": "thought", "content": f"→ Compliance: {analysis['overall_compliance_pct']}%"}
    yield {"type": "thought", "content": f"→ Present: {', '.join(analysis['sections_present']) or 'None'}"}
    yield {"type": "thought", "content": f"→ Missing: {', '.join(analysis['sections_missing']) or 'None'}"}
    yield {"type": "thought", "content": f"→ Images without lightbox: {analysis['images_without_lightbox']}"}
    yield {"type": "thought", "content": f"→ Frontmatter missing: {', '.join(analysis['frontmatter_missing']) or 'Complete'}"}

    if dry_run:
        yield {"type": "response", "content": json.dumps(analysis, indent=2)}
        return

    # --- Step 3: Fetch External Context (if URLs provided) ---
    external_context = ""
    if external_urls:
        yield {"type": "status", "content": f"🌐 Fetching {len(external_urls)} external references..."}
        for url in external_urls[:5]:  # Limit to 5
            fetched = fetch_external_content(url)
            if fetched:
                external_context += f"\n\n[External: {url}]\n{fetched[:3000]}"
                yield {"type": "log", "content": f"[DocStandards] Fetched {len(fetched)} chars from {url}"}
            else:
                yield {"type": "log", "content": f"[DocStandards] Failed to fetch {url}"}

    if not source_ref and analysis.get("detected_urls"):
        source_ref = analysis["detected_urls"][0]

    # --- Step 4: Assign Document ID ---
    category = detect_category(filepath, content)
    doc_id = assign_doc_id(filepath, category)
    yield {"type": "thought", "content": f"→ Document ID: {doc_id} (category: {category})"}

    # --- Step 5: Full Rewrite or Incremental Enhancement ---
    if full_rewrite:
        yield {"type": "status", "content": "Full document rewrite in progress..."}
        from prompts.doc_standards_prompt import FULL_STANDARDIZE_PROMPT, SECTION_GEN_SYSTEM_PROMPT
        full_content = content
        if external_context:
            full_content += f"\n\n[External Reference Context]{external_context}"
        result = _call_llm(
            SECTION_GEN_SYSTEM_PROMPT,
            FULL_STANDARDIZE_PROMPT.format(content=full_content[:10000]),
            model=model,
        )
        # Apply deterministic fixes on top of LLM output
        result = enforce_frontmatter(result, doc_id, source_ref=source_ref or "Internal")
        result = enforce_lightbox(result)
        result = inject_doc_id_badge(result, doc_id, source_ref or "Internal", category=category)
    else:
        # Incremental: keep existing content, generate and inject missing sections
        yield {"type": "status", "content": "Enhancing document incrementally..."}
        result = content

        # 5a. Fix frontmatter
        result = enforce_frontmatter(result, doc_id, source_ref=source_ref or "Internal")
        yield {"type": "log", "content": "[DocStandards] Frontmatter enforced."}

        # 5b. Inject Doc ID badge
        result = inject_doc_id_badge(result, doc_id, source_ref or "Internal", category=category)

        # 5c. Fix lightbox on all images
        result = enforce_lightbox(result)
        if analysis["images_without_lightbox"] > 0:
            yield {"type": "log", "content": f"[DocStandards] Added lightbox to {analysis['images_without_lightbox']} images."}

        # 5d. Generate missing sections via LLM
        gen_content = content
        if external_context:
            gen_content += external_context

        for section in analysis["sections_missing"]:
            yield {"type": "status", "content": f"Generating: {section.title()}..."}
            generated = generate_section(section, gen_content, model=model)
            if generated and not generated.startswith("<!-- Section"):
                # Find appropriate insertion point
                result = _insert_section(result, section, generated)
                yield {"type": "log", "content": f"[DocStandards] Generated: {section}"}
            else:
                yield {"type": "log", "content": f"[DocStandards] Skipped: {section} (generation failed)"}

    # --- Step 6: Write Output ---
    output_path = doc_path
    # If source is outside docs-site, write to docs-site
    if DOCS_ROOT not in doc_path.parents and doc_path != DOCS_ROOT:
        # Determine target subdir
        target_subdir = _get_docsite_subdir(filepath, category)
        output_path = DOCS_ROOT / target_subdir / doc_path.name
        output_path.parent.mkdir(parents=True, exist_ok=True)

    yield {"type": "status", "content": f"💾 Writing standardized document to {output_path}..."}
    try:
        output_path.write_text(result, encoding="utf-8")
        yield {"type": "log", "content": f"[DocStandards] Written to {output_path}"}
    except Exception as exc:
        yield {"type": "error", "content": f"Failed to write: {exc}"}
        return

    # --- Step 7: Final Report ---
    final_analysis = analyze_structure(result)
    yield {"type": "thought", "content": f"→ Final compliance: {final_analysis['overall_compliance_pct']}% (was {analysis['overall_compliance_pct']}%)"}

    report = (
        f"## 📋 Documentation Standards Report\n\n"
        f"| Metric | Before | After |\n"
        f"|--------|--------|-------|\n"
        f"| Compliance | {analysis['overall_compliance_pct']}% | {final_analysis['overall_compliance_pct']}% |\n"
        f"| Sections Present | {len(analysis['sections_present'])} | {len(final_analysis['sections_present'])} |\n"
        f"| Sections Missing | {len(analysis['sections_missing'])} | {len(final_analysis['sections_missing'])} |\n"
        f"| Images w/ Lightbox | {analysis['image_count'] - analysis['images_without_lightbox']} | {final_analysis['image_count']} |\n"
        f"| Document ID | {'✅' if 'doc_id' in analysis['frontmatter_fields'] else '❌'} | ✅ |\n\n"
        f"**Document ID:** `{doc_id}`\n"
        f"**Output:** `{output_path}`\n"
    )
    if final_analysis["sections_missing"]:
        report += f"\n**Still Missing:** {', '.join(final_analysis['sections_missing'])}\n"

    yield {"type": "response", "content": report}


# ---------------------------------------------------------------------------
# Section Insertion Helper
# ---------------------------------------------------------------------------
def _insert_section(content: str, section_name: str, generated: str) -> str:
    """Insert a generated section at the appropriate position in the document."""
    # Section order for insertion
    section_order = [
        "source citations & references",
        "changelog",
        "overview",
        "usage in the hive",
        "maintenance & updates",
        "functionality testing",
        "ui, screenshots & examples",
        "related documentation",
    ]

    # Map section to heading
    heading_map = {
        "source citations & references": "## Source Citations & References",
        "changelog": "## Changelog (Source → Implementation)",
        "overview": "## Overview",
        "usage in the hive": "## Usage in the Hive",
        "maintenance & updates": "## Maintenance & Updates",
        "functionality testing": "## Functionality Testing",
        "ui, screenshots & examples": "## UI, Screenshots & Examples",
        "related documentation": "## Related Documentation",
    }

    heading = heading_map.get(section_name, f"## {section_name.title()}")
    block = f"\n\n---\n\n{heading}\n\n{generated.strip()}\n"

    # Find insertion point: before the next section that exists
    idx = section_order.index(section_name) if section_name in section_order else len(section_order)
    for later_section in section_order[idx + 1:]:
        later_heading = heading_map.get(later_section, "")
        if later_heading:
            # Find this heading in content (case-insensitive)
            pattern = re.compile(re.escape(later_heading), re.IGNORECASE)
            match = pattern.search(content)
            if match:
                # Insert before the --- that precedes this section
                insert_at = match.start()
                # Walk back to find the preceding ---
                before = content[:insert_at].rstrip()
                if before.endswith("---"):
                    insert_at = len(before) - 3
                return content[:insert_at] + block + content[insert_at:]

    # No later section found — append at end
    return content.rstrip() + block + "\n"


def _get_docsite_subdir(filepath: str, category: str) -> str:
    """Map a category to a docs-site subdirectory."""
    category_dirs = {
        "ARCH": "architecture",
        "MOD": "modules",
        "PROC": "procedures",
        "TUT": "tutorials",
        "ADM": "admin-guide",
        "DEV": "developer-guide",
        "USR": "user-guide",
        "TSH": "troubleshooting",
        "REF": "reference",
        "SVC": "modules/services",
        "TOOL": "modules/tools",
        "FAQ": "faq",
        "SEC": "architecture",
    }
    return category_dirs.get(category, "reference")


# ---------------------------------------------------------------------------
# Batch Scan & Align — scan all docs and auto-fix
# ---------------------------------------------------------------------------
def _discover_markdown_files() -> list[Path]:
    """Find all .md files in docs-site/docs/ and docs/."""
    files: list[Path] = []
    for root_dir in [DOCS_ROOT, DOCS_SOURCE_ROOT]:
        if root_dir.exists():
            for md in sorted(root_dir.rglob("*.md")):
                # Skip site/ build output, __pycache__, hidden dirs
                parts = md.relative_to(root_dir).parts
                if any(p.startswith(".") or p in ("site", "__pycache__") for p in parts):
                    continue
                files.append(md)
    return files


def batch_scan(
    *,
    model: str | None = None,
    auto_fix: bool = True,
    full_rewrite: bool = False,
) -> Generator[dict[str, Any], None, None]:
    """
    Scan all markdown docs across docs-site/docs/ and docs/.
    Yields a compliance report, then auto-fixes non-compliant files.

    Args:
        model: Override LLM model for content generation.
        auto_fix: If True, standardize non-compliant files after scanning.
        full_rewrite: If True, use full LLM rewrite mode for fixes.

    Yields:
        dict events compatible with the router streaming protocol.
    """
    yield {"type": "status", "content": "📄 Doc Standards Agent: Starting full DocSite alignment scan..."}

    files = _discover_markdown_files()
    yield {"type": "log", "content": f"[DocStandards] Discovered {len(files)} markdown files across docs-site/docs/ and docs/"}

    if not files:
        yield {"type": "error", "content": "No markdown files found to scan."}
        return

    # --- Phase 1: Scan all files ---
    yield {"type": "status", "content": f"🔍 Phase 1: Scanning {len(files)} documents..."}
    results: list[dict] = []
    for i, md_path in enumerate(files, 1):
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception as exc:
            results.append({
                "file": str(md_path),
                "error": str(exc),
                "compliance": 0,
            })
            continue

        analysis = analyze_structure(content)
        cat = detect_category(str(md_path), content)

        results.append({
            "file": str(md_path),
            "relative": _relative_display(md_path),
            "compliance": analysis["overall_compliance_pct"],
            "sections_present": len(analysis["sections_present"]),
            "sections_missing": len(analysis["sections_missing"]),
            "missing_list": analysis["sections_missing"],
            "fm_missing": analysis["frontmatter_missing"],
            "images_no_lb": analysis["images_without_lightbox"],
            "category": cat,
        })

        # Progress every 20 files
        if i % 20 == 0:
            yield {"type": "log", "content": f"[DocStandards] Scanned {i}/{len(files)}..."}

    yield {"type": "log", "content": f"[DocStandards] Scan complete: {len(results)} files analyzed."}

    # --- Phase 2: Generate compliance report ---
    yield {"type": "status", "content": "📊 Phase 2: Generating compliance report..."}

    # Sort by compliance (worst first)
    results.sort(key=lambda r: r.get("compliance", 0))

    total = len(results)
    compliant = sum(1 for r in results if r.get("compliance", 0) >= 80)
    partial = sum(1 for r in results if 30 <= r.get("compliance", 0) < 80)
    non_compliant = sum(1 for r in results if r.get("compliance", 0) < 30)
    avg_compliance = sum(r.get("compliance", 0) for r in results) / max(total, 1)

    # Build markdown report table
    report_lines = [
        "## 📊 DocSite Alignment Report\n",
        f"**Scanned:** {total} files · "
        f"**Average Compliance:** {avg_compliance:.1f}%\n",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| ✅ Compliant (≥80%) | {compliant} |",
        f"| ⚠️ Partial (30-79%) | {partial} |",
        f"| ❌ Non-Compliant (<30%) | {non_compliant} |",
        "",
        "### Files by Compliance\n",
        "| File | Compliance | Missing Sections | Frontmatter | Images |",
        "|------|-----------|-----------------|-------------|--------|",
    ]

    for r in results:
        if "error" in r:
            report_lines.append(f"| `{r.get('relative', r['file'])}` | ❌ Error | — | — | — |")
            continue
        comp = r["compliance"]
        icon = "✅" if comp >= 80 else ("⚠️" if comp >= 30 else "❌")
        fm_status = "✅" if not r["fm_missing"] else f"❌ {', '.join(r['fm_missing'])}"
        img_status = "✅" if r["images_no_lb"] == 0 else f"⚠️ {r['images_no_lb']}"
        report_lines.append(
            f"| `{r.get('relative', r['file'])}` | {icon} {comp:.0f}% "
            f"| {r['sections_missing']} missing | {fm_status} | {img_status} |"
        )

    report = "\n".join(report_lines)
    yield {"type": "message", "content": report}

    # --- Phase 3: Auto-fix non-compliant files ---
    if not auto_fix:
        yield {"type": "log", "content": "[DocStandards] Dry-run mode — skipping fixes."}
        return

    needs_fix = [r for r in results if r.get("compliance", 0) < 80 and "error" not in r]
    if not needs_fix:
        yield {"type": "message", "content": "\n\n✅ **All documents are compliant (≥80%).** No fixes needed."}
        return

    yield {"type": "status", "content": f"🔧 Phase 3: Auto-fixing {len(needs_fix)} non-compliant documents..."}

    fixed = 0
    failed = 0
    for i, r in enumerate(needs_fix, 1):
        yield {"type": "status", "content": f"🔧 [{i}/{len(needs_fix)}] Fixing: {r.get('relative', r['file'])}..."}

        try:
            for event in standardize_document(
                r["file"],
                model=model,
                full_rewrite=full_rewrite,
            ):
                etype = event.get("type", "")
                # Forward logs and errors; suppress per-file responses (we'll summarize)
                if etype in ("log", "error"):
                    yield event
                elif etype == "thought":
                    yield event
            fixed += 1
        except Exception as exc:
            logger.error(f"[DocStandards] Batch fix failed for {r['file']}: {exc}")
            yield {"type": "log", "content": f"[DocStandards] ❌ Fix failed: {r.get('relative', r['file'])} — {exc}"}
            failed += 1

    # --- Phase 4: Summary ---
    summary = (
        f"\n\n## 📋 Alignment Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Total scanned | {total} |\n"
        f"| Already compliant | {compliant} |\n"
        f"| Fixed | {fixed} |\n"
        f"| Fix failed | {failed} |\n"
        f"| Remaining non-compliant | {non_compliant - fixed} |\n"
    )
    yield {"type": "message", "content": summary}


def _relative_display(path: Path) -> str:
    """Return a short display path relative to the workspace."""
    s = str(path).replace("\\", "/")
    for prefix in [str(DOCS_ROOT).replace("\\", "/"), str(DOCS_SOURCE_ROOT).replace("\\", "/")]:
        if s.startswith(prefix):
            base = "docs-site/docs/" if "docs-site" in prefix else "docs/"
            return base + s[len(prefix):].lstrip("/")
    return s


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    """CLI entry point for standalone use."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Hive Documentation Standards Agent",
        epilog="Example: python -m agents.specialized.doc_standards_agent docs/my-doc.md --full-rewrite\n"
               "         python -m agents.specialized.doc_standards_agent  (no args = full DocSite scan)",
    )
    parser.add_argument("filepath", nargs="?", default=None, help="Path to a markdown document (omit for full DocSite scan)")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--source-ref", default="", help="Source reference URL or name")
    parser.add_argument("--urls", nargs="*", default=[], help="External URLs to fetch for citation context")
    parser.add_argument("--full-rewrite", action="store_true", help="Full LLM rewrite instead of incremental")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't write changes")

    args = parser.parse_args()

    # Configure logging for CLI
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    if args.filepath:
        # Single-file mode
        events = standardize_document(
            args.filepath,
            model=args.model,
            source_ref=args.source_ref,
            external_urls=args.urls or None,
            full_rewrite=args.full_rewrite,
            dry_run=args.dry_run,
        )
    else:
        # Batch mode — full DocSite alignment
        events = batch_scan(
            model=args.model,
            auto_fix=not args.dry_run,
            full_rewrite=args.full_rewrite,
        )

    for event in events:
        etype = event.get("type", "")
        econtent = event.get("content", "")
        if etype == "error":
            print(f"❌ {econtent}")
        elif etype == "status":
            print(f"  {econtent}")
        elif etype == "thought":
            print(f"  💭 {econtent}")
        elif etype == "log":
            print(f"  📝 {econtent}")
        elif etype in ("response", "message"):
            print(f"\n{econtent}")


if __name__ == "__main__":
    main()
