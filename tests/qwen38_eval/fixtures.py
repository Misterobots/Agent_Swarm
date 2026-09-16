from __future__ import annotations

from pathlib import Path


def _defect_file(line: int, defect: str) -> str:
    lines = [f"# seeded review fixture line {i}" for i in range(1, line + 1)]
    lines[line - 1] = f"def defective_path(value):  # BUG: {defect}"
    return "\n".join(lines) + "\n"


REVIEW_FILES = {
    "src/auth.py": _defect_file(18, "missing issuer validation"),
    "src/cache.py": _defect_file(42, "stale key"),
    "src/api.py": _defect_file(77, "unchecked status"),
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


def chart_fixture() -> bytes:
    """Deterministic chart fixture with text assertions in the SVG itself."""
    return ("""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
<title>Qwen evaluation chart</title><text x="20" y="30">Quarterly latency chart</text>
<text x="30" y="330">Q1</text><text x="210" y="330">Q2</text><text x="390" y="330">Q3</text>
<text x="570" y="330">Q4</text><polyline points="40,260 220,210 400,150 580,90" stroke="blue" fill="none"/>
<text x="470" y="60">values 10 20 30 40</text></svg>""").encode("utf-8")


def screenshot_fixture() -> bytes:
    """Deterministic UI screenshot surrogate for API attachment tests."""
    return ("""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
<rect width="640" height="360" fill="white"/><text x="24" y="42">Memex project dashboard</text>
<text x="24" y="100">Qwen 3.8 Local Heavy</text><text x="24" y="145">Context: project 65536</text>
<text x="24" y="190">Status: approval required</text><text x="24" y="235">Project: fixture-alpha</text></svg>""").encode("utf-8")


def long_context_fixture(fact_count: int = 1600) -> str:
    lines = [f"padding-{i:04d}: stable filler text" for i in range(fact_count)]
    lines[17] = "FACT-A=violet"
    lines[fact_count // 3] = "FACT-B=quartz"
    lines[(fact_count * 2) // 3] = "FACT-C=17"
    lines[-17] = "FACT-D=harbor"
    return "\n".join(lines)
