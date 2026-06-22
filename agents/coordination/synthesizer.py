"""Synthesis helpers — merging research findings into implementation plans."""

import json
import os
import re as _re

import requests
from ollama import Client

from config import COORDINATOR_MODEL, CONTEXT_WINDOWS
from logger_setup import setup_logger
from utils.gpu_queue import (
    call_with_model_fallback,
    get_swarm_worker_host,
    request_lock,
    select_available_model,
)

logger = setup_logger("Lamport")


def _synthesize_findings(findings: str, original_task: str) -> dict:
    """
    LLM synthesis step: read all research findings and produce an implementation plan.
    Returns dict: {"plan", "confidence", "ambiguity", "ambiguous_points",
                   "clarification_question", "suggested_answers"}
    """
    from config import COORDINATOR_MODEL as _COORD_MODEL, ROUTER_MODEL as _ROUTER_MODEL
    _preferred = os.getenv("COORDINATOR_MODEL", _COORD_MODEL)
    _fallback = os.getenv("ROUTER_MODEL", _ROUTER_MODEL)
    # Resolve once for context-window / log purposes. The inference call
    # below uses call_with_model_fallback to retry against the chain.
    synth_model, host = select_available_model(_preferred, [_fallback, "qwen3:8b"])

    system_prompt = (
        "You are a technical lead synthesizing research findings into an implementation plan.\n"
        "Rules:\n"
        "- Read ALL findings carefully\n"
        "- Identify key insights, constraints, and dependencies\n"
        "- Produce a clear, actionable implementation plan\n"
        "- Note any conflicts or gaps in the research\n"
        "- Be specific about file paths, function names, and technical details\n\n"
        "IMPORTANT: At the very end of your response, on its own line, output a JSON block:\n"
        '{"confidence": 0.92, "ambiguity": 0.03, "ambiguous_points": ["brief point 1"], '
        '"clarification_question": "Single direct question to ask the user", '
        '"suggested_answers": ["Concrete option A", "Concrete option B", "Concrete option C"]}\n'
        "confidence: 0.0–1.0 — how confident you are this plan is complete and correct\n"
        "ambiguity:  0.0–1.0 — how much unclear information remains (0 = none, 1 = all unclear)\n"
        "ambiguous_points: list of short strings naming WHAT is unclear (empty list if nothing is ambiguous)\n"
        "clarification_question: a single, direct question to ask the user when ambiguity > 0.05 — "
        "phrase it as a genuine question, NOT a statement of need (e.g. 'Which visual style do you prefer?' NOT 'Art style details needed')\n"
        "suggested_answers: 3–4 short concrete answer options the user could click to resolve the question — "
        "these should be specific, actionable choices (e.g. 'Dark neon cyberpunk with glowing UI', "
        "'Gritty industrial dystopia palette') — leave empty list [] if nothing is ambiguous"
    )

    try:
        MAX_FINDINGS_CHARS = 24000
        if len(findings) > MAX_FINDINGS_CHARS:
            findings = findings[:MAX_FINDINGS_CHARS] + "\n\n[...truncated for context window...]"

        prompt = (
            f"Original Task: {original_task}\n\n"
            f"Research Findings:\n{findings}\n\n"
            "Synthesize these findings into a concrete implementation plan."
        )

        def _call(model_name: str, host_url: str):
            # Synthesis generates up to 8 192 tokens; large models (gemma4:31b,
            # qwen3.6:27b) can need 2-5 minutes for cold VRAM load + generation.
            _timeout = 300 if any(m in model_name for m in ("gemma", "31b", "27b", "30b")) else 120
            return requests.post(
                f"{host_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 8192,
                        "num_ctx": CONTEXT_WINDOWS.get(model_name, CONTEXT_WINDOWS["default"]),
                    },
                },
                timeout=_timeout,
            )

        resp = call_with_model_fallback(_preferred, [_fallback, "qwen3:8b"], _call)
        try:
            synth_model = resp.json().get("model", synth_model)
        except Exception:
            pass
        logger.info(f"[Coordinator] Synthesis HTTP {resp.status_code}, response_len={len(resp.text)}")

        if resp.status_code == 200:
            resp_json = resp.json()
            raw_text = resp_json.get("response", "")
            thinking_text = resp_json.get("thinking", "") or ""
            if not raw_text:
                logger.warning(f"[Coordinator] Synthesis empty response. done_reason={resp_json.get('done_reason')} eval_count={resp_json.get('eval_count')} thinking_len={len(thinking_text)}")
            clean_text = _re.sub(r"```(?:json)?", "", raw_text, flags=_re.IGNORECASE).replace("```", "")
            confidence = 0.80
            ambiguity = 0.15
            ambiguous_points = []
            plan_text = raw_text
            scores = None
            last_brace = clean_text.rfind("{")
            if last_brace != -1:
                try:
                    decoder = json.JSONDecoder()
                    candidate = clean_text[last_brace:].strip()
                    parsed, end_pos = decoder.raw_decode(candidate)
                    if "confidence" in parsed:
                        scores = parsed
                        json_start = raw_text.rfind("{")
                        json_end = json_start + end_pos
                        text_before = raw_text[:json_start].rstrip()
                        text_after = raw_text[json_end:].strip()
                        plan_text = text_before if text_before else text_after
                except (json.JSONDecodeError, ValueError):
                    pass
            if scores is None:
                lines = raw_text.strip().splitlines()
                for line in reversed(lines):
                    stripped = line.strip()
                    if stripped.startswith("{") and "confidence" in stripped:
                        try:
                            scores = json.loads(stripped)
                            text_before = raw_text[: raw_text.rfind(stripped)].rstrip()
                            text_after = raw_text[raw_text.rfind(stripped) + len(stripped):].strip()
                            plan_text = text_before if text_before else text_after
                        except (json.JSONDecodeError, ValueError):
                            pass
                        break
            clarification_question = ""
            suggested_answers: list = []
            if scores:
                confidence = float(scores.get("confidence", 0.80))
                ambiguity = float(scores.get("ambiguity", 0.15))
                ambiguous_points = scores.get("ambiguous_points", [])
                if not isinstance(ambiguous_points, list):
                    ambiguous_points = []
                clarification_question = scores.get("clarification_question", "") or ""
                suggested_answers = scores.get("suggested_answers", []) or []
                if not isinstance(suggested_answers, list):
                    suggested_answers = []
                logger.info(
                    f"[Coordinator] Synthesis JSON parsed: confidence={confidence:.0%} "
                    f"ambiguity={ambiguity:.0%} points={ambiguous_points} "
                    f"question={clarification_question!r} suggestions={suggested_answers}"
                )
            else:
                logger.warning(f"[Coordinator] Could not parse synthesis JSON block from response tail: {raw_text[-200:]!r}")
            if not plan_text:
                if thinking_text:
                    plan_text = thinking_text
                    logger.info(
                        f"[Coordinator] Using 'thinking' field as synthesis plan "
                        f"({len(thinking_text)} chars, model put plan in <think> block)"
                    )
                else:
                    plan_text = "Synthesis failed — no response from model."
                    confidence = 0.0
                    ambiguity = 1.0
                    logger.warning(
                        "[Coordinator] Synthesis plan_text empty after JSON extraction — "
                        f"forcing confidence=0.0 to trigger retry. raw_text len={len(raw_text)}, "
                        f"scores={scores}"
                    )
            return {
                "plan": plan_text,
                "confidence": confidence,
                "ambiguity": ambiguity,
                "ambiguous_points": ambiguous_points,
                "clarification_question": clarification_question,
                "suggested_answers": suggested_answers,
            }
    except Exception as e:
        logger.error(f"[Coordinator] Synthesis failed: {e}")

    return {
        "plan": f"Synthesis failed. Raw findings:\n{findings}",
        "confidence": 0.50,
        "ambiguity": 0.50,
        "ambiguous_points": [],
        "clarification_question": "",
        "suggested_answers": [],
    }


