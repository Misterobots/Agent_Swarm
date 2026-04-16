"""
Prompt templates for the Documentation Standards Agent.

Provides the system instructions, analysis prompt, and section generation
prompts used by the hybrid doc_standards_agent.
"""

# ---------------------------------------------------------------------------
# Master template — defines the canonical structure every DocSite page must have
# ---------------------------------------------------------------------------
DOC_STANDARD_TEMPLATE = """\
---
title: "{title}"
doc_id: "{doc_id}"
last_updated: "{last_updated}"
source_ref: "{source_ref}"
---

# {title}

> **Document ID:** `{doc_id}` · **Source:** {source_ref} · **Last Updated:** {last_updated}

{description}

---

## Source Citations & References

| # | Source | URL / Path | License | Notes |
|---|--------|------------|---------|-------|
{citations_table}

---

## Changelog (Source → Implementation)

| Date | Change | Source Version | Hive Version | Author |
|------|--------|----------------|--------------|--------|
{changelog_table}

---

## Overview

{overview}

---

## Usage in the Hive

### When This Module Is Invoked

{when_invoked}

### How to Use

{how_to_use}

### Configuration

{configuration}

---

## Maintenance & Updates

### How to Update

{how_to_update}

### Dependencies

{dependencies}

### Health Checks

{health_checks}

---

## Functionality Testing

### Automated Tests

{automated_tests}

### Manual Verification

{manual_verification}

---

## UI, Screenshots & Examples

{ui_screenshots}

---

## Related Documentation

{related_docs}
"""

# ---------------------------------------------------------------------------
# ANALYSIS — determines what a doc is missing vs. the standard
# ---------------------------------------------------------------------------
ANALYSIS_SYSTEM_PROMPT = """\
You are the Documentation Standards Analyst for the Agentic Hive (Agent Swarm) project.
Your job is to compare a document against the Hive DocSite standard template and produce
a structured JSON analysis of what is present, what is missing, and what needs enhancement.

The standard requires every document to have:
1. YAML frontmatter with title, doc_id, last_updated, source_ref
2. Source Citations & References table
3. Changelog (Source → Implementation) table
4. Overview section
5. Usage in the Hive (when invoked, how to use, configuration)
6. Maintenance & Updates (how to update, dependencies, health checks)
7. Functionality Testing (automated tests, manual verification)
8. UI, Screenshots & Examples (with expandable/zoomable images using glightbox)
9. Related Documentation links

Respond ONLY with valid JSON using this schema:
{
  "title": "detected or suggested title",
  "doc_id": "detected or suggested DOC-XXXX-NNNN id",
  "source_ref": "detected source reference or 'Unknown'",
  "sections_present": ["list of standard sections found"],
  "sections_missing": ["list of standard sections NOT found"],
  "sections_needing_enhancement": [
    {"section": "name", "reason": "why it needs improvement"}
  ],
  "detected_citations": ["any URLs, project names, or references found in the doc"],
  "detected_images": ["any image paths or references found"],
  "images_need_lightbox": true/false,
  "overall_compliance_pct": 0-100,
  "suggested_doc_id": "DOC-CATEGORY-NNNN format"
}
"""

ANALYSIS_USER_PROMPT = """\
Analyze this document against the Hive DocSite standard:

---FILE: {filepath}---
{content}
---END FILE---

Return the JSON analysis.
"""

# ---------------------------------------------------------------------------
# SECTION GENERATION — LLM fills in missing/weak sections
# ---------------------------------------------------------------------------
SECTION_GEN_SYSTEM_PROMPT = """\
You are a Staff-Level Technical Writer for the Agentic Hive (Agent Swarm) project.
You write clear, accurate, professional documentation in MkDocs Material markdown.

Project context:
- 3-node distributed AI system: Gateway (R730, 192.168.2.103), Execution (Justin-PC, 192.168.2.101), Control (192.168.2.102)
- Stack: FastAPI, Ollama, ComfyUI, SPIRE, Langfuse, Docker Compose, Traefik
- MkDocs Material with glightbox, macros, mermaid diagrams
- All images must use the lightbox class for zoom: `![alt](path){{ loading=lazy }}` (attr_list)
- Use admonitions (tip, warning, note, example) where helpful
- Use Jinja2 macros for IPs/URLs: {{ gateway_node_ip }}, {{ execution_node_ip }}, etc.
- Be concise but thorough. Use tables, code blocks, and mermaid diagrams.

When generating content, use ONLY information from the provided source document and project context.
Do NOT fabricate specific implementation details you cannot verify.
Mark uncertain content with: `<!-- TODO: Verify -->`
"""

