"""
routing/gates.py — Pending context dispatch for chat_swarm().

handle_pending_context() processes the 8 pending_ctx types that may be saved
from a previous turn (clarifications, onboarding steps, intent gates).

Usage in chat_swarm():

    if pending_ctx:
        _result = {"handled": False, "user_input": user_input}
        yield from handle_pending_context(pending_ctx, user_input, ..., _result)
        if _result["handled"]:
            return
        user_input = _result["user_input"]
"""

import logging
from pathlib import Path

logger = logging.getLogger("Router")


def handle_pending_context(
    pending_ctx: dict,
    user_input: str,
    session_id: str,
    owner_id,
    history: list | None,
    extracted_context: str,
    ace_token,
    ultraplan_mode: bool,
    dev_mode: bool,
    result: dict,
):
    """
    Generator — process a saved pending context entry and yield events.

    Updates ``result`` in-place:
      result["handled"]    = True  → caller should return immediately
      result["user_input"] = str   → modified user_input for fall-through paths
    """
    result["user_input"] = user_input  # default: pass through unchanged

    ctx_type = pending_ctx.get("type", "")

    # -----------------------------------------------------------------------
    # 1. image_clarification
    # -----------------------------------------------------------------------
    if ctx_type == "image_clarification":
        original_prompt = pending_ctx.get("prompt", "")
        user_lower = user_input.lower().strip()
        new_image_kws = ["generate", "create", "make", "draw", "paint", "design", "produce"]
        is_new_request = any(user_lower.startswith(kw) for kw in new_image_kws)
        comma_count = original_prompt.count(",")
        is_snowballed = comma_count >= 2 or len(original_prompt) > 150

        from brooks import clear_context
        if is_new_request or is_snowballed:
            logger.warning("[Router] Discarding stale image context (new=%s, snowball=%s)", is_new_request, is_snowballed)
            yield {"type": "log", "content": "[Context Manager] Stale clarification cleared."}
            clear_context(session_id=session_id, owner_id=owner_id)
        else:
            logger.info("[Router] Answering image clarification. Original: '%s' + Answer: '%s'", original_prompt, user_input)
            result["user_input"] = f"{original_prompt}, {user_input}"
            yield {"type": "log", "content": "[Context Manager] Clarification answered."}
            clear_context(session_id=session_id, owner_id=owner_id)
        return  # fall through (handled=False), caller uses result["user_input"]

    # -----------------------------------------------------------------------
    # 2. art_studio_redirect
    # -----------------------------------------------------------------------
    if ctx_type == "art_studio_redirect":
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)
        return  # fall through

    # -----------------------------------------------------------------------
    # 3. swarm_clarification
    # -----------------------------------------------------------------------
    if ctx_type == "swarm_clarification":
        original = pending_ctx.get("prompt", "")
        logger.info("[Router] Resolving Swarm Clarification. Original: '%s' + Answer: '%s'", original[:80], user_input[:80])
        result["user_input"] = f"{original}\n\nAdditional context: {user_input}"
        yield {"type": "log", "content": "[Context Manager] Swarm clarification resolved. Launching coordinator..."}
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)
        return  # fall through

    # -----------------------------------------------------------------------
    # 3b. swarm_steering (nuance direction selection)
    # -----------------------------------------------------------------------
    # The orchestrator saves type="swarm_steering" when nuance_detected=True and
    # the user is asked to pick a direction.  Reconstruct the full scoped prompt
    # so the coordinator gets ONE combined context, then pass already_steered=True
    # so the decomposer skips the nuance gate and goes straight to worker spawning.
    if ctx_type == "swarm_steering":
        original = pending_ctx.get("prompt", "")
        question = pending_ctx.get("question", "")
        logger.info(
            "[Router] Resolving Swarm Steering. Original: '%s' | Q: '%s' | Answer: '%s'",
            original[:80], question[:60], user_input[:60],
        )
        # Reconstruct a fully-scoped prompt for the next coordinate_task call.
        scoped_prompt = (
            f"{original}\n\n"
            f"[Steering context — already answered, do NOT ask again]\n"
            f"Question was: {question}\n"
            f"Chosen direction: {user_input}"
        )
        result["user_input"] = scoped_prompt
        result["already_steered"] = True
        yield {"type": "log", "content": f"[Context Manager] Swarm steering resolved → '{user_input}'. Launching coordinator..."}
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)
        return  # fall through to coordinate handler

    # -----------------------------------------------------------------------
    # 4. ambiguity_resolution
    # -----------------------------------------------------------------------
    if ctx_type == "ambiguity_resolution":
        original = pending_ctx.get("prompt")
        question = pending_ctx.get("question")
        logger.info("[Router] Resolving Ambiguity. Original: '%s' + Answer: '%s'", original, user_input)
        result["user_input"] = f"Original Request: '{original}'\nSystem Question: '{question}'\nUser Answer: '{user_input}'"
        yield {"type": "log", "content": "[Context Manager] Ambiguity Resolved. Analysing composite input..."}
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)
        return  # fall through

    # -----------------------------------------------------------------------
    # 5. project_onboarding_step_1
    # -----------------------------------------------------------------------
    if ctx_type == "project_onboarding_step_1":
        original_prompt = pending_ctx.get("original_prompt", "")
        project_type_answer = user_input
        from brooks import clear_context, save_pending_context as _save_ctx
        clear_context(session_id=session_id, owner_id=owner_id)
        try:
            _save_ctx(
                {
                    "type": "project_onboarding_step_2",
                    "original_prompt": original_prompt,
                    "project_type": project_type_answer,
                },
                session_id=session_id,
                owner_id=owner_id,
            )
        except Exception as _e:
            logger.warning("[Onboarding] Could not save step 2 context: %s", _e)
        yield {
            "type": "clarification_card",
            "clarification": {
                "question": "What's the project name?",
                "context": f"Project type: *{project_type_answer}*",
                "options": [],
                "allow_freetext": True,
                "card_type": "onboarding",
            },
        }
        result["handled"] = True
        return

    # -----------------------------------------------------------------------
    # 6. project_onboarding_step_2
    # -----------------------------------------------------------------------
    if ctx_type == "project_onboarding_step_2":
        original_prompt = pending_ctx.get("original_prompt", "")
        project_type_answer = pending_ctx.get("project_type", "")
        project_name = user_input.strip().replace(" ", "-").lower()
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)

        workspace_path = Path(__file__).parent.parent.parent / "workspace" / project_name
        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
            (workspace_path / "README.md").write_text(
                f"# {project_name}\n\n{original_prompt}\n",
                encoding="utf-8",
            )
            logger.info("[Onboarding] Created workspace at %s", workspace_path)
        except Exception as _e:
            logger.warning("[Onboarding] Could not create workspace: %s", _e)

        yield {
            "type": "clarification_card",
            "clarification": {
                "question": f"Project **{project_name}** is ready. Open the developer workspace to start building?",
                "context": f"Workspace created at `workspace/{project_name}/`",
                "options": [
                    {
                        "label": "Open Dev Workspace",
                        "value": f"open_dev:{project_name}",
                        "description": "Switch to editor + terminal",
                        "redirect": "/dev",
                    },
                    {
                        "label": "Generate starter code",
                        "value": f"generate_starter:{project_name}",
                        "description": "Let me scaffold the project first",
                    },
                ],
                "allow_freetext": False,
                "card_type": "onboarding",
            },
        }
        result["handled"] = True
        return

    # -----------------------------------------------------------------------
    # 7. dev_project_clarification
    # -----------------------------------------------------------------------
    if ctx_type == "dev_project_clarification":
        original_prompt = pending_ctx.get("prompt", "")
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)

        if user_input.startswith("existing_project"):
            logger.info("[Router] Dev project: routing as existing codebase task.")
            yield {"type": "log", "content": "[Context Manager] Routing to existing project coordinator..."}
            from lamport import coordinate_task as _coord
            yield {"type": "status", "content": "🛠️ Launching codebase coordinator..."}
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                ultraplan_mode=ultraplan_mode,
                dev_mode=dev_mode,
                skip_project_gate=True,
            ):
                yield chunk
            result["handled"] = True
            return

        elif user_input.startswith("new_project"):
            logger.info("[Router] Dev project (new): routing directly to coordinator.")
            yield {"type": "log", "content": "[Context Manager] New project: launching coordinator..."}
            from lamport import coordinate_task as _coord
            yield {"type": "status", "content": "🛠️ Launching coordinator..."}
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                ultraplan_mode=ultraplan_mode,
                dev_mode=True,
                skip_project_gate=True,
            ):
                yield chunk
            result["handled"] = True
            return

        else:
            # plan_only — fall through with original prompt
            logger.info("[Router] Dev project: plan-only mode, routing as external.")
            yield {"type": "log", "content": "[Context Manager] Plan-only mode — research and plan without code changes."}
            result["user_input"] = original_prompt
            return  # fall through

    # -----------------------------------------------------------------------
    # 8. task_intent_clarification
    # -----------------------------------------------------------------------
    if ctx_type == "task_intent_clarification":
        original_prompt = pending_ctx.get("prompt", "")
        saved_summary = pending_ctx.get("summary", "")
        intent_choice = user_input
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)

        if intent_choice.startswith("research_it"):
            logger.info("[Router] Task intent: user chose research.")
            yield {"type": "log", "content": "[Context Manager] Routing as deep research task..."}
            from lamport import coordinate_task as _coord
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                research_mode=True,
            ):
                yield chunk
            result["handled"] = True
            return

        elif intent_choice.startswith("plan_it"):
            logger.info("[Router] Task intent: user chose planning.")
            yield {"type": "log", "content": "[Context Manager] Routing as planning/architecture task..."}
            from lamport import coordinate_task as _coord
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                plan_mode=True,
                research_mode=True,
            ):
                yield chunk
            result["handled"] = True
            return

        elif intent_choice.startswith("build_it"):
            logger.info("[Router] Task intent: user chose build — asking project type.")
            try:
                from brooks import save_pending_context as _save_ctx
                _save_ctx(
                    {"type": "dev_project_clarification", "prompt": original_prompt, "summary": saved_summary},
                    session_id=session_id,
                    owner_id=owner_id,
                )
            except Exception as _e:
                logger.warning("[Router] Could not save dev_project context: %s", _e)
            yield {
                "type": "clarification_card",
                "clarification": {
                    "question": "Is this for an existing project or a new one?",
                    "context": f"Building: *{saved_summary}*",
                    "options": [
                        {"label": "Existing project", "value": "existing_project", "description": "I'll work within your current codebase"},
                        {"label": "New project", "value": "new_project", "description": "Walk me through setup"},
                        {"label": "Just plan it", "value": "plan_only", "description": "Research and plan, no files changed"},
                    ],
                    "allow_freetext": False,
                    "card_type": "dev_project",
                },
            }
            result["handled"] = True
            return

        else:
            # Freetext — route as research
            logger.info("[Router] Task intent: freetext — routing as research.")
            yield {"type": "log", "content": "[Context Manager] Routing as research task..."}
            result["user_input"] = original_prompt
            return  # fall through

    # -----------------------------------------------------------------------
    # 9. dev_mode_gate
    # -----------------------------------------------------------------------
    if ctx_type == "dev_mode_gate":
        original_prompt = pending_ctx.get("prompt", "")
        from brooks import clear_context
        clear_context(session_id=session_id, owner_id=owner_id)

        if user_input.startswith("switch_to_dev_mode"):
            logger.info("[Router] Dev mode gate: user chose to switch to Dev Mode.")
            yield {
                "type": "delta",
                "content": (
                    "Opening the **Developer** workspace...\n\n"
                    "Your request has been saved. In the **Developer** tab:\n"
                    "1. Enable the **🤖 Agent** toggle\n"
                    "2. Re-send your request for full implementation (file creation, code execution, live preview)\n\n"
                    f"Your original request was:\n> *{original_prompt[:200]}{'...' if len(original_prompt) > 200 else ''}*"
                ),
            }
            result["handled"] = True
            return

        elif user_input.startswith("request_dev_access"):
            logger.info("[Router] Dev mode gate: user requested dev access via governance.")
            try:
                from liskov import governance_manager, RequestType
                item = governance_manager.submit_request(
                    type=RequestType.DEV_MODE,
                    description=f"User {owner_id!r} requests Dev Mode access. Task: {original_prompt[:300]}",
                    user=owner_id or "anonymous",
                )
                yield {
                    "type": "delta",
                    "content": (
                        f"✅ Dev Mode access request submitted (ID: `{item.id}`). "
                        f"An admin will review your request.\n\n"
                        "In the meantime, running a **research & planning pass**:\n"
                    ),
                }
            except Exception as _gov_e:
                logger.warning("[DevModeGate] Governance request failed: %s", _gov_e)
                yield {"type": "delta", "content": "⚠️ Could not submit governance request. Running research & planning pass:\n"}

            from lamport import coordinate_task as _coord
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                ultraplan_mode=ultraplan_mode,
                dev_mode=True,
                plan_mode=True,
            ):
                yield chunk
            result["handled"] = True
            return

        else:
            # plan_only / freetext — research & plan, no file writes
            logger.info("[Router] Dev mode gate: user chose research & plan-only.")
            from lamport import coordinate_task as _coord
            for chunk in _coord(
                original_prompt,
                session_id=session_id,
                owner_id=owner_id,
                history_context="\n".join(m.get("content", "") for m in (history or [])[-4:]),
                extracted_context=extracted_context,
                ace_token=ace_token,
                ultraplan_mode=ultraplan_mode,
                dev_mode=True,
                plan_mode=True,
                research_mode=True,
            ):
                yield chunk
            result["handled"] = True
            return