def _generate_followups(synthesis: str, impl_tasks: list) -> str:
    """Build a short 'What next?' section appended to the final synthesis."""
    code_roles = {"coder", "devops", "architect"}
    has_code = any(t.get("role", "") in code_roles for t in impl_tasks)

    suggestions = []
    if has_code:
        suggestions.append("**🛠 Build it** — Ask me to implement a specific step from the plan above")
        suggestions.append("**🚀 DevOps** — Deploy and test this in the dev environment")
    else:
        suggestions.append("**📝 Draft it** — Have me write up a detailed spec or document for this plan")
    suggestions.append("**🔍 Dig deeper** — Ask me to expand on any specific section")
    suggestions.append("**🔄 Alternative** — Explore a completely different approach")

    lines = ["\n---", "**💡 What would you like to do next?**"]
    for s in suggestions[:3]:
        lines.append(f"- {s}")
    return "\n".join(lines)


def _synthesize_perspective_matrix(findings_by_perspective: dict[str, str], original_task: str) -> dict:
    """
    Merge per-perspective findings into a Perspective Matrix with convergent and divergent highlights.

    Returns::
        {
          "matrix_md": str,
          "convergent_points": list[str],
          "divergent_points": list[str],
          "controversy_level": "low"|"medium"|"high",
          "synthesis_narrative": str,
        }
    """
    _host = get_swarm_worker_host(COORDINATOR_MODEL)
    # timeout on Client constructor — ollama Python client does not accept timeout
    # as a kwarg on individual .chat() calls (raises TypeError in recent versions).
    # 300s accommodates gemma4:31b / qwen3.6:27b cold VRAM load + 8k token generation.
    client = Client(host=_host, timeout=300)

    schema = {
        "type": "object",
        "required": ["convergent_points", "divergent_points", "controversy_level", "synthesis_narrative"],
        "properties": {
            "convergent_points":   {"type": "array", "items": {"type": "string"}},
            "divergent_points":    {"type": "array", "items": {"type": "string"}},
            "controversy_level":   {"type": "string", "enum": ["low", "medium", "high"]},
            "synthesis_narrative": {"type": "string"},
        },
    }

    findings_text = "\n\n".join(
        f"=== {label} ===\n{text}" for label, text in findings_by_perspective.items()
    )

    prompt = (
        f"You are a research synthesis coordinator. Below are findings about the following "
        f"topic gathered from multiple distinct expert perspectives:\n\n"
        f"TOPIC: {original_task}\n\n"
        f"FINDINGS BY PERSPECTIVE:\n{findings_text}\n\n"
        f"Your tasks:\n"
        f"1. Identify CONVERGENT POINTS — facts, conclusions, or recommendations where ALL or "
        f"MOST perspectives agree. These are the most reliable takeaways.\n"
        f"2. Identify DIVERGENT POINTS — areas where perspectives CONFLICT, reach opposite "
        f"conclusions, or where the topic is genuinely controversial or contested. Be specific "
        f"about WHICH perspectives disagree and WHY.\n"
        f"3. Rate the overall CONTROVERSY LEVEL: 'low' (broad consensus), 'medium' (some tensions), "
        f"'high' (strong disagreements or value conflicts).\n"
        f"4. Write a synthesis_narrative (3-5 paragraphs) that integrates all perspectives, "
        f"names the tensions explicitly, and gives the user a balanced view.\n\n"
        f"Return valid JSON only."
    )

    result = {
        "convergent_points": [],
        "divergent_points": [],
        "controversy_level": "medium",
        "synthesis_narrative": "",
    }

    try:
        MAX_FINDING_CHARS = 6000
        truncated_findings = {}
        for label, text in findings_by_perspective.items():
            # Coerce non-string values defensively (primary fix is in executor._run_worker)
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
            truncated_findings[label] = (
                text[:MAX_FINDING_CHARS] + "\n[... truncated for synthesis ...]"
                if len(text) > MAX_FINDING_CHARS
                else text
            )
        findings_text_trunc = "\n\n".join(
            f"=== {label} ===\n{text}" for label, text in truncated_findings.items()
        )
        trunc_prompt = prompt.replace(findings_text, findings_text_trunc)

        with request_lock(context="text"):
            resp = client.chat(
                model=COORDINATOR_MODEL,
                messages=[{"role": "user", "content": trunc_prompt}],
                format=schema,
                options={"temperature": 0.3, "num_predict": 8192},
            )
        raw = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
        parsed = json.loads(raw)
        result.update(parsed)
        if not result.get("synthesis_narrative"):
            logger.warning("[Coordinator] _synthesize_perspective_matrix returned empty synthesis_narrative")
    except Exception as e:
        logger.warning(f"[Coordinator] _synthesize_perspective_matrix failed: {e}")

    table_rows = []
    for label, text in findings_by_perspective.items():
        # Guard: text must be a str; dicts/lists can slip in if a worker returns JSON content
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
        snippet = text.replace("\n", " ").strip()[:200]
        if len(text) > 200:
            snippet += "…"
        table_rows.append(f"| {label} | {snippet} |")

    table_md = (
        f"| Perspective | Summary |\n"
        f"|-------------|----------|\n"
        + "\n".join(table_rows)
    )

    convergent_md = (
        "\n".join(f"- {p}" for p in result["convergent_points"])
        or "_No strong convergent points identified._"
    )
    divergent_md = (
        "\n".join(f"- {p}" for p in result["divergent_points"])
        or "_No strong divergent points identified._"
    )

    controversy_alert = ""
    if result["controversy_level"] == "high":
        controversy_alert = (
            f"> **Controversy Alert** — Perspectives significantly disagree on this topic. "
            f"Consider which lens is most relevant to your context before acting on any single viewpoint.\n\n"
        )

    matrix_md = (
        f"## Perspective Research Matrix\n\n"
        f"{table_md}\n\n"
        f"### Convergent Points _(broad agreement across perspectives)_\n\n"
        f"{convergent_md}\n\n"
        f"### Divergent Points _(conflicting views or contested territory)_\n\n"
        f"{controversy_alert}"
        f"{divergent_md}\n\n"
        f"**Controversy Level:** {result['controversy_level'].capitalize()}\n\n"
        f"### Synthesis\n\n"
        f"{result['synthesis_narrative']}\n"
    )

    result["matrix_md"] = matrix_md
    return result
