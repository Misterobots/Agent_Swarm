from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import swarm_run_event_store


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args):
        return None

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, **_kwargs):
        return FakeCursor(self.rows)


def test_list_events_preserves_original_timestamp_and_hides_storage_marker(monkeypatch):
    connection = FakeConnection([
        {
            "type": "status",
            "seq": 4,
            "payload": {
                "content": "ready",
                "_event_ts": "2026-08-25T12:00:00+00:00",
            },
            "created_at": 1787659200,
        }
    ])

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(swarm_run_event_store, "_db", fake_db)
    events = swarm_run_event_store.list_events("run-1", "owner-1")

    assert events == [{
        "type": "status",
        "run_id": "run-1",
        "seq": 4,
        "ts": "2026-08-25T12:00:00+00:00",
        "payload": {"content": "ready"},
    }]
