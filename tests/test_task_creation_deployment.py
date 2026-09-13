"""Deployment contract for the owner-authenticated New Task composer."""

from pathlib import Path


def test_both_turing_compose_variants_enable_direct_task_creation_with_override():
    root = Path(__file__).parents[1] / "turing_gateway"
    expected = "TASKS_DIRECT_CREATE_ENABLED=${TASKS_DIRECT_CREATE_ENABLED:-true}"

    for name in ("docker-compose.yml", "docker-compose-Justin-PC.yml"):
        compose = (root / name).read_text(encoding="utf-8")
        assert expected in compose, name
