import os
import sys

import pytest


WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

AGENTS_DIR = os.path.join(WORKSPACE_ROOT, "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)


def test_context_isolated_by_distinct_session_ids(monkeypatch, tmp_path):
    from agents import brooks as context_manager

    monkeypatch.setattr(context_manager, "CONTEXT_DIR", str(tmp_path))

    context_manager.save_pending_context({"marker": "A_ONLY"}, session_id="sess_a", owner_id="user_a")

    assert context_manager.get_pending_context(session_id="sess_b", owner_id="user_a") is None
    assert context_manager.get_pending_context(session_id="sess_a", owner_id="user_a") == {"marker": "A_ONLY"}


def test_context_collision_should_not_leak_across_principals(monkeypatch, tmp_path):
    from agents import brooks as context_manager

    monkeypatch.setattr(context_manager, "CONTEXT_DIR", str(tmp_path))

    shared_session_id = "shared_session"
    context_manager.save_pending_context({"marker": "A_ONLY"}, session_id=shared_session_id, owner_id="user_a")

    principal_b_view = context_manager.get_pending_context(session_id=shared_session_id, owner_id="user_b")

    assert principal_b_view is None


def test_user_preferences_do_not_share_values_between_instances():
    from agents.preferences import UserPreferences

    user_a = UserPreferences("user_a")
    user_b = UserPreferences("user_b")

    user_a.set("theme", "cyberpunk", task_type="image_generation")

    assert user_a.get("theme") == "cyberpunk"
    assert user_b.get("theme") is None
    assert user_b.get_for_task("image_generation") == {}


def test_user_preferences_roundtrip_preserves_owner_and_values():
    from agents.preferences import UserPreferences

    prefs = UserPreferences("user_a")
    prefs.set("style", "art_deco", task_type="image_generation", confidence=0.9)

    restored = UserPreferences.from_dict(prefs.to_dict())

    assert restored.user_id == "user_a"
    assert restored.get("style") == "art_deco"
    assert restored.get_for_task("image_generation") == {"style": "art_deco"}


def test_memory_recent_summaries_are_global_shared_state(monkeypatch, tmp_path):
    from agents import memory_system

    temp_memory_file = tmp_path / "skills_memory.json"
    monkeypatch.setattr(memory_system, "MEMORY_FILE", str(temp_memory_file))

    memory = memory_system.MemorySystem()
    memory.add_session_summary("2026-03-31", "user_a", "A_ONLY")
    memory.add_session_summary("2026-04-01", "user_b", "B_ONLY")

    summaries = memory.get_recent_summaries(n=5)

    assert len(summaries) == 2
    assert [summary["summary"] for summary in summaries] == ["B_ONLY", "A_ONLY"]


def test_memory_recall_should_filter_to_caller_owned_records(monkeypatch, tmp_path):
    from agents import memory_system

    temp_memory_file = tmp_path / "skills_memory.json"
    monkeypatch.setattr(memory_system, "MEMORY_FILE", str(temp_memory_file))

    memory = memory_system.MemorySystem()
    memory.add_session_summary("2026-03-31", "user_a", "A_ONLY", owner_id="user_a")
    memory.add_session_summary("2026-04-01", "user_b", "B_ONLY", owner_id="user_b")

    caller_visible = memory.get_recent_summaries(n=5, owner_id="user_a")

    assert [summary["summary"] for summary in caller_visible] == ["A_ONLY"]