"""
Lamport Coordinator — main orchestration generator and project onboarding flow.

Phases:
    1. Decompose (LLM) — break task into subtasks
    2. Research (parallel workers) — investigate unknowns
    3. Synthesize (LLM) — merge findings into plan, score confidence
    4. Implement (workers) — execute the plan
    5. Verify (fresh worker) — check results
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as futures_wait
from typing import Generator, Optional

from config import ARCHITECT_MODEL
from logger_setup import setup_logger
from utils.gpu_queue import request_lock

from coordination.decomposer import _decompose_task, _decompose_task_perspectives
from coordination.executor import _derive_worker_token, _get_agent_for_role, _run_worker
from coordination.palace import (
    _palace_project_lookup, _palace_project_save, _team_store, _team_clear,
)
from coordination.session import CoordinatorSession, WorkerState
from coordination.synthesizer import (
    _generate_followups, _synthesize_findings, _synthesize_perspective_matrix,
)

logger = setup_logger("Lamport")


def coordinate_project_onboarding(
    original_prompt: str,
    session_id: str = "default_session",
    owner_id: str = None,
) -> Generator[dict, None, None]:
    """
    Multi-step onboarding flow for brand-new projects.
    Emits a sequence of clarification_card events and on completion
    creates a workspace/<project-name>/ directory.
    """
    try:
        from brooks import save_pending_context as _save_ctx
        _save_ctx(
            {
                "type": "project_onboarding_step_1",
                "original_prompt": original_prompt,
            },
            session_id=session_id,
            owner_id=owner_id,
        )
    except Exception as _e:
        logger.warning(f"[Onboarding] Could not save step 1 context: {_e}")

    yield {
        "type": "clarification_card",
        "clarification": {
            "question": "What would you like to call this project, and what type is it?",
            "context": f"Let's set up your new project: *{original_prompt[:120]}*",
            "options": [
                {"label": "Web App", "value": "type:web", "description": "Next.js / React"},
                {"label": "API / Backend", "value": "type:api", "description": "FastAPI / Node"},
                {"label": "CLI Tool", "value": "type:cli", "description": "Python / Bash"},
                {"label": "Library / Package", "value": "type:lib", "description": "Reusable module"},
            ],
            "allow_freetext": True,
            "card_type": "onboarding",
        },
    }


def coordinate_task(
    user_input: str,
    session_id: str = "default_session",
    owner_id: str = None,
    history_context: str = "",
    extracted_context: str = "",
    ace_token: str = None,
    template_metadata: dict = None,
    ultraplan_mode: bool = False,
    dev_mode: bool = False,
    plan_mode: bool = False,
    research_mode: bool = False,
    skip_project_gate: bool = False,
    already_steered: bool = False,
) -> Generator[dict, None, None]:
    """
    Main coordinator generator. Yields status/progress/response dicts
    matching the chat_swarm() yield contract.
    """
    session = CoordinatorSession(session_id, owner_id)
    logger.info(
        f"[Coordinator] Starting coordination {session.coordination_id} "
        f"for session {session_id}"
    )

    try:
        # === PHASE 1: DECOMPOSE ===
        yield {"type": "swarm_phase", "phase_num": 1, "phase_name": "Decompose", "total_phases": 5}
        yield {"type": "status", "content": "🧩 Coordinator: Decomposing task..."}
        yield {"type": "thought", "content": "→ Phase 1/5: Task Decomposition (LLM)"}

        # Zone-aware GPU prep — only evict if we're actually switching away from an
        # image/compose context.  Runs AFTER the first yield so the client sees
        # activity immediately instead of waiting up to 180 s in silence.
        try:
            from utils.gpu_queue import get_redis_client as _grc, ZONE_KEY as _ZK
            _current_zone = _grc().get(_ZK)
            if _current_zone and _current_zone != "text":
                yield {"type": "status", "content": "⚡ Releasing image pipeline VRAM for text inference..."}
                from utils.gpu_queue import evict_klein as _ek, evict_comfyui as _ec
                _ek()
                _ec()
                _grc().set(_ZK, "text")
                yield {"type": "log", "content": "[Coordinator] GPU zone → text."}
        except Exception as _e:
            logger.warning(f"[Coordinator] GPU zone check skipped (non-fatal): {_e}")

        plan = _decompose_task(user_input, history_context, already_steered=already_steered)
        summary = plan.get("summary", user_input[:200])
        research_tasks = plan.get("research_tasks", [])
        impl_tasks = plan.get("implementation_tasks", [])
        verification_criteria = plan.get("verification_criteria", [])
        scope = plan.get("scope", "unknown")
        project_type = plan.get("project_type", "unknown")

        # --- AMBIGUITY GATE ---
        if plan.get("clarification_needed", False):
            question = plan.get(
                "clarification_question",
                "Could you provide more context about what you're trying to achieve?",
            )
            logger.info(f"[Coordinator] Clarification needed: {question}")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "swarm_clarification", "prompt": user_input, "question": question},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save clarification context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": question,
                    "context": "I need a little more information before assembling the research team.",
                    "options": [],
                    "allow_freetext": True,
                    "card_type": "ambiguity",
                },
            }
            return

        # --- NUANCE STEERING GATE ---
        # Fires when the task is clear but has multiple meaningfully different valid directions.
        # Unlike the ambiguity gate (missing info), this catches well-specified requests where
        # choosing the wrong approach would waste the research team's effort.
        # The user picks a direction; the coordinator resumes with that context via Brooks.
        if plan.get("nuance_detected", False) and not dev_mode and not research_mode and not already_steered:
            steering_q = plan.get(
                "steering_question",
                "Which angle would be most valuable to explore?",
            )
            suggested_dirs = plan.get("suggested_directions", [])
            logger.info(
                f"[Coordinator] Nuance detected — steering question: {steering_q!r} "
                f"({len(suggested_dirs)} directions)"
            )
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {
                        "type": "swarm_steering",
                        "prompt": user_input,
                        "question": steering_q,
                        "suggested_directions": suggested_dirs,
                    },
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save steering context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": steering_q,
                    "context": (
                        f"I can approach **{summary}** from several angles. "
                        "Pointing me in the right direction will make the research team much more effective."
                    ),
                    "options": [
                        {
                            "label": d.get("label", d.get("value", "Option")),
                            "value": d.get("value", d.get("label", "option")),
                            "description": d.get("description", ""),
                        }
                        for d in suggested_dirs
                    ],
                    "allow_freetext": True,
                    "card_type": "steering",
                },
            }
            return

        # --- LOW CONFIDENCE GATE ---
        if scope == "unknown" and not dev_mode and not research_mode and not plan_mode:
            logger.info("[Coordinator] Scope unknown after decomposition — prompting user to classify intent.")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "task_intent_clarification", "prompt": user_input, "summary": summary},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save task_intent context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": "How would you like to approach this?",
                    "context": f"I wasn't sure how to classify this request: *{summary}*",
                    "options": [
                        {
                            "label": "Research it",
                            "value": "research_it",
                            "description": "Deep-dive, multi-perspective analysis — no code changes",
                        },
                        {
                            "label": "Plan it",
                            "value": "plan_it",
                            "description": "Architecture and design documents — no code written",
                        },
                        {
                            "label": "Build it",
                            "value": "build_it",
                            "description": "Create or modify code in a project",
                        },
                    ],
                    "allow_freetext": True,
                    "card_type": "task_intent",
                },
            }
            return

        # --- DEV PROJECT GATE ---
        _should_gate = (
            (scope == "codebase")
            or (scope == "unknown" and dev_mode and not research_mode)
        )
        if _should_gate and not skip_project_gate and not plan_mode:
            logger.info(f"[Coordinator] Codebase task detected (project_type={project_type}), asking for project routing.")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "dev_project_clarification", "prompt": user_input, "summary": summary},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning(f"[Coordinator] Could not save dev project context: {_e}")
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": "Is this for an existing project or a new one?",
                    "context": f"I detected a coding task: *{summary}*",
                    "options": [
                        {
                            "label": "Existing project",
                            "value": "existing_project",
                            "description": "I'll work within your current codebase",
                        },
                        {
                            "label": "New project",
                            "value": "new_project",
                            "description": "Walk me through setup",
                            "redirect": None,
                        },
                        {
                            "label": "Just plan it",
                            "value": "plan_only",
                            "description": "Research and plan, no files changed",
                        },
                    ],
                    "allow_freetext": False,
                    "card_type": "dev_project",
                },
            }
            return

        yield {
            "type": "log",
            "content": (
                f"[Coordinator] Decomposed into {len(research_tasks)} research "
                f"+ {len(impl_tasks)} implementation tasks"
            ),
        }
        yield {"type": "message", "content": f"**📋 Task Plan: {summary}**\n\n"}

        if research_tasks:
            task_list = "\n".join(
                f"  {i+1}. **{t['role']}** — {t['task']}"
                for i, t in enumerate(research_tasks)
            )
            yield {
                "type": "message",
                "content": (
                    f"**🔬 Research Phase** ({len(research_tasks)} workers, parallel):\n"
                    f"{task_list}\n\n"
                ),
            }
        if impl_tasks:
            task_list = "\n".join(
                f"  {i+1}. **{t['role']}** — {t['task']}"
                for i, t in enumerate(impl_tasks)
            )
            yield {
                "type": "message",
                "content": (
                    f"**🔨 Implementation Phase** ({len(impl_tasks)} tasks):\n"
                    f"{task_list}\n\n"
                ),
            }

        session.write_to_scratchpad("00_plan.json", json.dumps(plan, indent=2))

        # -----------------------------------------------------------------------
        # PERSPECTIVE RESEARCH FLOW
        # -----------------------------------------------------------------------
        _use_perspective_mode = research_mode
        _perspective_probe: dict = {}

        # Creative writing tasks are NOT multi-faceted research topics — skip perspective mode.
        _CREATIVE_SIGNALS = frozenset([
            "write a scene", "describe a scene", "write a story", "write a description",
            "scene description", "vivid description", "creative writing", "detailed description",
            "fiction", "fictional", "roleplay", "role-play", "fanfic", "fan fiction",
            "worldbuilding", "world building", "lore", "narrative", "screenplay",
            "shadowrun", "cyberpunk", "in the universe of", "in the world of",
            "fantasy scene", "fantasy setting",
        ])
        _input_lower_persp = user_input.lower()
        _is_creative_task = any(sig in _input_lower_persp for sig in _CREATIVE_SIGNALS)

        if research_mode and not _use_perspective_mode and not _is_creative_task:
            yield {"type": "thought", "content": "→ Checking if topic is multi-faceted for perspective mode..."}
            _perspective_probe = _decompose_task_perspectives(user_input, history_context)
            _use_perspective_mode = _perspective_probe.get("is_multifaceted", False)
            if _use_perspective_mode:
                yield {"type": "thought", "content": "→ Multi-faceted topic detected — activating Perspective Research Mode"}
                yield {"type": "log", "content": "[Coordinator] Auto-activated perspective research mode"}
        elif _is_creative_task and not _use_perspective_mode:
            yield {"type": "thought", "content": "→ Creative writing task detected — skipping perspective research mode"}

        if _use_perspective_mode:
            if not _perspective_probe:
                _perspective_probe = _decompose_task_perspectives(user_input, history_context)

            perspectives = _perspective_probe.get("perspectives", [])
            if not perspectives:
                perspectives = [
                    {"role": "technical",   "perspective_label": "Technical Analysis",   "task": user_input, "lens_description": "Engineering and implementation perspective"},
                    {"role": "ethical",     "perspective_label": "Ethical Analysis",     "task": user_input, "lens_description": "Moral and societal impact perspective"},
                    {"role": "economic",    "perspective_label": "Economic Analysis",    "task": user_input, "lens_description": "Financial and market perspective"},
                ]

            yield {
                "type": "message",
                "content": (
                    f"**🔬 Perspective Research Mode** — {len(perspectives)} lenses activated\n\n"
                    + "\n".join(f"- **{p['perspective_label']}**: {p['lens_description']}" for p in perspectives)
                    + "\n\n"
                ),
            }

            yield {"type": "swarm_phase", "phase_num": 2, "phase_name": "Research", "total_phases": 4}
            yield {
                "type": "status",
                "content": f"🔬 Launching {len(perspectives)} perspective research workers...",
            }

            findings_by_perspective: dict[str, str] = {}
            max_workers_p = min(len(perspectives), 3)

            with ThreadPoolExecutor(max_workers=max_workers_p) as pool:
                futures_p = {}
                for i, persp in enumerate(perspectives):
                    role = persp.get("role", "researcher")
                    label = persp.get("perspective_label", role.capitalize())
                    task_text = persp.get("task", user_input)
                    lens_desc = persp.get("lens_description", "")

                    persp_prompt = (
                        f"[Perspective Research Task: {label}]\n\n"
                        f"TOPIC: {task_text}\n\n"
                        f"YOUR LENS: {lens_desc}\n"
                        f"You are analyzing this topic EXCLUSIVELY through the lens of a {label} expert. "
                        f"Actively look for where this perspective DISAGREES with or COMPLICATES mainstream "
                        f"consensus or other viewpoints. Highlight any tensions, trade-offs, or controversial "
                        f"aspects that are most visible from this lens. Do not simply agree with the default "
                        f"view — probe for what YOUR perspective uniquely reveals.\n\n"
                        f"Produce a detailed, structured analysis. Use headings. End with a summary "
                        f"'Key Takeaways from the {label} Perspective'."
                    )
                    if extracted_context:
                        persp_prompt += f"\n\n[Context]:\n{extracted_context}"

                    worker_id = session.register_worker(role, task_text, "research")
                    agent = _get_agent_for_role("researcher", session_id=session_id, scope="research")
                    child_token = _derive_worker_token(ace_token, role, task_text)

                    future = pool.submit(
                        _run_worker, session, worker_id, agent, persp_prompt,
                        child_token=child_token,
                    )
                    futures_p[future] = (worker_id, role, label)
                    pioneer = session.workers[worker_id].pioneer
                    yield {
                        "type": "swarm_worker_created",
                        "worker_id": worker_id,
                        "role": role,
                        "pioneer_name": pioneer["name"],
                        "pioneer_full_name": pioneer["full_name"],
                        "pioneer_motto": pioneer["motto"],
                        "task": f"[{label}] {task_text[:80]}",
                        "phase": "research",
                        "content": f"Spawned {pioneer['name']} ({label})",
                    }

                _pending_p = set(futures_p.keys())
                while _pending_p:
                    _done_p, _pending_p = futures_wait(_pending_p, timeout=20)
                    if not _done_p:
                        yield {"type": "heartbeat", "content": ""}
                        continue
                    for future in _done_p:
                        worker_id, role, label = futures_p[future]
                        try:
                            result = future.result()
                            findings_by_perspective[label] = result or ""
                            worker = session.workers[worker_id]
                            elapsed = (
                                (worker.completed_at or time.time())
                                - (worker.started_at or time.time())
                            )
                            pioneer = worker.pioneer
                            yield {
                                "type": "message",
                                "content": f"✅ **{pioneer['name']}** ({label}) completed in {elapsed:.1f}s\n\n",
                            }
                            _team_store(
                                session.coordination_id,
                                f"perspective_{label}_{worker_id}",
                                result[:2000] if result else "",
                                author=role,
                            )
                        except Exception as e:
                            yield {
                                "type": "log",
                                "content": f"[Coordinator] Perspective worker {label} failed: {e}",
                            }
                            yield {
                                "type": "message",
                                "content": f"⚠️ **{label}** worker failed: {e}\n\n",
                            }

            yield {"type": "swarm_phase", "phase_num": 3, "phase_name": "Synthesize", "total_phases": 4}
            yield {"type": "status", "content": "🧠 Building Perspective Matrix..."}
            yield {"type": "thought", "content": "→ Phase 3/4: Perspective Matrix synthesis"}

            persp_matrix = _synthesize_perspective_matrix(findings_by_perspective, user_input)
            matrix_md = persp_matrix.get("matrix_md", "")

            session.write_to_scratchpad("01_perspective_matrix.md", matrix_md)
            _team_store(session.coordination_id, "perspective_matrix", matrix_md)

            yield {"type": "message", "content": "**🧠 Perspective Matrix Complete** ✓\n\n"}

            yield {"type": "swarm_phase", "phase_num": 4, "phase_name": "Verify", "total_phases": 4}

            total_time = time.time() - session.created_at
            total_workers = len(session.workers)
            completed = sum(1 for w in session.workers.values() if w.state == WorkerState.COMPLETED)
            failed = sum(1 for w in session.workers.values() if w.state == WorkerState.FAILED)

            yield {
                "type": "message",
                "content": (
                    f"---\n"
                    f"**📊 Perspective Research Summary**\n"
                    f"- Perspectives researched: {len(findings_by_perspective)}\n"
                    f"- Convergent points: {len(persp_matrix.get('convergent_points', []))}\n"
                    f"- Divergent points: {len(persp_matrix.get('divergent_points', []))}\n"
                    f"- Controversy level: {persp_matrix.get('controversy_level', 'unknown')}\n"
                    f"- Completed workers: {completed} | Failed: {failed}\n"
                    f"- Total time: {total_time:.1f}s\n"
                ),
            }

            followup_section = _generate_followups(persp_matrix.get("synthesis_narrative", ""), [])
            yield {"type": "response", "content": f"{matrix_md}{followup_section}"}
            logger.info(
                f"[Coordinator] Perspective research {session.coordination_id} complete: "
                f"{completed}/{total_workers} workers, {total_time:.1f}s, "
                f"controversy={persp_matrix.get('controversy_level')}"
            )
            return

        # === PHASE 2: RESEARCH (parallel) ===
        yield {"type": "swarm_phase", "phase_num": 2, "phase_name": "Research", "total_phases": 5}
        yield {
            "type": "status",
            "content": f"🔬 Coordinator: Launching {len(research_tasks)} research workers...",
        }
        yield {
            "type": "thought",
            "content": f"→ Phase 2/5: Research ({len(research_tasks)} parallel workers)",
        }

        research_results = {}
        if research_tasks:
            max_workers = min(len(research_tasks), 3)

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for i, task_def in enumerate(research_tasks):
                    role = task_def.get("role", "researcher")
                    task_text = task_def.get("task", "")

                    worker_id = session.register_worker(role, task_text, "research")
                    agent = _get_agent_for_role(role, session_id=session_id, scope=scope)
                    child_token = _derive_worker_token(ace_token, role, task_text)

                    worker_prompt = (
                        f"[Research Task {i+1}/{len(research_tasks)}]\n{task_text}"
                    )
                    if extracted_context:
                        worker_prompt += f"\n\n[Available Context]:\n{extracted_context}"

                    future = pool.submit(
                        _run_worker, session, worker_id, agent, worker_prompt,
                        child_token=child_token,
                    )
                    futures[future] = (worker_id, role, task_text)
                    pioneer = session.workers[worker_id].pioneer
                    yield {
                        "type": "swarm_worker_created",
                        "worker_id": worker_id,
                        "role": role,
                        "pioneer_name": pioneer["name"],
                        "pioneer_full_name": pioneer["full_name"],
                        "pioneer_motto": pioneer["motto"],
                        "task": task_text,
                        "phase": "research",
                        "content": f"Spawned {pioneer['name']} ({role})",
                    }
                    yield {
                        "type": "log",
                        "content": (
                            f"[Coordinator] Spawned worker {worker_id} ({role}) → {pioneer['name']}: "
                            f"{task_text[:80]}..."
                        ),
                    }

                yield {
                    "type": "swarm_task_list",
                    "workers": [
                        {
                            "worker_id": w.worker_id,
                            "pioneer_name": w.pioneer["name"],
                            "role": w.role,
                            "task": w.task,
                            "state": w.state.value,
                        }
                        for w in session.workers.values()
                        if w.phase == "research"
                    ],
                    "content": "Research workers queued",
                }

                _pending_r = set(futures.keys())
                while _pending_r:
                    _done_r, _pending_r = futures_wait(_pending_r, timeout=20)
                    if not _done_r:
                        yield {"type": "heartbeat", "content": ""}
                        continue
                    for future in _done_r:
                        worker_id, role, task_text = futures[future]
                        try:
                            result = future.result()
                            research_results[worker_id] = result
                            worker = session.workers[worker_id]
                            elapsed = (
                                (worker.completed_at or time.time())
                                - (worker.started_at or time.time())
                            )
                            yield {
                                "type": "log",
                                "content": (
                                    f"[Coordinator] Worker {worker_id} ({role}) "
                                    f"completed in {elapsed:.1f}s"
                                ),
                            }
                            pioneer = worker.pioneer
                            yield {
                                "type": "message",
                                "content": f"✅ **{pioneer['name']}** ({role}) completed\n\n",
                            }
                            yield {
                                "type": "swarm_task_list",
                                "workers": [
                                    {
                                        "worker_id": w.worker_id,
                                        "pioneer_name": w.pioneer["name"],
                                        "pioneer_full_name": w.pioneer["full_name"],
                                        "pioneer_motto": w.pioneer["motto"],
                                        "role": w.role,
                                        "task": w.task,
                                        "state": w.state.value,
                                        "output": (research_results.get(w.worker_id, "") or "")[:600],
                                    }
                                    for w in session.workers.values()
                                    if w.phase == "research"
                                ],
                                "content": f"{pioneer['name']} completed",
                            }
                            _team_store(
                                session.coordination_id,
                                f"research_{role}_{worker_id}",
                                result[:2000] if result else "",
                                author=role,
                            )
                        except Exception as e:
                            yield {
                                "type": "log",
                                "content": (
                                    f"[Coordinator] Worker {worker_id} ({role}) failed: {e}"
                                ),
                            }
                            yield {
                                "type": "message",
                                "content": f"⚠️ Research worker **{role}** failed: {e}\n\n",
                            }
                            yield {
                                "type": "swarm_task_list",
                                "workers": [
                                    {
                                        "worker_id": w.worker_id,
                                        "pioneer_name": w.pioneer["name"],
                                        "pioneer_full_name": w.pioneer["full_name"],
                                        "pioneer_motto": w.pioneer["motto"],
                                        "role": w.role,
                                        "task": w.task,
                                        "state": w.state.value,
                                        "output": (research_results.get(w.worker_id, "") or "")[:600],
                                    }
                                    for w in session.workers.values()
                                    if w.phase == "research"
                                ],
                                "content": f"{role} failed",
                            }

        # === PHASE 3: SYNTHESIZE (LLM) ===
        yield {"type": "swarm_phase", "phase_num": 3, "phase_name": "Synthesize", "total_phases": 5}
        yield {"type": "status", "content": "🧠 Coordinator: Synthesizing research findings..."}
        yield {"type": "thought", "content": "→ Phase 3/5: Synthesis (LLM — reading all findings)"}

        all_findings = session.get_all_scratchpad_content()
        max_synth_passes = 3
        synthesis = ""
        synth_confidence = 0.80
        synth_ambiguity = 0.20
        synth_ambiguous_points = []
        synth_clarification_question = ""
        synth_suggested_answers: list = []

        for synth_pass in range(1, max_synth_passes + 1):
            yield {
                "type": "status",
                "content": f"🧠 Synthesis pass {synth_pass}/{max_synth_passes}: reading all findings...",
            }
            with request_lock(context="text"):
                synth_result = _synthesize_findings(all_findings, user_input)
            synthesis = synth_result["plan"]
            synth_confidence = synth_result["confidence"]
            synth_ambiguity = synth_result["ambiguity"]
            synth_ambiguous_points = synth_result.get("ambiguous_points", [])
            synth_clarification_question = synth_result.get("clarification_question", "") or ""
            synth_suggested_answers = synth_result.get("suggested_answers", []) or []

            _MIN_SYNTHESIS_LEN = 300
            if len(synthesis) < _MIN_SYNTHESIS_LEN or synthesis.startswith("Synthesis failed"):
                yield {
                    "type": "log",
                    "content": (
                        f"[Coordinator] Synthesis pass {synth_pass} produced only "
                        f"{len(synthesis)} chars — treating as failure and retrying."
                    ),
                }
                synth_confidence = 0.0
                synth_ambiguity = 1.0

            required_confidence = 0.90 if synth_pass == 1 else 0.95
            yield {
                "type": "log",
                "content": (
                    f"[Coordinator] Synthesis pass {synth_pass}/{max_synth_passes}: "
                    f"confidence={synth_confidence:.0%}, ambiguity={synth_ambiguity:.0%} "
                    f"(need ≥{required_confidence:.0%} confidence, ≤5% ambiguity)"
                ),
            }

            if synth_confidence >= required_confidence and synth_ambiguity <= 0.25:
                break

            if synth_pass >= max_synth_passes:
                # Creative writing tasks never need visual style clarification — just produce the content.
                if _is_creative_task:
                    logger.info(
                        "[Coordinator] Synthesis thresholds not met on creative task — "
                        "skipping clarification, proceeding with available synthesis."
                    )
                    break

                logger.warning(
                    f"[Coordinator] Synthesis thresholds not met after {max_synth_passes} passes "
                    f"(confidence={synth_confidence:.0%}, ambiguity={synth_ambiguity:.0%}). "
                    "Requesting clarification."
                )
                try:
                    from brooks import save_pending_context as _save_ctx
                    _save_ctx(
                        {"type": "swarm_clarification", "prompt": user_input, "question":
                         f"I've analysed the task but my confidence is only {synth_confidence:.0%} "
                         f"with {synth_ambiguity:.0%} ambiguity remaining. What additional detail "
                         "or constraint would help me proceed with confidence?"},
                        session_id=session_id,
                        owner_id=owner_id,
                    )
                except Exception as _e:
                    logger.warning(f"[Coordinator] Could not save clarification context: {_e}")

                _GENERIC_SYNTH_PHRASES = (
                    "more detail", "more context", "more information", "provide more",
                    "can you clarify", "could you clarify", "what do you mean",
                    "please clarify", "please provide", "help me proceed",
                    "additional detail", "additional context",
                )
                _q_lower = (synth_clarification_question or "").lower()
                _question_is_valid = bool(synth_clarification_question) and not any(
                    p in _q_lower for p in _GENERIC_SYNTH_PHRASES
                )
                if not _question_is_valid and not synth_ambiguous_points:
                    logger.info(
                        "[Coordinator] Synthesis thresholds not met but no specific clarification "
                        "question available — proceeding without clarification card."
                    )
                    break

                if _question_is_valid:
                    _clarif_question = synth_clarification_question
                elif synth_ambiguous_points:
                    _clarif_question = "Which of the following would you like to clarify first?"
                else:
                    _clarif_question = "Could you provide more detail to help me proceed?"

                if synth_ambiguous_points:
                    _points_summary = "; ".join(synth_ambiguous_points[:3])
                    _clarif_context = f"Uncertain about: {_points_summary}"
                else:
                    _clarif_context = "Additional detail will help me build a better result."

                if synth_suggested_answers:
                    _clarif_options = [
                        {"label": str(s)[:80], "value": str(s)[:80]}
                        for s in synth_suggested_answers[:4]
                    ]
                elif synth_ambiguous_points:
                    _clarif_options = [
                        {"label": p[:60], "value": p[:60]}
                        for p in synth_ambiguous_points[:4]
                    ]
                else:
                    _clarif_options = []

                yield {
                    "type": "clarification_card",
                    "clarification": {
                        "question": _clarif_question,
                        "context": _clarif_context,
                        "options": _clarif_options,
                        "allow_freetext": True,
                        "card_type": "ambiguity",
                    },
                }
                return

        session.write_to_scratchpad("01_synthesis.md", f"# Synthesis\n\n{synthesis}")
        _team_store(session.coordination_id, "synthesis", synthesis)

        yield {"type": "message", "content": "**🧠 Synthesis Complete** ✓\n\n"}
        yield {"type": "log", "content": f"[Coordinator] Synthesis: {len(synthesis)} chars, confidence={synth_confidence:.0%}"}

        # === PHASE 4: IMPLEMENTATION (serial) ===
        yield {"type": "swarm_phase", "phase_num": 4, "phase_name": "Implement", "total_phases": 5}

        execute_code = (not plan_mode) and (not ultraplan_mode) and (scope == "codebase")

        _existing_project_context = ""
        if execute_code and owner_id:
            _palace_hits = _palace_project_lookup(owner_id, user_input, limit=3)
            if _palace_hits:
                _best = _palace_hits[0]
                _hit_content = _best.get("content", "") or _best.get("document", "")
                if _hit_content and "PROJECT:" in _hit_content:
                    _existing_project_context = (
                        f"\n\n[MEMORY PALACE — EXISTING PROJECT FOUND FOR THIS USER]:\n"
                        f"{_hit_content}\n"
                        f"CRITICAL: Read the existing file first using read_file(), then update "
                        f"it in place using write_file(). Do NOT call build_web_app() — that "
                        f"creates a new project at a new path and discards the user's work.\n"
                    )
                    yield {
                        "type": "log",
                        "content": (
                            f"[Coordinator] Palace: existing project found for '{owner_id}' — "
                            f"injecting context into coder prompt"
                        ),
                    }
                    yield {
                        "type": "thought",
                        "content": "→ Memory Palace: Existing project detected — coder will read-then-update",
                    }

        yield {
            "type": "status",
            "content": (
                f"{'⚡ Executing' if execute_code else '📝 Planning'}: "
                f"{len(impl_tasks)} implementation task(s)..."
            ),
        }
        yield {
            "type": "thought",
            "content": (
                f"→ Phase 4/5: Implementation ({len(impl_tasks)} tasks, serial) — "
                f"{'EXECUTION MODE' if execute_code else 'PLAN MODE'}"
            ),
        }
        if execute_code:
            yield {
                "type": "log",
                "content": "[Coordinator] Execution mode active — Leibniz will write files and run tools.",
            }

        impl_results = {}
        _preview_url = None
        for i, task_def in enumerate(impl_tasks):
            role = task_def.get("role", "architect")
            task_text = task_def.get("task", "")

            worker_id = session.register_worker(role, task_text, "implementation")
            try:
                if execute_code and role in ("architect", "coder", "devops"):
                    from leibniz_agent import get_architect_agent
                    agent = get_architect_agent(session_id=session_id)
                else:
                    agent = _get_agent_for_role(role, session_id=session_id, scope=scope)
            except Exception as _agent_err:
                logger.warning(
                    f"[Coordinator] Agent init failed for role '{role}' (falling back to simple agent): {_agent_err}"
                )
                _fb_host = get_swarm_worker_host(ARCHITECT_MODEL)
                from agno.agent import Agent as _Agent
                from agno.models.ollama import Ollama as _Ollama
                agent = _Agent(
                    name=f"{role.capitalize()} Worker",
                    model=_Ollama(id=ARCHITECT_MODEL, host=_fb_host, client_kwargs={"timeout": 300.0}),
                    instructions=[
                        f"You are a {role} worker producing a detailed plan.",
                        "Produce written plans, designs, and documentation only.",
                        "Do NOT execute commands, SSH to servers, or make live connections.",
                    ],
                    show_tool_calls=False,
                )
            _impl_pioneer = session.workers[worker_id].pioneer
            yield {
                "type": "swarm_worker_created",
                "worker_id": worker_id,
                "role": role,
                "pioneer_name": _impl_pioneer["name"],
                "pioneer_full_name": _impl_pioneer["full_name"],
                "pioneer_motto": _impl_pioneer["motto"],
                "task": task_text,
                "phase": "implementation",
                "content": f"Spawned {_impl_pioneer['name']} ({role})",
            }

            if execute_code and role in ("architect", "coder", "devops"):
                impl_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)}]\n"
                    f"{task_text}\n\n"
                    f"You have access to tools: build_web_app, get_project_template, write_file, "
                    f"read_file, list_dir, run_command.\n"
                    f"EXECUTE this task — write actual code and files. "
                    f"For web apps, use build_web_app(project_name, html_content) to create the "
                    f"project and get a live URL. Use get_project_template(type) to start from a "
                    f"scaffold (available types: game, dashboard, landing).\n\n"
                    f"CRITICAL — TEMPLATE CUSTOMIZATION: If you use get_project_template(), you MUST "
                    f"replace ALL placeholder content before calling build_web_app(). The template is "
                    f"a structural scaffold only. Replace every generic name, location, description, "
                    f"game objective, and placeholder comment with rich, specific content for THIS "
                    f"exact project. Never leave 'Starting Point', 'Central Hub', 'GAME TEMPLATE', "
                    f"'replace this section', or any other template placeholder in the final HTML.\n\n"
                    f"[Implementation Plan from Synthesis]:\n{synthesis}\n\n"
                    f"{_existing_project_context}"
                )
            else:
                impl_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)}]\n"
                    f"{task_text}\n\n"
                    f"IMPORTANT: Produce a detailed written plan, design, or documentation for this "
                    f"task. Do NOT execute commands, SSH to servers, or make live connections.\n\n"
                    f"[Synthesis / Implementation Plan]:\n{synthesis}\n\n"
                )
            if extracted_context:
                impl_prompt += f"[Original Context]:\n{extracted_context}"

            yield {
                "type": "log",
                "content": (
                    f"[Coordinator] Running implementation worker {worker_id} ({role}): "
                    f"{task_text[:80]}..."
                ),
            }

            result = _run_worker(
                session, worker_id, agent, impl_prompt,
                child_token=_derive_worker_token(ace_token, role, task_text),
            )
            impl_results[worker_id] = result

            worker = session.workers[worker_id]
            elapsed = (
                (worker.completed_at or time.time())
                - (worker.started_at or time.time())
            )

            _done_pioneer = worker.pioneer
            if worker.state == WorkerState.COMPLETED:
                yield {
                    "type": "message",
                    "content": f"✅ **{_done_pioneer['name']}** — step {i+1} completed ({elapsed:.1f}s)\n\n",
                }
            else:
                yield {
                    "type": "message",
                    "content": (
                        f"⚠️ **{_done_pioneer['name']}** — step {i+1} failed: {worker.error}\n\n"
                    ),
                }
            yield {
                "type": "swarm_task_list",
                "workers": [
                    {
                        "worker_id": w.worker_id,
                        "pioneer_name": w.pioneer["name"],
                        "role": w.role,
                        "task": w.task,
                        "state": w.state.value,
                    }
                    for w in session.workers.values()
                    if w.phase == "implementation"
                ],
                "content": f"Implementation step {i+1} done",
            }

        if execute_code:
            import re as _re
            _url_pattern = _re.compile(r"PROJECT_URL:\s*(https?://[^\s\n\"'<>]+)")
            for _worker_result in impl_results.values():
                _match = _url_pattern.search(_worker_result or "")
                if _match:
                    _preview_url = _match.group(1).rstrip("/") + "/"
                    break

            if not _preview_url:
                try:
                    import pathlib as _pl
                    _tmp = _pl.Path("/tmp/web_builder_last_url.txt")
                    if _tmp.exists():
                        _candidate = _tmp.read_text(encoding="utf-8").strip()
                        if _candidate.startswith("http"):
                            _preview_url = _candidate.rstrip("/") + "/"
                            _tmp.unlink(missing_ok=True)
                except Exception:
                    pass

            if _preview_url:
                yield {
                    "type": "set_preview_url",
                    "url": _preview_url,
                    "content": "",
                }
                yield {
                    "type": "message",
                    "content": (
                        f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"
                        f"The project is now running — check the Preview pane.\n\n"
                    ),
                }

                if owner_id:
                    import re as _re
                    _slug_match = _re.search(r"/projects/([^/?\s]+)", _preview_url)
                    if _slug_match:
                        _project_slug = _slug_match.group(1).rstrip("/")
                        _project_desc = user_input[:400]
                        _palace_project_save(
                            owner_id=owner_id,
                            slug=_project_slug,
                            url=_preview_url,
                            description=_project_desc,
                            path=f"user_projects/{_project_slug}/index.html",
                        )

        # === PHASE 5: VERIFICATION ===
        yield {"type": "swarm_phase", "phase_num": 5, "phase_name": "Verify", "total_phases": 5}
        yield {"type": "status", "content": "🔍 Coordinator: Verification in progress..."}
        yield {"type": "thought", "content": "→ Phase 5/5: Verification (fresh-eyes worker)"}

        all_work = session.get_all_scratchpad_content()
        # Cap work product fed to verifier — qwen3:14b has a 16K context window;
        # keeping input under ~24K chars (~6K tokens) leaves headroom for generation.
        _MAX_VERIFY_CHARS = 24_000
        if len(all_work) > _MAX_VERIFY_CHARS:
            all_work = all_work[:_MAX_VERIFY_CHARS] + "\n\n[...work product truncated for context window...]"
        criteria_text = "\n".join(f"- {c}" for c in verification_criteria)

        verify_prompt = (
            f"[Verification Task]\n"
            f"Review all work done for this task and verify against the criteria.\n\n"
            f"Original Task: {user_input}\n\n"
            f"Verification Criteria:\n{criteria_text}\n\n"
            f"Work Product:\n{all_work}"
        )

        verify_worker_id = session.register_worker("verifier", "Final verification", "verification")
        _verify_pioneer = session.workers[verify_worker_id].pioneer
        yield {
            "type": "swarm_worker_created",
            "worker_id": verify_worker_id,
            "role": "verifier",
            "pioneer_name": _verify_pioneer["name"],
            "pioneer_full_name": _verify_pioneer["full_name"],
            "pioneer_motto": _verify_pioneer["motto"],
            "task": "Final verification",
            "phase": "verification",
            "content": f"Spawned {_verify_pioneer['name']} (verifier)",
        }
        verifier = _get_agent_for_role("verifier")
        verify_result = _run_worker(
            session, verify_worker_id, verifier, verify_prompt,
            child_token=_derive_worker_token(ace_token, "verifier", "Final verification"),
        )

        session.write_to_scratchpad("99_verification.md", f"# Verification\n\n{verify_result}")

        verify_worker = session.workers[verify_worker_id]
        yield {
            "type": "swarm_task_list",
            "workers": [
                {
                    "worker_id": verify_worker.worker_id,
                    "pioneer_name": _verify_pioneer["name"],
                    "pioneer_full_name": _verify_pioneer["full_name"],
                    "pioneer_motto": _verify_pioneer["motto"],
                    "role": verify_worker.role,
                    "task": verify_worker.task,
                    "state": verify_worker.state.value,
                }
            ],
            "content": "Verification complete",
        }

        yield {"type": "message", "content": f"**🔍 Verification**\n\n{verify_result}\n\n"}

        # Auto-retry if verification failed on plan-only
        _verify_lower = verify_result.lower()
        _is_fail = any(kw in _verify_lower for kw in ("fail", "not complete", "no code", "no implementation", "planning document", "no actual"))
        if _is_fail and not execute_code and scope == "codebase":
            logger.warning("[Coordinator] Verification FAIL on plan-only run — auto-retrying in execution mode")
            yield {
                "type": "thought",
                "content": "→ Auto-retry: verification caught plan-only result, re-running with code execution enabled",
            }
            yield {"type": "status", "content": "⚡ Auto-correcting: running implementation in execution mode..."}
            execute_code = True
            for i, task_def in enumerate(impl_tasks):
                task_text = task_def.get("task", "")
                role = task_def.get("role", "architect")
                retry_prompt = (
                    f"[Implementation Task {i+1}/{len(impl_tasks)} — EXECUTION REQUIRED]\n"
                    f"{task_text}\n\n"
                    f"You MUST write actual code and create files. Use build_web_app(project_name, html_content) "
                    f"to create a live web project. Do NOT just plan or describe — WRITE THE CODE NOW.\n\n"
                    f"[Implementation Plan from Synthesis]:\n{synthesis}\n\n"
                    f"{_existing_project_context}"
                )
                retry_worker_id = session.register_worker(role, task_text, "implementation")
                retry_agent = _get_agent_for_role(role, session_id=session_id, scope="codebase")
                retry_result = _run_worker(
                    session, retry_worker_id, retry_agent, retry_prompt,
                    child_token=_derive_worker_token(ace_token, role, task_text),
                )
                yield {
                    "type": "message",
                    "content": f"✅ Retry: {role} completed — {retry_result[:200]}...\n\n" if len(retry_result) > 200 else f"✅ Retry: {role} completed\n\n",
                }
                impl_results[f"retry_w-{retry_worker_id}"] = retry_result

            _retry_url_pattern = re.compile(r"PROJECT_URL:\s*(https?://[^\s\n\"'<>]+)")
            for _res in impl_results.values():
                _m = _retry_url_pattern.search(_res or "")
                if _m:
                    _preview_url = _m.group(1).rstrip("/") + "/"
                    yield {"type": "set_preview_url", "url": _preview_url, "content": ""}
                    yield {"type": "message", "content": f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"}
                    if owner_id:
                        import re as _re2
                        _sm = _re2.search(r"/projects/([^/?\s]+)", _preview_url)
                        if _sm:
                            _palace_project_save(owner_id, _sm.group(1).rstrip("/"), _preview_url, user_input[:400])
                    break
            if not _preview_url:
                try:
                    import pathlib as _pl2
                    _tmp2 = _pl2.Path("/tmp/web_builder_last_url.txt")
                    if _tmp2.exists():
                        _c2 = _tmp2.read_text(encoding="utf-8").strip()
                        if _c2.startswith("http"):
                            _preview_url = _c2.rstrip("/") + "/"
                            _tmp2.unlink(missing_ok=True)
                            yield {"type": "set_preview_url", "url": _preview_url, "content": ""}
                            yield {"type": "message", "content": f"**🌐 Live Preview:** [{_preview_url}]({_preview_url})\n\n"}
                            if owner_id:
                                import re as _re3
                                _sm3 = _re3.search(r"/projects/([^/?\s]+)", _preview_url)
                                if _sm3:
                                    _palace_project_save(owner_id, _sm3.group(1).rstrip("/"), _preview_url, user_input[:400])
                except Exception:
                    pass

        _team_store(session.coordination_id, "verification", verify_result, author="verifier")

        # === FINAL SUMMARY ===
        total_workers = len(session.workers)
        completed = sum(1 for w in session.workers.values() if w.state == WorkerState.COMPLETED)
        failed = sum(1 for w in session.workers.values() if w.state == WorkerState.FAILED)
        total_time = time.time() - session.created_at

        yield {
            "type": "message",
            "content": (
                f"---\n"
                f"**📊 Coordination Summary**\n"
                f"- Workers spawned: {total_workers}\n"
                f"- Completed: {completed} | Failed: {failed}\n"
                f"- Total time: {total_time:.1f}s\n"
                f"- Scratchpad: {len(session.list_scratchpad())} files\n"
            ),
        }

        followup_section = _generate_followups(synthesis, impl_tasks)
        yield {"type": "response", "content": f"{synthesis}{followup_section}"}

        logger.info(
            f"[Coordinator] Coordination {session.coordination_id} complete: "
            f"{completed}/{total_workers} workers, {total_time:.1f}s"
        )

    except Exception as e:
        logger.error(f"[Coordinator] Coordination failed: {e}", exc_info=True)
        yield {"type": "error", "content": f"Coordination failed: {e}"}
