"""Routing contract for Code / Collective / Gauntlet turns.

These pin the decisions the desktop's flattened MODE_FLAGS contract depends on,
because a mis-route here is invisible in the transcript: the request never reaches
church.py's router, so no log or event reveals that a Collective was served by the
single-agent DevHarness loop instead.

  * dev_mode + swarm_mode + research_mode  -> coordinator, with perspective research engaged
  * dev_mode + research_mode alone         -> not DevHarness, and still not swarm_mode,
                                              so church.py resolves it to RESEARCH
  * gauntlet_mode                          -> needs a bar (422 without one) and outranks DevHarness
  * dev_mode alone with a real model       -> unchanged DevHarness loop
  * legacy wire values (the ``swarm`` model sentinel and the /swarm /build /plan
    /collective prefixes)                  -> still mean coordinator
"""
import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# main.py's import chain reaches native and pre-rename-legacy modules that only exist
# inside the runtime container. conftest.py already stubs langfuse the same way. Any
# module *not* on this list is a real failure and is re-raised, so the predicates below
# can never be tested against a silently hollow import.
_ALLOWED_ABSENT = frozenset({
    "pynvml",
    "phi", "phi.agent", "phi.model", "phi.model.ollama", "phi.knowledge",
    "phi.knowledge.combined", "phi.vectordb", "phi.vectordb.pgvector",
    "phi.storage", "phi.storage.agent", "phi.storage.agent.postgres",
})


def _import_main():
    # conftest.py puts control_plane/ ahead of agents/ on sys.path, and control_plane
    # ships its own `security` package — so main.py's `from security.audit_logger ...`
    # resolves against the wrong tree under pytest. Other tests sidestep this by
    # importing `agents.security` explicitly; agents/ has to come first to import main
    # itself. The order is restored immediately so no other module sees the swap.
    agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
    original = list(sys.path)
    if agents_dir in sys.path:
        sys.path.remove(agents_dir)
    sys.path.insert(0, agents_dir)
    try:
        for _ in range(40):
            try:
                return __import__("main")
            except ModuleNotFoundError as exc:
                if exc.name not in _ALLOWED_ABSENT:
                    raise
                sys.modules[exc.name] = MagicMock()
        raise RuntimeError("main did not finish importing within the stub budget")
    finally:
        sys.path[:] = original


main = _import_main()


def req(**flags):
    """A ChatRequest shaped like the desktop's stream: one user turn, streaming."""
    body = {"messages": [{"role": "user", "content": "do the thing"}], "stream": True}
    body.update(flags)
    return main.ChatRequest.model_validate(body)


def slash(text, **flags):
    body = {"messages": [{"role": "user", "content": text}], "stream": True}
    body.update(flags)
    return main.ChatRequest.model_validate(body)


# --- item 1: research_mode must escape the DevHarness guard -----------------

def test_collective_with_a_project_reaches_the_coordinator():
    """dev+swarm+research is the desktop's Collective-on-a-project shape."""
    request = req(dev_mode=True, swarm_mode=True, research_mode=True)
    assert main._swarm_turn(request) is True
    assert main._routes_to_dev_harness(request) is False


def test_research_only_turn_escapes_dev_harness():
    request = req(dev_mode=True, research_mode=True)
    assert main._routes_to_dev_harness(request) is False


def test_research_only_turn_is_not_forced_into_swarm_mode():
    """The exemption must not widen _swarm_turn.

    _swarm_turn's value is passed to chat_swarm as swarm_mode, and church.py applies
    its research branch *before* its swarm branch — so a research-only turn that also
    read as a swarm turn would land on COORDINATE instead of RESEARCH.
    """
    request = req(dev_mode=True, research_mode=True)
    assert main._swarm_turn(request) is False


# A slash command is the user naming a mode explicitly. dev_mode riding along only
# means a workspace is attached, so it must not downgrade the request into the code
# loop — church.py's table runs after this decision and would never see the command.
@pytest.mark.parametrize("cmd", [
    "/research", "/think", "/cad", "/workshop", "/grill", "/design",
    "/flow-batch-edit", "/flow-variants", "/agent-flows",
])
def test_non_swarm_slash_commands_escape_the_dev_harness(cmd):
    request = slash(f"{cmd} a topic", dev_mode=True)
    assert main._routes_to_dev_harness(request) is False
    # Escaping DevHarness must not silently promote them to a coordinator turn:
    # _swarm_turn feeds swarm_mode downstream, which would force COORDINATE.
    assert main._swarm_turn(request) is False


def test_bare_slash_command_with_no_payload_still_escapes():
    assert main._routes_to_dev_harness(slash("/cad", dev_mode=True)) is False


def test_unrecognized_slash_text_still_uses_the_code_loop():
    assert main._routes_to_dev_harness(slash("/notes list my tasks", dev_mode=True)) is True


