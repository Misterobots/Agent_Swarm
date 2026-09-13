"""Tests for the "dense" GPU zone — the one that borrows Friday's card.

The invariant worth protecting: Friday must be flagged suspended BEFORE her brain is unloaded,
and un-flagged when the zone is released. Get the order wrong and a voice turn lands between
the unload and the flag, hanging on a model that no longer exists until LLM_TIMEOUT.

No Redis, no Ollama, no GPU — `requests` and `get_redis_client` are both faked.
"""
import os
import sys

import pytest

_AGENTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agents"))


class FakeRedis:
    """Records flag writes so tests can assert on ordering and TTL."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.calls: list[tuple] = []

    def set(self, key, value, ex=None):
        self.store[key] = value
        self.calls.append(("set", key, value, ex))

    def delete(self, key):
        self.store.pop(key, None)
        self.calls.append(("delete", key))

    def get(self, key):
        return self.store.get(key)


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class FakeRequests:
    """Minimal stand-in for the `requests` module, recording the sequence of calls."""

    def __init__(self, ps_models=None, reachable=True):
        self.ps_models = ps_models if ps_models is not None else []
        self.reachable = reachable
        self.calls: list[tuple] = []
        self._ps_hits = 0

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        if not self.reachable:
            raise ConnectionError("unreachable")
        self._ps_hits += 1
        # First /api/ps reports residents; later polls report empty (unload completed).
        return FakeResponse({"models": self.ps_models if self._ps_hits == 1 else []})

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, (json or {}).get("model"), (json or {}).get("keep_alive")))
        return FakeResponse({})


@pytest.fixture
def gq(monkeypatch):
    sys.path.insert(0, _AGENTS)
    sys.path.insert(0, os.path.join(_AGENTS, "utils"))
    import utils.gpu_queue as g
    monkeypatch.setattr(g.time, "sleep", lambda *_: None)  # don't wait on unload polling
    yield g


@pytest.fixture
def fake_redis(gq, monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(gq, "get_redis_client", lambda: r)
    return r


@pytest.mark.unit
class TestEvictFriday:
    def test_flag_is_set_before_the_unload(self, gq, fake_redis, monkeypatch):
        """The ordering invariant. A turn arriving mid-eviction must see the flag."""
        req = FakeRequests(ps_models=[{"name": "qwen3:8b"}])
        monkeypatch.setattr(gq, "requests", req)
        order: list[str] = []
        real_set = gq._set_voice_suspended
        monkeypatch.setattr(gq, "_set_voice_suspended",
                            lambda s, reason="": (order.append(f"flag={s}"), real_set(s, reason))[1])
        monkeypatch.setattr(req, "post", lambda *a, **k: (order.append("unload"), FakeResponse({}))[1])

        gq.evict_friday()
        assert order[0] == "flag=True", f"flag must precede unload, got {order}"
        assert "unload" in order

    def test_flag_carries_a_ttl(self, gq, fake_redis, monkeypatch):
        """Without a TTL, a dense job that dies mid-zone strands Friday offline forever."""
        monkeypatch.setattr(gq, "requests", FakeRequests())
        gq.evict_friday()
        sets = [c for c in fake_redis.calls if c[0] == "set"]
        assert sets and sets[0][3] == gq.VOICE_SUSPEND_TTL
        assert sets[0][1] == gq.VOICE_SUSPENDED_KEY

    def test_protected_models_are_evicted_anyway(self, gq, fake_redis, monkeypatch):
        """PROTECTED_OLLAMA_MODELS guards the voice lane from evict_ollama(). Overriding that
        guard is the entire purpose of this zone, so it must NOT be honoured here."""
        # compose sets PROTECTED_OLLAMA_MODELS=qwen3:8b; the module default is qwen3:14b, so pin
        # it here rather than let the test depend on the developer's environment.
        monkeypatch.setattr(gq, "PROTECTED_OLLAMA_MODELS", frozenset({"qwen3:8b"}))
        assert gq._is_protected_model("qwen3:8b"), "precondition: Friday's brain is protected"
        req = FakeRequests(ps_models=[{"name": "qwen3:8b"}])
        monkeypatch.setattr(gq, "requests", req)
        gq.evict_friday()
        unloads = [c for c in req.calls if c[0] == "POST" and c[3] == 0]
        assert [u[2] for u in unloads] == ["qwen3:8b"]

    def test_targets_fridays_host_not_the_shared_one(self, gq, fake_redis, monkeypatch):
        req = FakeRequests(ps_models=[{"name": "qwen3:8b"}])
        monkeypatch.setattr(gq, "requests", req)
        gq.evict_friday()
        assert all(gq.FRIDAY_OLLAMA_HOST in c[1] for c in req.calls)
        assert not any(gq.OLLAMA_HOST in c[1] for c in req.calls if gq.OLLAMA_HOST != gq.FRIDAY_OLLAMA_HOST)

    def test_unreachable_host_does_not_raise(self, gq, fake_redis, monkeypatch):
        """A dense job must still run if Friday's Ollama is down — as it is right now."""
        monkeypatch.setattr(gq, "requests", FakeRequests(reachable=False))
        gq.evict_friday()  # must not raise
        assert fake_redis.store.get(gq.VOICE_SUSPENDED_KEY) == "dense"


