"""Task decomposition — LLM-driven breakdown into research and implementation subtasks."""

import json
import os
import re as _re

import requests
from ollama import Client

from config import COORDINATOR_MODEL
from logger_setup import setup_logger
from utils.gpu_queue import get_swarm_worker_host, select_available_model
from coordination.pioneers import PERSPECTIVE_TAXONOMY

logger = setup_logger("Lamport")


def _decompose_task(user_input: str, history_context: str = "") -> dict:
    """
    Use LLM to decompose a complex task into subtasks.
    Returns dict with research_tasks, implementation_tasks, verification_criteria.
    """
    _preferred = os.getenv("COORDINATOR_MODEL", "qwen3:14b")
    _fallback = os.getenv("ROUTER_MODEL", "qwen3:8b")
    decompose_model, host = select_available_model(_preferred, [_fallback, "qwen3:8b"])

    system_prompt = (
        "You are a task decomposition engine. Given a complex task, break it into phases.\n"
        "Output ONLY valid JSON with this structure:\n"
        "{\n"
        '  "summary": "One-sentence summary of the task",\n'
        '  "scope": "codebase|external|unknown",\n'
        '  "project_type": "existing|new|unknown",\n'
        '  "clarification_needed": false,\n'
        '  "clarification_question": null,\n'
        '  "research_tasks": [\n'
        '    {"role": "researcher|architect|analyst", "task": "specific research question"}\n'
        "  ],\n"
        '  "implementation_tasks": [\n'
        '    {"role": "architect|coder|devops", "task": "specific implementation step"}\n'
        "  ],\n"
        '  "verification_criteria": ["criterion 1", "criterion 2"]\n'
        "}\n\n"
        "Rules:\n"
        "- research_tasks run in PARALLEL\n"
        "- implementation_tasks run SERIALLY\n"
        "- Keep tasks focused and actionable\n"
        "- Use role names: researcher, architect, coder, devops, analyst\n"
        "- 2-5 research tasks, 1-4 implementation tasks, 1-3 verification criteria\n\n"
        "RESEARCH TASK DIVERSITY (critical for scope='external'):\n"
        "When the task is research or analysis (scope='external'), you MUST generate 3-4 DISTINCT research tasks.\n"
        "Each task must investigate a DIFFERENT angle or sub-question. NEVER copy the user input verbatim into multiple tasks.\n"
        "Good research decomposition example for 'Explain NERC CIP standards':\n"
        "  1. researcher: What are the core NERC CIP reliability standards and their mandatory requirements?\n"
        "  2. researcher: What are the current compliance challenges and enforcement gaps in NERC CIP?\n"
        "  3. analyst: How do NERC CIP standards compare to other critical infrastructure frameworks (NIST, IEC 62443)?\n"
        "  4. researcher: What are real-world case studies of NERC CIP violations and their consequences?\n"
        "Each researcher should look at a UNIQUE aspect: requirements, implementation, history, comparisons, risks, or current state.\n\n"
        "SCOPE RULES:\n"
        "- scope='codebase': task involves writing, reading, or modifying code in an existing or new project\n"
        "- scope='external': task involves research, explanation, analysis, or web lookups with no code changes\n"
        "- scope='unknown': cannot determine without more information\n"
        "- project_type='existing': working with/inside an existing codebase\n"
        "- project_type='new': creating a brand new project/app from scratch\n"
        "- project_type='unknown': cannot determine (use only when scope='codebase')\n\n"
        "AMBIGUITY CHECK: Be extremely conservative — the default MUST be clarification_needed=false.\n"
        "Only set clarification_needed=true if ALL of the following are true:\n"
        "  1. A single CRITICAL piece of information is genuinely absent (not just nice-to-have)\n"
        "  2. Without it, research would go in the completely WRONG direction\n"
        "  3. The question cannot be reasonably inferred from context\n"
        "NEVER ask for clarification when:\n"
        "  - The request describes a creative project (game, app, website) with any style/mechanic/theme guidance\n"
        "  - The task is a build/make/create request with a clear subject\n"
        "  - The user has provided visual style, tone, audience, or feature descriptions\n"
        "  - You could make reasonable assumptions and proceed\n"
        "  - The question would be generic (e.g. 'provide more detail', 'what do you mean', 'more context')\n"
        "If you set clarification_needed=true, the clarification_question MUST be specific and actionable\n"
        "(e.g. 'Should this target mobile browsers or desktop only?'), NOT vague (e.g. 'Can you provide more detail?').\n"
        "Default: clarification_needed=false, clarification_question=null."
    )

    prompt = f"{history_context}\n\nTask to decompose:\n{user_input}" if history_context else user_input

    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": decompose_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": 0.3, "num_predict": 2048},
            },
            timeout=20,
        )

        if resp.status_code == 200:
            raw = resp.json().get("response", "{}") or "{}"
            raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip() or "{}"
            raw = _re.sub(r"```(?:json)?", "", raw, flags=_re.IGNORECASE).replace("```", "").strip()
            if not raw or raw == "{}":
                thinking = resp.json().get("thinking", "") or ""
                m = _re.search(r"\{.*\}", thinking, _re.DOTALL)
                raw = m.group(0) if m else "{}"
            parsed = json.loads(raw)
            if "research_tasks" not in parsed or not parsed["research_tasks"]:
                parsed["research_tasks"] = [{"role": "researcher", "task": user_input}]
            if "implementation_tasks" not in parsed or not parsed["implementation_tasks"]:
                parsed["implementation_tasks"] = [{"role": "architect", "task": user_input}]

            r_tasks = parsed.get("research_tasks", [])
            if (
                parsed.get("scope") == "external"
                and len(r_tasks) == 1
                and r_tasks[0].get("task", "").strip() == user_input.strip()
            ):
                logger.warning(
                    "[Coordinator] Decomposition returned single verbatim research task for external "
                    "scope — perspective mode will compensate."
                )
            if "verification_criteria" not in parsed or not parsed["verification_criteria"]:
                parsed["verification_criteria"] = ["Task completed correctly"]

            _GENERIC_PHRASES = (
                "more detail", "more context", "more information", "provide more",
                "can you clarify", "could you clarify", "what do you mean",
                "please clarify", "please provide", "help me proceed",
                "additional detail", "additional context", "additional information",
            )
            if parsed.get("clarification_needed"):
                q = (parsed.get("clarification_question") or "").lower()
                if not q or any(p in q for p in _GENERIC_PHRASES):
                    logger.info(
                        f"[Coordinator] Rejecting vague clarification question {q!r} — proceeding without clarification"
                    )
                    parsed["clarification_needed"] = False
                    parsed["clarification_question"] = None

            _BUILD_VERBS = frozenset({
                "build", "make", "create", "develop", "implement", "write", "code",
            })
            _SOFTWARE_ARTIFACTS = frozenset({
                "app", "website", "web app", "web application", "script", "function",
                "class", "api", "bot", "tool", "game", "program", "widget", "component",
                "feature", "backend", "frontend", "endpoint", "service", "microservice",
                "plugin", "extension", "dashboard", "cli", "command line", "mobile app",
                "interface", "module", "library", "package",
            })
            _input_lower = user_input.lower()
            if parsed.get("scope") == "unknown":
                _has_verb = bool(set(_input_lower.split()) & _BUILD_VERBS)
                _has_artifact = any(a in _input_lower for a in _SOFTWARE_ARTIFACTS)
                if _has_verb and _has_artifact:
                    logger.info(
                        "[Coordinator] Scope override: 'unknown' → 'codebase' "
                        "(software build verb + artifact detected)"
                    )
                    parsed["scope"] = "codebase"
                    if parsed.get("project_type") not in ("existing", "new"):
                        parsed["project_type"] = "new"

            return parsed
    except Exception as e:
        logger.error(f"[Coordinator] Task decomposition failed: {e}")

    _fl = user_input.lower()
    _CODE_VERBS = {"build", "create", "write", "implement", "fix", "improve", "refactor",
                   "develop", "update", "optimize", "debug", "work on", "code"}
    _CODE_NOUNS = {"app", "application", "script", "function", "class", "api", "bot",
                   "tool", "game", "program", "feature", "service", "module", "website",
                   "component", "code", "codebase", "implementation", "endpoint"}
    _has_code_verb = any(v in _fl for v in _CODE_VERBS)
    _has_code_noun = any(n in _fl for n in _CODE_NOUNS)
    _fallback_scope = "codebase" if (_has_code_verb and _has_code_noun) else "unknown"
    _new_words = {"new", "create", "build", "make", "from scratch", "fresh", "start"}
    _fallback_project_type = "new" if any(w in _fl for w in _new_words) else "unknown"
    return {
        "summary": user_input[:200],
        "scope": _fallback_scope,
        "project_type": _fallback_project_type,
        "research_tasks": [{"role": "researcher", "task": user_input}],
        "implementation_tasks": [{"role": "architect", "task": user_input}],
        "verification_criteria": ["Task completed correctly"],
    }


