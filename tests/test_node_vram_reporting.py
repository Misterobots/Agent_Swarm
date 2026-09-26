"""Node capacity reporting in inference/node_health.py.

Guards the decision that replaced two hardcoded VRAM literals. The numbers were
never inert: `vram_mb=16384` for Lovelace described a box that is 2 x 16311 MiB,
and read as a real limit it made a Collective's model fan-out look like VRAM
eviction rather than a configuration choice.

The contract is now: capacity comes from the deployment, or from a measurement
this process can actually take, and is reported as *unknown* when neither is
available. A guessed integer is the one outcome that must not come back, because
downstream nothing can tell it apart from a measured one.
"""
import pytest

import inference.node_health as nh


@pytest.fixture
def clean_env(monkeypatch):
    """No inherited capacity config, and no real GPU probing."""
    monkeypatch.delenv("LOVELACE_VRAM_MB", raising=False)
    monkeypatch.delenv("TURING_VRAM_MB", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("SECONDARY_OLLAMA_HOST", raising=False)
    monkeypatch.setattr(nh, "_measure_visible_vram_mb", lambda: None)
    return monkeypatch


def _nodes():
    return nh.NodeHealthMonitor().nodes


def test_configured_capacity_is_used_and_labelled(clean_env):
    clean_env.setenv("LOVELACE_VRAM_MB", "32622")
    clean_env.setenv("OLLAMA_HOST", "http://ollama:11434")
    node = _nodes()["http://ollama:11434"]
    assert node.vram_mb == 32622
    assert node.vram_source == "configured"


def test_unmeasurable_node_reports_unknown_not_a_default(clean_env):
    """The regression this whole change exists to stop."""
    clean_env.setenv("OLLAMA_HOST", "http://ollama:11434")
    clean_env.setenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")
    nodes = _nodes()
    assert nodes["http://ollama:11434"].vram_mb is None
    assert nodes["http://ollama:11434"].vram_source == "unknown"
    assert nodes["http://192.168.2.103:11434"].vram_mb is None


def test_loopback_capacity_is_measured(clean_env):
    clean_env.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    clean_env.setattr(nh, "_measure_visible_vram_mb", lambda: 32622)
    node = _nodes()["http://127.0.0.1:11434"]
    assert node.vram_mb == 32622
    assert node.vram_source == "measured"


def test_a_sibling_container_is_not_probed_as_localhost(clean_env):
    """`ollama` shares the host machine, but nothing here can prove it shares the
    cards, so a measurement must not be attributed to it."""
    clean_env.setenv("OLLAMA_HOST", "http://ollama:11434")
    clean_env.setattr(nh, "_measure_visible_vram_mb", lambda: 32622)
    node = _nodes()["http://ollama:11434"]
    assert node.vram_mb is None
    assert node.vram_source == "unknown"


def test_configuration_beats_a_measurement(clean_env):
    """An operator stating capacity outranks what this process happens to see."""
    clean_env.setenv("OLLAMA_HOST", "http://localhost:11434")
    clean_env.setenv("LOVELACE_VRAM_MB", "24576")
    clean_env.setattr(nh, "_measure_visible_vram_mb", lambda: 32622)
    node = _nodes()["http://localhost:11434"]
    assert node.vram_mb == 24576
    assert node.vram_source == "configured"


def test_junk_capacity_config_falls_through_to_unknown(clean_env):
    clean_env.setenv("OLLAMA_HOST", "http://ollama:11434")
    clean_env.setenv("LOVELACE_VRAM_MB", "thirty-two-ish")
    node = _nodes()["http://ollama:11434"]
    assert node.vram_mb is None
    assert node.vram_source == "unknown"


@pytest.mark.parametrize("host,expected", [
    ("http://localhost:11434", True),
    ("http://127.0.0.1:11434", True),
    ("http://127.0.0.53:11434", True),
    ("http://[::1]:11434", True),
    ("http://ollama:11434", False),
    ("http://192.168.2.103:11434", False),
    ("not a url", False),
    ("", False),
])
def test_locality_rule(host, expected):
    assert nh._host_is_local(host) is expected


def test_dynamically_discovered_host_starts_unknown(clean_env):
    monitor = nh.NodeHealthMonitor(nodes={})
    monkey = clean_env
    monkey.setattr(nh.requests, "get", lambda *a, **k: _raise())
    status = monitor.check_node("http://10.0.0.9:11434")
    assert status.vram_mb is None
    assert status.vram_source == "unknown"
    assert status.healthy is False


def test_status_payload_carries_the_source(clean_env):
    clean_env.setenv("OLLAMA_HOST", "http://ollama:11434")
    clean_env.setenv("LOVELACE_VRAM_MB", "32622")
    monitor = nh.NodeHealthMonitor()
    monkey = clean_env
    monkey.setattr(nh.requests, "get", lambda *a, **k: _raise())
    payload = monitor.get_all_statuses()[0]
    assert payload["vram_mb"] == 32622
    assert payload["vram_source"] == "configured"
    # The desktop only reads `healthy` out of this response today, so the source
    # field is the sole defence against the number being trusted implicitly again.
    assert set(payload) >= {"name", "host", "healthy", "vram_mb", "vram_source"}


def _raise():
    raise OSError("node down")


def test_module_source_no_longer_asserts_a_card_size():
    """Source-text guard: a literal card size in this file is indistinguishable
    from measured data by everything downstream that reads it."""
    with open(nh.__file__, encoding="utf-8") as fh:
        source = fh.read()
    for stale in ("16384", "8192"):
        assert stale not in source, f"{stale} MB hardcode is back in node_health.py"