@pytest.mark.unit
class TestRestoreFriday:
    def test_clears_the_flag(self, gq, fake_redis, monkeypatch):
        monkeypatch.setattr(gq, "_WARM_FRIDAY_ON_RESTORE", False)
        fake_redis.store[gq.VOICE_SUSPENDED_KEY] = "dense"
        gq.restore_friday()
        assert gq.VOICE_SUSPENDED_KEY not in fake_redis.store

    def test_warm_runs_off_the_critical_path(self, gq, fake_redis, monkeypatch):
        """The warm must not block the zone switch, which already holds the GPU lock."""
        started = {}
        monkeypatch.setattr(gq, "_WARM_FRIDAY_ON_RESTORE", True)
        monkeypatch.setattr(gq.threading, "Thread",
                            lambda target, name=None, daemon=None: type(
                                "T", (), {"start": lambda s: started.update(daemon=daemon, name=name)})())
        gq.restore_friday()
        assert started.get("daemon") is True


@pytest.mark.unit
class TestZoneSwitch:
    @staticmethod
    def _record(gq, monkeypatch):
        calls: list[str] = []
        for fn in ("evict_friday", "evict_ollama", "evict_comfyui", "evict_klein",
                   "restore_friday", "warmup_klein", "evict_voice_engine", "restore_voice_engine"):
            monkeypatch.setattr(gq, fn, (lambda n: lambda *a, **k: calls.append(n))(fn))
        return calls

    def test_dense_evicts_friday_first(self, gq, monkeypatch):
        """Friday goes into canned mode before the slower ComfyUI/Klein evictions run."""
        calls = self._record(gq, monkeypatch)
        gq._run_zone_switch("dense", "text")
        assert calls[0] == "evict_friday", calls
        assert set(calls) >= {"evict_friday", "evict_ollama", "evict_comfyui", "evict_klein"}

    def test_leaving_dense_restores_friday(self, gq, monkeypatch):
        calls = self._record(gq, monkeypatch)
        gq._run_zone_switch("text", "dense")
        assert calls[0] == "restore_friday", calls

    def test_same_zone_is_a_noop(self, gq, monkeypatch):
        calls = self._record(gq, monkeypatch)
        gq._run_zone_switch("dense", "dense")
        assert calls == []

    def test_text_zone_never_touches_friday(self, gq, monkeypatch):
        """The whole point of the dedicated instance: ordinary text work leaves voice alone."""
        calls = self._record(gq, monkeypatch)
        gq._run_zone_switch("text", "image")
        assert "evict_friday" not in calls

    def test_training_also_reclaims_friday(self, gq, monkeypatch):
        calls = self._record(gq, monkeypatch)
        gq._run_zone_switch("training", "text")
        assert "evict_friday" in calls


