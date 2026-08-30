"""Coverage for the live Agent View coordination-session registry."""

import gc
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

import coordination.session as session_module


def test_snapshot_serializes_owner_workers_and_newest_first(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)

    older = session_module.CoordinatorSession("session-old", owner_id="owner-a", coordination_id="coord-old")
    time.sleep(0.01)
    newer = session_module.CoordinatorSession("session-new", owner_id="owner-b", coordination_id="coord-new")
    worker_id = newer.register_worker("coder", "Implement the fixture", "implementation")
    newer.workers[worker_id].started_at = newer.created_at

    snapshots = session_module.snapshot_active_sessions()

    assert [item["coordination_id"] for item in snapshots[:2]] == ["coord-new", "coord-old"]
    assert snapshots[0]["owner_id"] == "owner-b"
    assert snapshots[0]["worker_count"] == 1
    assert snapshots[0]["running_count"] == 0
    assert snapshots[0]["workers"][0]["worker_id"] == worker_id
    assert snapshots[0]["workers"][0]["role"] == "coder"
    assert snapshots[0]["workers"][0]["state"] == "pending"


def test_registry_drops_sessions_after_the_last_strong_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)

    session = session_module.CoordinatorSession("session-gc", coordination_id="coord-gc")
    assert any(item["coordination_id"] == "coord-gc" for item in session_module.snapshot_active_sessions())

    del session
    gc.collect()

    assert all(item["coordination_id"] != "coord-gc" for item in session_module.snapshot_active_sessions())


def test_cancel_active_session_sets_cooperative_stop(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)

    session = session_module.CoordinatorSession("session-stop", coordination_id="coord-stop")
    worker_id = session.register_worker("coder", "cancel me", "implementation")

    assert session_module.cancel_active_session("coord-stop") is True
    assert session.cancel_requested is True
    assert session.workers[worker_id].cancel_flag.is_set()
    assert session_module.cancel_active_session("missing") is False
