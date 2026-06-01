---
title: Design Studio
---

# Design Studio

The Design Studio is a dedicated intent handler that generates self-contained HTML prototypes using local Ollama models. It is invoked when `design_mode=True` is set in the chat request, or when the router classifies intent as `DESIGN`.

## How it works

```
User message + attachments
  → church.py attachment bridge  (images → extracted_context, text files → decoded context)
  → detect_skill_from_prompt()   (user message, then context doc fallback)
  → get_skill_system_prompt()    (returns skill-specific instructions)
  → Ollama /api/chat             (with assistant prefill: "<!DOCTYPE html>")
  → parse_artifact_html()        (strips think-blocks, extracts HTML)
  → design_artifact SSE event    (HTML + OD project URL)
```

## Skill System

Design Studio selects a system prompt based on the user's intent. Skill detection uses **whole-word regex matching** (not substring matching — "graph" will not match inside "typography").

| Skill ID | Triggers | Description |
|---|---|---|
| `guizang-ppt` | deck, slide, presentation, ppt, pitch deck, slideshow | HTML slideshow (CSS scroll-snap, 5-8 slides) |
| `dashboard` | dashboard, analytics, data viz, chart, graph, kpi, monitoring, metrics | Dark-mode analytics dashboard with KPI cards |
| `saas-landing` | saas, marketing site, hero section, conversion, sign up page | SaaS marketing landing page |
| `mobile-app` | mobile app, ios app, android app, mobile ui, phone app, smartphone | Phone prototype at 390×844px in a frame |
| `immersive-ui` | **tablet**, kiosk, holographic, **immersive**, sci-fi ui, cinematic ui, full screen | Full-bleed 1280×800 tablet/kiosk interface |
| `web-prototype` | *(fallback — anything else)* | Generic polished interactive web prototype |

**Context fallback:** If the user message alone matches only `web-prototype`, Design Studio also scans the first 2 KB of any attached context document for skill keywords. This allows attaching a design brief that contains "tablet" without the message itself needing that word.

## Assistant Prefill

Design Studio injects `<!DOCTYPE html>\n<html lang="en">` as the start of the assistant turn in the Ollama chat API. This forces the model to begin generating HTML immediately — no preamble, no explanation. The prefill is prepended to `full_output` before `parse_artifact_html` runs.

## Attachment Pipeline

Files attached via the paperclip are processed by `church.py` before reaching the handler:

| MIME type | What happens |
|---|---|
| `image/*` | Promoted to `extracted_context` as `data:{mime};base64,{data}`. Binary data is stripped before passing to text models. |
| `text/*`, `application/json`, `application/pdf` | Base64-decoded, first 12 KB appended to `extracted_context` as labelled text block. |

Multiple attachments accumulate — they do not overwrite each other.

The entire `extracted_context` is prepended to the final model prompt under `[Attached context / reference material]`. This means an attached design brief or reference document is fully visible to the model during generation.

## Artifact Parsing

`parse_artifact_html()` in `open_design_client.py` extracts HTML from model output in four stages:

1. **Strip `<think>/<thinking>` blocks** — UltraThink reasoning tokens removed first
2. **OD artifact tags** — `<artifact ...>...</artifact>`
3. **Markdown code fences** — ` ```html...``` ` or ` ``` ` blocks containing HTML
4. **Embedded HTML** — `<!DOCTYPE html>` or `<html>` anywhere in the output
5. Returns `None` if none match → emits error event

## Open Design Integration

Design Studio creates an Open Design project for every run, providing an "Open Studio" deep-link. The OD daemon (`http://192.168.2.101:7456`) generates the project; HTML generation is handled by Ollama (the OD BYOK proxy blocks RFC1918 addresses).

Artifacts are saved locally to `/workspace/delivered_artifacts/design_{uuid}.html`.

## Usage

1. Toggle **Design Mode** on in the chat settings popover (Settings₂ icon in the input toolbar)
2. Optionally attach:
   - A design brief document (`.md`, `.txt`, `.json`) — gets injected as context
   - Reference images (`.jpg`, `.png`, `.webp`) — image content noted as placeholder since text models can't see them; a vision model will be needed for true visual analysis
3. Send your design request

For repeatable project designs, maintain a context document (e.g., `hhgttg-context.md`) and attach it with every run. The context doc survives across sessions and prevents re-deriving project conventions.

## Validated Techniques

These patterns produce reliable output from local models:

**Hollow/outlined text** — Use CSS `-webkit-text-stroke` with `color: transparent`:
```css
.outline-text {
    color: transparent;
    -webkit-text-stroke: 3px #1A2A35;
    font-family: 'Courier New', monospace;
    font-weight: 900;
}
```
Do NOT ask the model to construct letters from `<div>` elements — it will produce identical-looking shapes for every letter.

**Header + flex layout** — When an absolutely-positioned header sits inside a flex container, add `padding-top` equal to the header height:
```css
.content-area {
    display: flex;
    padding-top: 60px; /* prevents content hiding behind the 60px header */
}
```

**SVG illustrations** — Request specific named shapes (continent silhouettes, real objects) rather than generic geometric proxies. The model defaults to identical blobs if not given distinct descriptions.

## Configuration

Skill system prompts: `agents/specialized/open_design_client.py` — `SKILL_SYSTEM_PROMPTS` dict.

To add a new skill:

1. Add an entry to `SKILL_SYSTEM_PROMPTS`
2. Add trigger keywords to `detect_skill_from_prompt()`
3. If the skill ID differs from its internal name, add to `_SKILL_ID_MAP` in `handlers/design.py`

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `model did not produce an HTML artifact` | Model output has no parseable HTML | Check model is loaded; verify skill prompt isn't conflicting with user request |
| `generator didn't stop after throw()` | `_langfuse_span` double-yield bug | Fixed in `handlers/base.py` 2026-06-01; ensure latest code is deployed |
| `Skill: dashboard` for a non-dashboard request | Old substring matching; "typography" contains "graph" | Fixed 2026-06-01 with word-boundary regex; ensure latest code is deployed |
| Design Mode fires on plain messages | `designMode` toggle persisted from previous session | Click Settings₂ icon in chat toolbar, turn Design off |
