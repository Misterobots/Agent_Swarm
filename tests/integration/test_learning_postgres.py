"""Opt-in PostgreSQL concurrency and restart checks for learning.v1.

Run only against a disposable database with:

    LEARNING_TEST_POSTGRES_DSN=postgresql://... pytest -m integration tests/integration/test_learning_postgres.py

The test refuses the configured application DSN and never discovers or uses it
implicitly. The normal test suite skips this module when the explicit DSN is
absent.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents"))

from config import AGNO_DB_URL  # noqa: E402
from learning_contract import IdempotencyConflict, request_fingerprint  # noqa: E402
from learning_store import LearningStore  # noqa: E402


pytestmark = pytest.mark.integration


@pytest.fixture()
def disposable_store():
    dsn = os.getenv("LEARNING_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("LEARNING_TEST_POSTGRES_DSN is not configured")
    if dsn == AGNO_DB_URL:
        pytest.fail("refusing to run learning integration tests against AGNO_DB_URL")

    store = LearningStore(dsn=dsn)
    store.init_tables()
    owner = f"learning-test-{uuid4()}"
    yield store, owner, dsn

    # Cleanup is scoped to the unique test owner in the explicitly supplied
    # disposable database. No production table outside learning_* is touched.
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM learning_events WHERE owner_id=%s", (owner,))
            cur.execute("DELETE FROM learning_idempotency WHERE owner_id=%s", (owner,))
            cur.execute("DELETE FROM learning_jobs WHERE owner_id=%s", (owner,))


def _spec(owner: str) -> dict:
    return {
        "job_id": str(uuid4()),
        "owner_id": owner,
        "workspace_id": "learning-test-workspace",
        "kind": "sft",
        "budgets": {
            "window_timezone": "America/Chicago",
            "max_wall_clock_sec": 120,
            "max_retries": 1,
        },
    }


def test_concurrent_identical_creation_replays_one_job(disposable_store):
    store, owner, _dsn = disposable_store
    spec = _spec(owner)
    key = f"same-key-{uuid4()}"
    fingerprint = request_fingerprint(spec)

    def create():
        return store.create_job(
            spec,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _item: create(), range(2)))

    assert sorted(replayed for _response, replayed in results) == [False, True]
    assert {response["job"]["job_id"] for response, _replayed in results} == {spec["job_id"]}

    with pytest.raises(IdempotencyConflict):
        store.create_job(
            {**spec, "workspace_id": "different-workspace"},
            idempotency_key=key,
            request_fingerprint="sha256:different",
        )


def test_job_and_event_round_trip_after_new_store(disposable_store):
    store, owner, dsn = disposable_store
    spec = _spec(owner)
    response, replayed = store.create_job(
        spec,
        idempotency_key=f"restart-key-{uuid4()}",
        request_fingerprint=request_fingerprint(spec),
    )
    assert replayed is False

    restarted = LearningStore(dsn=dsn)
    job = restarted.get_job(spec["job_id"], owner)
    events = restarted.list_events(spec["job_id"], owner)

    assert job["budgets"]["max_wall_clock_sec"] == 120
    assert job["event_cursor"] == 0
    assert events[0]["experiment_id"] is None
    assert events[0]["event_seq"] == response["event"]["event_seq"] == 0
