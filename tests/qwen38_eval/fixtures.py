from __future__ import annotations

from pathlib import Path


REVIEW_FILES = {
    "src/auth.py": "def validate(token):\n    return token is not None\n",
    "src/cache.py": "def key(user):\n    return 'user:' + user\n",
    "src/api.py": "def fetch(client, url):\n    response = client.get(url)\n    return response.json()\n",
}

EXPECTED_FINDINGS = {
    "src/auth.py:18": "issuer validation",
    "src/cache.py:42": "stale key",
    "src/api.py:77": "unchecked status",
}

BUILD_FILES = {
    "app.py": "def greet(name):\n    return f'Hello, {name}!'\n",
    "tests/test_app.py": "def test_greet():\n    assert greet('Ada') == 'Hello, Ada!'\n",
}

HIDDEN_BUILD_ASSERTIONS = {
    "app.py": "def greet(name):\n    return f'Hello, {name}!'\n",
    "tests/test_app.py": "assert greet('Ada') == 'Hello, Ada!'",
}


def seed_review_fixture(root: Path) -> Path:
    for name, content in REVIEW_FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def seed_build_fixture(root: Path) -> Path:
    for name, content in BUILD_FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def image_fixture() -> bytes:
    """Small deterministic PPM with a known three-color legend."""
    rows = [
        "P3", "6 2", "255",
        "255 0 0 0 255 0 0 0 255 255 255 255 255 0 0 0 255 0",
        "255 0 0 0 255 0 0 0 255 255 255 255 255 0 0 0 255 0",
    ]
    return ("\n".join(rows) + "\n").encode("ascii")


def long_context_fixture(fact_count: int = 1600) -> str:
    lines = [f"padding-{i:04d}: stable filler text" for i in range(fact_count)]
    lines[17] = "FACT-A=violet"
    lines[fact_count // 3] = "FACT-B=quartz"
    lines[(fact_count * 2) // 3] = "FACT-C=17"
    lines[-17] = "FACT-D=harbor"
    return "\n".join(lines)

