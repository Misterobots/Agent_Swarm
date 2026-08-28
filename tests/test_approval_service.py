from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import dev_harness.approval_service as approvals


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.params = None

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self, row):
        self.cursor_obj = FakeCursor(row)

    def cursor(self, **_kwargs):
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_get_request_is_owner_scoped(monkeypatch):
    connection = FakeConnection({"call_id": "c1", "owner_id": "alice"})

    @contextmanager
    def fake_db():
        yield connection

    monkeypatch.setattr(approvals, "_db", fake_db)

    assert approvals.get_request("alice", "c1")["owner_id"] == "alice"
    assert "owner_id=%s" in connection.cursor_obj.query
    assert connection.cursor_obj.params == ("alice", "c1")


def test_get_request_rejects_missing_identity():
    assert approvals.get_request("", "c1") is None
    assert approvals.get_request("alice", "") is None


def test_arguments_hash_is_deterministic_and_does_not_return_raw_arguments():
    hashed = approvals.arguments_hash({"token": "secret", "z": 1})
    assert len(hashed) == 64
    assert "secret" not in hashed
    assert hashed == approvals.arguments_hash({"z": 1, "token": "secret"})
