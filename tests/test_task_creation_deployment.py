"""Deployment contract for the owner-authenticated New Task composer."""

from pathlib import Path


def test_canonical_compose_enables_direct_task_creation_with_override():
    compose = (
        Path(__file__).parents[1] / "turing_gateway" / "docker-compose.yml"
    ).read_text(encoding="utf-8")

    assert "TASKS_DIRECT_CREATE_ENABLED=${TASKS_DIRECT_CREATE_ENABLED:-true}" in compose
