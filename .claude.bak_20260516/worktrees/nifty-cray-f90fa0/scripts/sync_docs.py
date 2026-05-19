#!/usr/bin/env python3
"""
Build-time sync: merge enhanced docs/ content into docs-site/docs/.

Run from repo root:
    python scripts/sync_docs.py

Phases:
  1. Copy screenshots to docs-site/docs/assets/screenshots/
  2. Create new feature pages (Buddy, Plan/Think modes)
  3. Append enhancement sections to existing pages
"""

import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
SITE = REPO / "docs-site" / "docs"

# ---------------------------------------------------------------------------
# Phase 1: Screenshot sync
# ---------------------------------------------------------------------------

def sync_screenshots():
    """Copy all screenshots from docs/assets/screenshots → docs-site/docs/assets/screenshots."""
    src_dirs = [
        DOCS / "assets" / "screenshots",
        DOCS / "screenshots",
    ]
    dst_dir = SITE / "assets" / "screenshots"
    dst_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src_dir in src_dirs:
        if not src_dir.exists():
            continue
        for f in src_dir.glob("*.png"):
            dst = dst_dir / f.name
            shutil.copy2(f, dst)
            copied += 1
    print(f"  Screenshots: {copied} files → {dst_dir.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# Phase 2: New pages — copy with path + frontmatter adjustments
# ---------------------------------------------------------------------------

# Mapping: (source in docs/, destination in docs-site/docs/, yaml title)
NEW_PAGES = [
    (
        "user/buddy_companion_guide.md",
        "user-guide/buddy.md",
        "Buddy Companion",
    ),
    (
        "user/plan_and_think_modes.md",
        "user-guide/plan-think.md",
        "Plan & Think Modes",
    ),
]


def _fix_content(content: str, dest_rel: str) -> str:
    """Adjust image paths and internal links for docs-site nesting."""
    # Fix screenshot paths:  ../assets/screenshots/ → ../../assets/screenshots/
    # (user-guide/ pages are one level deep from docs-site/docs/)
    depth = dest_rel.count("/")
    prefix = "../" * depth

    content = content.replace("../assets/screenshots/", f"{prefix}assets/screenshots/")
    content = content.replace("../screenshots/", f"{prefix}assets/screenshots/")

    # Remove "Back to: ... INDEX.md" nav lines (not relevant in MkDocs)
    content = re.sub(r"> \*\*Back to:\*\*.*\n", "", content)

    # Strip raw INDEX.md links
    content = content.replace("](../INDEX.md)", "](../../index.md)")

    return content


def create_new_pages():
    """Copy enhanced docs/ files as new pages in docs-site/docs/."""
    for src_rel, dst_rel, title in NEW_PAGES:
        src = DOCS / src_rel
        dst = SITE / dst_rel
        if not src.exists():
            print(f"  SKIP (not found): {src_rel}")
            continue

        content = src.read_text(encoding="utf-8")
        content = _fix_content(content, dst_rel)

        # Replace first H1 with yaml frontmatter + H1
        h1_match = re.match(r"^#\s+(.+)\n", content)
        if h1_match:
            original_title = h1_match.group(1)
            frontmatter = f"---\ntitle: \"{title}\"\n---\n\n# {original_title}\n"
            content = frontmatter + content[h1_match.end():]
        else:
            content = f"---\ntitle: \"{title}\"\n---\n\n{content}"

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        print(f"  NEW: {dst_rel} ← {src_rel}")


# ---------------------------------------------------------------------------
# Phase 3: Append enhancement sections to existing pages
# ---------------------------------------------------------------------------

# Markers that delimit enhancement sections in docs/ files
ENHANCEMENT_MARKERS = [
    "## Source References",
    "## Changelog",
    "## Maintenance & Update Guide",
    "## Functionality Testing",
]

# Mapping: (docs/ source, docs-site/docs/ target, which H2 sections to extract)
ENHANCEMENTS = [
    (
        "user/art_studio_guide.md",
        "user-guide/art-studio.md",
        ["Source References", "Changelog", "Maintenance & Update Guide", "Functionality Testing"],
    ),
    (
        "user/overview.md",
        "user-guide/index.md",
        ["Source References", "Changelog", "Maintenance & Update Guide", "Functionality Testing"],
    ),
    (
        "admin/technical_reference.md",
        "admin-guide/port-map.md",
        ["Source References", "Changelog", "Maintenance & Update Guide", "Functionality Testing"],
    ),
]


def _extract_sections(content: str, section_names: list[str]) -> str:
    """Extract named H2 sections from markdown content."""
    blocks = []
    for name in section_names:
        # Match from "## Name" to next "## " or "---\n" end-of-section or EOF
        pattern = rf"(## {re.escape(name)}.*?)(?=\n## |\n---\s*\n<details>|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            blocks.append(match.group(1).rstrip())
    return "\n\n---\n\n".join(blocks)


def _has_section(content: str, name: str) -> bool:
    return f"## {name}" in content


def append_enhancements():
    """Append enhancement sections from docs/ files to docs-site/docs/ pages."""
    for src_rel, dst_rel, sections in ENHANCEMENTS:
        src = DOCS / src_rel
        dst = SITE / dst_rel
        if not src.exists() or not dst.exists():
            print(f"  SKIP: {src_rel} or {dst_rel} not found")
            continue

        src_content = src.read_text(encoding="utf-8")
        dst_content = dst.read_text(encoding="utf-8")

        # Only extract sections not already present
        needed = [s for s in sections if not _has_section(dst_content, s)]
        if not needed:
            print(f"  SKIP (already enhanced): {dst_rel}")
            continue

        extracted = _extract_sections(src_content, needed)
        if not extracted:
            print(f"  SKIP (no sections found in source): {src_rel}")
            continue

        extracted = _fix_content(extracted, dst_rel)

        # Append with separator
        dst_content = dst_content.rstrip() + "\n\n---\n\n" + extracted + "\n"
        dst.write_text(dst_content, encoding="utf-8")
        print(f"  ENHANCED: {dst_rel} (+{', '.join(needed)})")


# ---------------------------------------------------------------------------
# Phase 4: Also copy the 4 deep-dive specs as architecture sub-pages
# ---------------------------------------------------------------------------

SPEC_PAGES = [
    ("architecture/jwt_ace_card_lifecycle_deep_dive.md", "architecture/jwt-ace-deep-dive.md", "JWT-ACE Card Lifecycle Deep Dive"),
    ("architecture/marsrl_inference_verification_deep_dive.md", "architecture/marsrl-deep-dive.md", "MarsRL Inference Verification Deep Dive"),
    ("architecture/mempalace_integration_deep_dive.md", "architecture/mempalace-deep-dive.md", "MemPalace Integration Deep Dive"),
    ("architecture/memory_preferences_subsystem_deep_dive.md", "architecture/memory-preferences-deep-dive.md", "Memory & Preferences Deep Dive"),
    ("architecture/router_intent_token_flow_deep_dive.md", "architecture/router-intent-deep-dive.md", "Router Intent & Token Flow Deep Dive"),
    ("architecture/skills_hooks_pipeline_deep_dive.md", "architecture/skills-hooks-deep-dive.md", "Skills & Hooks Pipeline Deep Dive"),
]


def create_spec_pages():
    """Copy deep-dive specs into docs-site architecture section."""
    for src_rel, dst_rel, title in SPEC_PAGES:
        src = DOCS / src_rel
        dst = SITE / dst_rel
        if not src.exists():
            print(f"  SKIP (not found): {src_rel}")
            continue

        content = src.read_text(encoding="utf-8")
        content = _fix_content(content, dst_rel)

        h1_match = re.match(r"^#\s+(.+)\n", content)
        if h1_match:
            original_title = h1_match.group(1)
            frontmatter = f"---\ntitle: \"{title}\"\n---\n\n# {original_title}\n"
            content = frontmatter + content[h1_match.end():]
        else:
            content = f"---\ntitle: \"{title}\"\n---\n\n{content}"

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        print(f"  SPEC: {dst_rel} ← {src_rel}")


# ---------------------------------------------------------------------------

def main():
    print("=== Docs Sync: docs/ → docs-site/docs/ ===\n")
    print("[Phase 1] Screenshots")
    sync_screenshots()
    print("\n[Phase 2] New feature pages")
    create_new_pages()
    print("\n[Phase 3] Enhancement sections")
    append_enhancements()
    print("\n[Phase 4] Deep-dive spec pages")
    create_spec_pages()
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
