from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from coordination import workspace_lifecycle as lifecycle


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.query = ""
        self.params = None

    def execute(self, query, params=None):
        self.query, self.params = query, params

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class Connection:
    def __init__(self, row=None, rows=None):
        self.cursor_obj = Cursor(row, rows)

    def cursor(self, **_kwargs):
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_create_validates_identity_and_repository_inputs():
    with pytest.raises(ValueError):
        lifecycle.create(owner_id="../owner", session_id="s1")
    with pytest.raises(ValueError):
        lifecycle.create(owner_id="alice", session_id="s1", repository_ref="file:///tmp/repo")
    with pytest.raises(ValueError):
        lifecycle.create(owner_id="alice", session_id="s1", branch="../main")


def test_transition_is_owner_scoped_and_marks_cleanup(monkeypatch):
    row = {"worktree_id": "wt_1", "owner_id": "alice", "lifecycle_status": "exited", "cleanup_status": "exited"}
    connection = Connection(row=row)

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(lifecycle, "_db", fake_db)
    result = lifecycle.transition(worktree_id="wt_1", owner_id="alice", status="exited")
    assert result == row
    assert "WHERE worktree_id=%s AND owner_id=%s" in connection.cursor_obj.query
    assert connection.cursor_obj.params[-2:] == ("wt_1", "alice")


def test_transition_rejects_unknown_status():
    with pytest.raises(ValueError):
        lifecycle.transition(worktree_id="wt_1", owner_id="alice", status="deleted")