@pytest.mark.unit
class TestFailOpen:
    def test_redis_down_does_not_break_the_zone_switch(self, gq, monkeypatch):
        """gpu_queue's contract is fail-open. A Redis outage must not block GPU work — the cost
        is that Friday won't know she's suspended, which is strictly better than a stuck swarm."""
        def boom():
            raise ConnectionError("redis down")
        monkeypatch.setattr(gq, "get_redis_client", boom)
        monkeypatch.setattr(gq, "requests", FakeRequests())
        gq.evict_friday()      # must not raise
        gq._set_voice_suspended(False)


@pytest.mark.unit
class TestVoiceEngineEviction:
    """voice-engine is a persistent CUDA process: only stop/start reclaims its ~5.5 GiB."""

    def test_evict_stops_rather_than_restarts(self, gq, monkeypatch):
        """A restart would reload the model and free nothing for the job's duration."""
        acts: list[tuple] = []
        monkeypatch.setattr(gq, "_owns_containers", lambda: True)
        monkeypatch.setattr(gq, "_container_action", lambda n, a: (acts.append((n, a)), True)[1])
        gq.evict_voice_engine()
        assert acts == [(gq.VOICE_ENGINE_CONTAINER, "stop")]

    def test_restore_starts_it(self, gq, monkeypatch):
        acts: list[tuple] = []
        monkeypatch.setattr(gq, "_owns_containers", lambda: True)
        monkeypatch.setattr(gq, "_container_action", lambda n, a: (acts.append((n, a)), True)[1])
        gq.restore_voice_engine()
        assert acts == [(gq.VOICE_ENGINE_CONTAINER, "start")]

    def test_noop_without_container_ownership(self, gq, monkeypatch):
        """A remote agent_runtime has no docker socket and must not try."""
        acts: list[tuple] = []
        monkeypatch.setattr(gq, "_owns_containers", lambda: False)
        monkeypatch.setattr(gq, "_container_action", lambda n, a: (acts.append((n, a)), True)[1])
        gq.evict_voice_engine()
        gq.restore_voice_engine()
        assert acts == []

    def test_dense_zone_evicts_and_exit_restores(self, gq, monkeypatch):
        calls = TestZoneSwitch._record(gq, monkeypatch)
        gq._run_zone_switch("dense", "text")
        assert "evict_voice_engine" in calls
        calls.clear()
        gq._run_zone_switch("text", "dense")
        assert "restore_voice_engine" in calls


@pytest.mark.unit
class TestZoneResolution:
    """Size-based zone selection: big models yield the voice lane, small ones don't."""

    @staticmethod
    def _sized(gq, monkeypatch, gib):
        monkeypatch.setattr(gq, "_model_size_bytes", lambda m: int(gib * 1024 ** 3))

    def test_large_model_upgrades_text_to_dense(self, gq, monkeypatch):
        self._sized(gq, monkeypatch, 17.28)  # qwen3-coder:30b
        assert gq.resolve_zone("text", "qwen3-coder:30b") == "dense"

    def test_small_model_stays_text(self, gq, monkeypatch):
        self._sized(gq, monkeypatch, 4.87)  # qwen3:8b
        assert gq.resolve_zone("text", "qwen3:8b") == "text"

    def test_threshold_is_inclusive(self, gq, monkeypatch):
        self._sized(gq, monkeypatch, 16.0)
        assert gq.resolve_zone("text", "exactly-at-threshold") == "dense"

    def test_other_zones_are_never_rewritten(self, gq, monkeypatch):
        """image/training already evict what they need; an explicit dense is honoured as-is."""
        self._sized(gq, monkeypatch, 30.0)
        for zone in ("image", "image_fast", "training", "dense"):
            assert gq.resolve_zone(zone, "huge:70b") == zone

    def test_no_model_is_a_passthrough(self, gq):
        """Existing call sites pass no model and must behave exactly as before."""
        assert gq.resolve_zone("text", None) == "text"

    def test_unknown_model_does_not_upgrade(self, gq, monkeypatch):
        """Catalog lookup failure must fail toward the LESS disruptive zone."""
        monkeypatch.setattr(gq, "requests", FakeRequests())
        monkeypatch.setattr(gq, "_model_size_cache", {}, raising=False)
        assert gq.resolve_zone("text", "never-heard-of-it:1b") == "text"