def _decompose_task_perspectives(user_input: str, history_context: str = "") -> dict:
    """
    Ask the LLM whether a topic is multi-faceted and, if so, which perspectives apply.

    Returns::
        {
          "is_multifaceted": bool,
          "perspectives": [
              {"role": str, "perspective_label": str, "task": str, "lens_description": str},
              ...
          ],
          "summary": str,
        }
    """
    _host = get_swarm_worker_host(COORDINATOR_MODEL)
    client = Client(host=_host)

    schema = {
        "type": "object",
        "required": ["is_multifaceted", "perspectives", "summary"],
        "properties": {
            "is_multifaceted": {"type": "boolean"},
            "summary": {"type": "string"},
            "perspectives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["role", "perspective_label", "task", "lens_description"],
                    "properties": {
                        "role":               {"type": "string"},
                        "perspective_label":  {"type": "string"},
                        "task":               {"type": "string"},
                        "lens_description":   {"type": "string"},
                    },
                },
            },
        },
    }

    taxonomy_list = ", ".join(PERSPECTIVE_TAXONOMY)
    prompt = (
        f"You are a research planning coordinator. Analyse the following topic:\n\n"
        f"TOPIC: {user_input}\n\n"
        f"HISTORY CONTEXT:\n{history_context[:800]}\n\n"
        f"Decide whether this topic is multi-faceted — i.e. it has meaningfully different "
        f"implications depending on the viewpoint (e.g. technical, ethical, economic, regulatory). "
        f"A topic is multi-faceted when at least 3 distinct perspectives from the taxonomy below "
        f"would each produce substantially different findings or reach different conclusions.\n\n"
        f"Available perspective roles: {taxonomy_list}\n\n"
        f"If multi-faceted, choose 3–5 perspectives that are MOST relevant to this topic. "
        f"For each perspective:\n"
        f"  - role: one of the taxonomy values above\n"
        f"  - perspective_label: short human-readable label (e.g. 'Technical Analysis')\n"
        f"  - task: the SAME topic reframed as a research task through that lens\n"
        f"  - lens_description: 1-sentence description of what this lens focuses on\n\n"
        f"Return valid JSON only."
    )

    try:
        resp = client.chat(
            model=COORDINATOR_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format=schema,
            options={"temperature": 0.2, "num_predict": 1200},
        )
        raw = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[Coordinator] _decompose_task_perspectives failed: {e}")
        return {"is_multifaceted": False, "perspectives": [], "summary": user_input[:200]}
