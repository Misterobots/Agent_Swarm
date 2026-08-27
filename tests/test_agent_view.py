"""Focused tests for the live Agent View session registry."""

import gc
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

import coordination.session as session_module


def test_snapshot_serializes_active_session_and_workers(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)
    session_module._ACTIVE_SESSIONS.clear()

    session = session_module.CoordinatorSession(
        "session-1", owner_id="alice", coordination_id="coord-1"
    )
    worker_id = session.register_worker("researcher", "Find relevant evidence", "research")
    worker = session.workers[worker_id]
    worker.state = session_module.WorkerState.RUNNING
    worker.started_at = time.time() - 2

    snapshot = session_module.snapshot_active_sessions()

    assert len(snapshot) == 1
    assert snapshot[0]["coordination_id"] == "coord-1"
    assert snapshot[0]["owner_id"] == "alice"
    assert snapshot[0]["worker_count"] == 1
    assert snapshot[0]["running_count"] == 1
    assert snapshot[0]["workers"][0]["worker_id"] == worker_id
    assert snapshot[0]["workers"][0]["state"] == "running"
    assert snapshot[0]["workers"][0]["task"] == "Find relevant evidence"


def test_registry_drops_collected_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "SCRATCHPAD_ROOT", tmp_path)
    session_module._ACTIVE_SESSIONS.clear()

    session = session_module.CoordinatorSession(
        "session-2", owner_id="alice", coordination_id="coord-2"
    )
    assert session_module.get_active_session("coord-2") is session

    del session
    gc.collect()

    assert session_module.get_active_session("coord-2") is None
    assert session_module.snapshot_active_sessions() == []