GENERATE_CITATIONS_PROMPT = """\
Based on this document, generate a Source Citations & References table in markdown.
Identify all external projects, libraries, protocols, APIs, or documentation referenced.
Format as:

| # | Source | URL / Path | License | Notes |
|---|--------|------------|---------|-------|
| 1 | Project Name | URL or file path | License if known | Brief note |

If a URL is uncertain, use `<!-- TODO: Verify URL -->` as placeholder.

Document:
{content}
"""

GENERATE_CHANGELOG_PROMPT = """\
Generate a Changelog (Source → Implementation) table for this document/component.
This tracks how the original source project/concept was adapted for the Hive.

Format as:

| Date | Change | Source Version | Hive Version | Author |
|------|--------|----------------|--------------|--------|
| YYYY-MM-DD | Description of change | vX.Y.Z or N/A | Phase N | Hive Team |

Use dates from git history if mentioned, otherwise use reasonable estimates.
Mark uncertain entries with `<!-- TODO: Verify -->`.

Document:
{content}
"""

GENERATE_USAGE_PROMPT = """\
Generate the "Usage in the Hive" section for this component/module, including:

1. **When This Module Is Invoked** — what intents, triggers, or conditions activate it
2. **How to Use** — step-by-step usage from the Hive UI or API
3. **Configuration** — environment variables, settings, tunables (use a table)

Base this on the document content below. Use admonitions for tips/warnings.
Use Jinja2 macros like {{ execution_node_ip }} for IPs.

Document:
{content}
"""

GENERATE_MAINTENANCE_PROMPT = """\
Generate the "Maintenance & Updates" section for this component, including:

1. **How to Update** — commands, procedures, Docker steps
2. **Dependencies** — upstream projects, internal dependencies (table format)
3. **Health Checks** — how to verify the component is healthy (commands, endpoints)

Be practical. Include actual commands where possible.
Use code blocks for commands. Use admonitions for warnings.

Document:
{content}
"""

GENERATE_TESTING_PROMPT = """\
Generate the "Functionality Testing" section for this component, including:

1. **Automated Tests** — pytest files, test commands, CI integration
2. **Manual Verification** — step-by-step manual test procedures

If test files exist, reference them. If not, suggest what tests should be created
and mark with `<!-- TODO: Create test file -->`.

Document:
{content}
"""

GENERATE_UI_EXAMPLES_PROMPT = """\
Generate the "UI, Screenshots & Examples" section for this component.

Rules:
- Reference existing screenshots if paths are detected in the document
- For all images, use MkDocs Material lightbox format:
  `<figure markdown="span">
    ![Description](path/to/image.png){{ loading=lazy }}
    <figcaption>Caption text</figcaption>
  </figure>`
- Include practical usage examples with code blocks
- If no screenshots exist, add placeholder directives:
  `!!! example "Screenshot Needed"
      <!-- TODO: Add screenshot of [specific UI element] -->`
- For mermaid diagrams, wrap in ```mermaid blocks

Document:
{content}
"""

GENERATE_RELATED_PROMPT = """\
Generate a "Related Documentation" section with links to other DocSite pages
that are relevant to this component. Use relative markdown links like:
- [Architecture: Topic](../architecture/topic.md)
- [Module: Name](../modules/name.md)
- [Procedure: Task](../procedures/task.md)

Known DocSite sections: architecture/, modules/, procedures/, tutorials/,
admin-guide/, developer-guide/, user-guide/, troubleshooting/, reference/

Document:
{content}
"""

# ---------------------------------------------------------------------------
# FULL STANDARDIZATION — one-shot rewrite for smaller docs
# ---------------------------------------------------------------------------
FULL_STANDARDIZE_PROMPT = """\
Rewrite this document to conform to the Hive DocSite standard template.
Apply ALL of these sections (skip none):

1. YAML frontmatter (title, doc_id as DOC-CATEGORY-NNNN, last_updated, source_ref)
2. Header with Document ID badge
3. Source Citations & References table
4. Changelog (Source → Implementation) table
5. Overview
6. Usage in the Hive (when invoked, how to use, configuration)
7. Maintenance & Updates (how to update, dependencies, health checks)
8. Functionality Testing (automated tests, manual verification)
9. UI, Screenshots & Examples (use glightbox format for all images)
10. Related Documentation

All images must use: `![alt](path){{ loading=lazy }}` for lightbox zoom.
Use admonitions, tables, mermaid diagrams, and code blocks.
Mark anything uncertain with `<!-- TODO: Verify -->`.

Original document:
{content}
"""

# ---------------------------------------------------------------------------
# EXTERNAL URL CONTEXT — for fetching and summarizing external references
# ---------------------------------------------------------------------------
EXTERNAL_CONTEXT_PROMPT = """\
Summarize this external documentation page for use as a source citation
in the Hive DocSite. Extract:
1. Project name and version
2. Key concepts relevant to our implementation
3. License information
4. Important API/configuration details

External page content:
{content}
"""
