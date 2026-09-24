"""Gauntlet's quality gate: what the critic accepts, and what it leaves behind.

A Gauntlet run is only worth its name if completion is *gated* on an independent
critic verdict that outlives the stream. These cover the verdict predicate and the
persistence that makes a resume truthful.
"""
import importlib
import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

# coordination.orchestrator pulls in native/legacy modules that only exist inside the
# runtime container; anything outside this list is a real failure and is re-raised.
_ALLOWED_ABSENT = frozenset({
    "pynvml",
    "ollama",  # coordination/decomposer.py imports `from ollama import Client`
    "prometheus_client",  # agents/metrics.py, reached via main -> church
    "phi", "phi.agent", "phi.model", "phi.model.ollama", "phi.knowledge",
    "phi.knowledge.combined", "phi.vectordb", "phi.vectordb.pgvector",
    "phi.storage", "phi.storage.agent", "phi.storage.agent.postgres",
})


def _import(name):
    # conftest.py puts control_plane/ ahead of agents/, and control_plane ships its own
    # `security` package that shadows the one these modules import. agents/ first, then
    # restored so no other test module sees the swap.
    agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
    original = list(sys.path)
    if agents_dir in sys.path:
        sys.path.remove(agents_dir)
    sys.path.insert(0, agents_dir)
    try:
        for _ in range(40):
            try:
                return importlib.import_module(name)
            except ModuleNotFoundError as exc:
                if exc.name not in _ALLOWED_ABSENT:
                    raise
                sys.modules[exc.name] = MagicMock()
        raise RuntimeError(f"{name} did not finish importing within the stub budget")
    finally:
        sys.path[:] = original


orchestrator = _import("coordination.orchestrator")
swarm_run_store = _import("swarm_run_store")


class RecordingCursor:
    def __init__(self, rows=()):
        self.calls = []
        self._rows = list(rows)
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.calls.append((" ".join(str(sql).split()), params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else (None,)

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class RecordingConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, **_kwargs):
        return self._cursor


@pytest.fixture
def store_db(monkeypatch):
    """Route swarm_run_store._db() at a recording cursor."""
    def install(rows=()):
        cursor = RecordingCursor(rows=rows)

        @contextmanager
        def fake_db():
            yield RecordingConnection(cursor)

        monkeypatch.setattr(swarm_run_store, "_db", fake_db)
        return cursor
    return install


# --- the verdict predicate -------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Reviewed the diff, tests pass.\nVERDICT: PASS", True),
    ("VERDICT: PASS", True),
    ("summary\n    verdict: pass", True),
    ("Reviewed it.\nVERDICT: FAIL\nGAP: no regression test", False),
    # A critic describing the format must not clear its own gate.
    ('End with "VERDICT: PASS" when satisfied.', False),
    ("", False),
    (None, False),
])
def test_only_a_line_initial_verdict_clears_the_gate(text, expected):
    assert orchestrator._gauntlet_passed(text) is expected


# --- persistence -----------------------------------------------------------

def test_record_gauntlet_review_stamps_the_bar_and_appends_a_numbered_verdict(store_db):
    # The SELECT already yields MAX(iteration)+1, so whatever it returns is the row's
    # iteration number; the store must use it verbatim rather than re-deriving it.
    cursor = store_db(rows=[(3,)])

    swarm_run_store.record_gauntlet_review(
        "coord-1", "https://example.test/bar", "fail", "GAP: build still fails",
    )

    statements = [sql for sql, _ in cursor.calls]
    assert any(s.startswith("UPDATE swarm_runs SET gauntlet_bar=") for s in statements), \
        "the run row must carry the bar so a restart can tell a Gauntlet from a Collective"
    assert any("MAX(iteration)" in s for s in statements)

    inserts = [p for sql, p in cursor.calls if sql.startswith("INSERT INTO swarm_gauntlet_reviews")]
    assert len(inserts) == 1, "the verdict must be persisted, not only streamed"
    coordination_id, iteration, verdict, critic_output, _ts = inserts[0]
    assert (coordination_id, iteration, verdict) == ("coord-1", 3, "fail")
    assert critic_output == "GAP: build still fails"


def test_record_gauntlet_review_is_non_fatal(monkeypatch):
    """A DB outage may not raise into the coordination loop."""
    @contextmanager
    def boom():
        raise RuntimeError("db down")
        yield None

    monkeypatch.setattr(swarm_run_store, "_db", boom)
    swarm_run_store.record_gauntlet_review("coord-1", "bar", "pass", "ok")


def test_schema_provides_the_gauntlet_columns_and_table(store_db):
    cursor = store_db()
    swarm_run_store.init_table()

    joined = "\n".join(sql for sql, _ in cursor.calls)
    assert "ADD COLUMN IF NOT EXISTS gauntlet_bar" in joined
    assert "CREATE TABLE IF NOT EXISTS swarm_gauntlet_reviews" in joined


def test_interrupted_gauntlet_stays_resumable_instead_of_reading_as_failed(store_db):
    cursor = store_db()
    swarm_run_store.reconcile_stale_runs("agent_runtime restarted mid-run")

    sql = cursor.calls[0][0]
    assert "gauntlet_bar" in sql
    assert "'needs_input'" in sql
    assert "'failed'" in sql, "ordinary interrupted runs must still be reported as failed"
