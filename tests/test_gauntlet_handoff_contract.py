"""Regression contract for desktop-owned Gauntlet continuation IDs."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

import main


def test_chat_request_accepts_a_structured_gauntlet_handoff():
    request = main.ChatRequest.model_validate({
        "messages": [{"role": "user", "content": "please resume"}],
        "gauntlet_mode": True,
        "gauntlet_bar": "https://example.test/bar",
        "gauntlet_handoff": {
            "id": "checkpoint_12345678",
            "goal": "Preserved original objective",
            "qualityBar": "https://example.test/bar",
            "effort": {"model": "qwen3:14b", "reasoningEffort": "high"},
        },
    })
    assert request.gauntlet_handoff["id"] == "checkpoint_12345678"
    assert request.gauntlet_handoff["goal"] == "Preserved original objective"


def test_gauntlet_prompt_keeps_the_named_bar_visible_to_workers():
    prompt = main._gauntlet_prompt("Build the vertical slice", "https://example.test/bar")
    assert "Build the vertical slice" in prompt
    assert "https://example.test/bar" in prompt
    assert "separate Pioneer-backed builder and critic" in prompt


def test_project_routing_keeps_the_desktop_checkpoint_id():
    """A project picker must resume the original Gauntlet task, not fork it."""
    root = Path(__file__).resolve().parents[1]
    orchestrator = (root / "agents" / "coordination" / "orchestrator.py").read_text(encoding="utf-8")
    gates = (root / "agents" / "routing" / "gates.py").read_text(encoding="utf-8")

    assert '"coordination_id": session.coordination_id' in orchestrator
    assert 'preserved_coordination_id = str(pending_ctx.get("coordination_id") or "").strip()' in gates
    assert 'coordination_id = preserved_coordination_id or f"coord-{_uuid.uuid4().hex[:8]}"' in gates


def test_resuming_a_gauntlet_run_clears_pause_end_time_without_reviving_terminal_runs():
    root = Path(__file__).resolve().parents[1]
    store = (root / "agents" / "swarm_run_store.py").read_text(encoding="utf-8")

    assert "ended_at=CASE WHEN %s IN ('queued', 'running') THEN NULL ELSE ended_at END" in store
    assert "status NOT IN ('completed', 'failed', 'cancelled', 'denied')" in store


def test_desktop_code_workspace_uses_a_scoped_session_container():
    root = Path(__file__).resolve().parents[1]
    sandbox = (root / "agents" / "coordination" / "session_sandbox.py").read_text(encoding="utf-8")
    handler = (root / "agents" / "handlers" / "coordinate.py").read_text(encoding="utf-8")

    assert '"desktop_local"' in sandbox
    assert "MEMEX_DESKTOP_WORKSPACE_ROOT" in sandbox
    assert 'session_mode="desktop_local" if workspace_key else None' in handler


def test_gauntlet_completion_requires_a_persisted_independent_critic_verdict():
    root = Path(__file__).resolve().parents[1]
    store = (root / "agents" / "swarm_run_store.py").read_text(encoding="utf-8")
    orchestrator = (root / "agents" / "coordination" / "orchestrator.py").read_text(encoding="utf-8")

    assert "swarm_gauntlet_reviews" in store
    assert "record_gauntlet_review" in orchestrator
    assert "VERDICT: PASS" in orchestrator
    assert 'status="needs_input"' in orchestrator