def test_legacy_collective_prefix_still_means_coordinator():
    request = slash("/collective build x", dev_mode=True)
    assert main._swarm_turn(request) is True
    assert main._routes_to_dev_harness(request) is False


# --- legacy wire values must keep working ----------------------------------

@pytest.mark.parametrize("text", ["/swarm x", "/build x", "/plan x", "/collective x"])
def test_swarm_slash_prefixes_still_mean_coordinator(text):
    request = slash(text, dev_mode=True)
    assert main._swarm_turn(request) is True
    assert main._routes_to_dev_harness(request) is False


def test_swarm_model_sentinel_still_means_coordinator():
    request = req(dev_mode=True, model="swarm")
    assert main._swarm_turn(request) is True
    assert main._routes_to_dev_harness(request) is False


# --- acceptance 5: ordinary Code is unchanged ------------------------------

def test_plain_code_turn_still_uses_the_dev_harness():
    request = req(dev_mode=True, model="qwen3.8:27b")
    assert main._routes_to_dev_harness(request) is True


def test_non_streaming_code_turn_is_untouched_by_the_guard():
    """The guard always required stream=True; research alone must not change that."""
    assert main._routes_to_dev_harness(req(dev_mode=True, stream=False)) is False


# --- item 2 / acceptance 3+4: Gauntlet ------------------------------------

def test_gauntlet_without_a_bar_is_rejected():
    request = req(gauntlet_mode=True)
    with pytest.raises(HTTPException) as exc:
        main._validate_gauntlet_request(request)
    assert exc.value.status_code == 422


def test_gauntlet_with_a_bar_is_accepted_and_forces_the_coordinator():
    request = req(gauntlet_mode=True, gauntlet_bar="  https://example.test/bar  ")
    main._validate_gauntlet_request(request)
    assert request.gauntlet_bar == "https://example.test/bar"
    assert request.swarm_mode is True
    assert main._swarm_turn(request) is True


def test_gauntlet_beats_dev_harness():
    """The desktop's steering re-run sends dev_mode with Gauntlet; Gauntlet wins."""
    request = req(dev_mode=True, swarm_mode=True, gauntlet_mode=True,
                  gauntlet_bar="https://example.test/bar")
    main._validate_gauntlet_request(request)
    assert main._routes_to_dev_harness(request) is False


def test_gauntlet_mode_alone_escapes_dev_harness_even_without_validation():
    assert main._routes_to_dev_harness(req(dev_mode=True, gauntlet_mode=True)) is False


def test_malformed_handoff_id_is_rejected():
    request = req(gauntlet_mode=True, gauntlet_bar="https://example.test/bar",
                  gauntlet_handoff={"id": "short"})
    with pytest.raises(HTTPException) as exc:
        main._validate_gauntlet_request(request)
    assert exc.value.status_code == 422


def test_chat_request_keeps_the_desktop_handoff_as_typed_fields():
    """extra=\"allow\" used to swallow these; they are declared now."""
    request = main.ChatRequest.model_validate({
        "messages": [{"role": "user", "content": "please resume"}],
        "gauntlet_mode": True,
        "gauntlet_bar": "https://example.test/bar",
        "gauntlet_handoff": {
            "id": "checkpoint_12345678",
            "goal": "Preserved original objective",
            "qualityBar": "https://example.test/bar",
            "effort": {"model": "qwen3:14b", "reasoningEffort": "high"},
            "clarifications": ["keep the sqlite backend"],
        },
    })
    assert request.gauntlet_handoff["id"] == "checkpoint_12345678"
    assert request.gauntlet_bar == "https://example.test/bar"


def test_gauntlet_prompt_keeps_the_named_bar_visible_to_workers():
    prompt = main._gauntlet_prompt("Build the vertical slice", "https://example.test/bar")
    assert "Build the vertical slice" in prompt
    assert "https://example.test/bar" in prompt
    assert "separate Pioneer-backed builder and critic" in prompt


def test_critic_verdict_event_is_not_dropped_at_the_sse_allowlist():
    """A new rich event that is not in the allowlist reaches no client at all."""
    assert "gauntlet_critic_verdict" in main._RICH_EVENT_TYPES


def test_checkpoint_id_is_forwarded_as_the_coordination_id():
    """The desktop's checkpoint must become the coordinator's durable id, or the critic
    verdict is persisted under a key nothing the client can poll.

    Asserted against the call site because reaching it for real would mean running the
    whole endpoint: chat_swarm() builds agents and touches the DB.
    """
    from pathlib import Path

    source = Path(main.__file__).read_text(encoding="utf-8")
    assert 'coordination_id=(str((request.gauntlet_handoff or {}).get("id") or "").strip() or None)' in source


def test_scheduled_triggers_can_carry_research_mode():
    cfg = main.TriggerTaskConfig(prompt="survey X", swarm_mode=True, research_mode=True)
    assert cfg.research_mode is True
    assert main.TriggerTaskConfig(prompt="x").research_mode is False
