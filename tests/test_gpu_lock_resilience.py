"""Resilience tests for agents/utils/gpu_queue.py.

Covers:
- Fix A: in-process semaphore prevents concurrent zone-switching even when
  Redis is unavailable (fail-open path).
- Fix B: degraded-mode metrics (gpu_lock_degraded_total, gpu_mutex_healthy)
  fire when Redis ping() raises.
- Fix C: _CircuitBreaker opens after 3 consecutive failures, short-circuits
  while open, and probes after the cooldown.
- Fix D: call_with_model_fallback drops a failing model from the chain and
  retries with the next one.

These tests monkey-patch Redis / requests so they run without external
services.
"""

import threading
import time

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _import_gpu_queue():
    import importlib
    import utils.gpu_queue as gq  # type: ignore
    importlib.reload(gq)
    return gq


# ---------------------------------------------------------------------------
# Fix A — concurrent request_lock under Redis failure
# ---------------------------------------------------------------------------
def test_inproc_semaphore_serializes_when_redis_down(monkeypatch):
    gq = _import_gpu_queue()

    class _BrokenRedis:
        def ping(self):
            raise ConnectionError("Redis down (test)")
    monkeypatch.setattr(gq, "get_redis_client", lambda: _BrokenRedis())

    inside = {"count": 0, "max": 0}
    lock = threading.Lock()

    def worker():
        with gq.request_lock("image"):
            with lock:
                inside["count"] += 1
                inside["max"] = max(inside["max"], inside["count"])
            time.sleep(0.05)
            with lock:
                inside["count"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert inside["max"] == 1, (
        f"In-process semaphore failed — saw {inside['max']} concurrent holders"
    )


# ---------------------------------------------------------------------------
# Fix B — degraded metrics emission
# ---------------------------------------------------------------------------
def test_degraded_metrics_emit_on_redis_down(monkeypatch):
    gq = _import_gpu_queue()

    class _BrokenRedis:
        def ping(self):
            raise ConnectionError("Redis down (test)")
    monkeypatch.setattr(gq, "get_redis_client", lambda: _BrokenRedis())

    inc_calls = []
    set_calls = []

    class _FakeCounter:
        def labels(self, **kw):
            inc_calls.append(kw)
            return self
        def inc(self, *a, **kw):
            inc_calls.append("inc")

    class _FakeGauge:
        def set(self, v):
            set_calls.append(v)

    monkeypatch.setattr(gq, "GPU_LOCK_DEGRADED_TOTAL", _FakeCounter())
    monkeypatch.setattr(gq, "GPU_MUTEX_HEALTHY", _FakeGauge())

    with gq.request_lock("text"):
        pass

    assert {"reason": "redis_unavailable"} in inc_calls
    assert "inc" in inc_calls
    assert 0 in set_calls  # gauge dropped to 0 on degradation


# ---------------------------------------------------------------------------
# Fix C — circuit breaker open/close
# ---------------------------------------------------------------------------
def test_circuit_breaker_opens_after_threshold():
    gq = _import_gpu_queue()
    cb = gq._CircuitBreaker()
    host = "http://fake:1234"
    svc = "klein"

    assert cb.allow(host, svc) is True
    for _ in range(cb.FAIL_THRESHOLD):
        cb.record_failure(host, svc)
    assert cb.allow(host, svc) is False, "Circuit should be OPEN after threshold"


def test_circuit_breaker_short_circuits_post(monkeypatch):
    gq = _import_gpu_queue()
    cb = gq._circuit_breaker

    # Reset the breaker for this host/svc
    cb._circuits.pop(("http://test-klein:0", "klein"), None)

    call_count = {"n": 0}

    def fake_post(*a, **kw):
        call_count["n"] += 1
        raise ConnectionError("boom")

    monkeypatch.setattr(gq.requests, "post", fake_post)

    for _ in range(cb.FAIL_THRESHOLD):
        gq._guarded_post("http://test-klein:0", "klein", "/evict", timeout=1)

    # Now circuit should be OPEN — next call must NOT hit requests.post
    before = call_count["n"]
    result = gq._guarded_post("http://test-klein:0", "klein", "/evict", timeout=1)
    assert call_count["n"] == before, "Open circuit must short-circuit the post"
    assert result is None


def test_circuit_breaker_half_open_probe(monkeypatch):
    gq = _import_gpu_queue()
    cb = gq._circuit_breaker
    key = ("http://test2:0", "omnigen")
    cb._circuits.pop(key, None)

    # Drive it open
    for _ in range(cb.FAIL_THRESHOLD):
        cb.record_failure(key[0], key[1])
    assert cb.allow(key[0], key[1]) is False

    # Simulate cooldown elapsing by rewinding opened_at
    cb._circuits[key]["opened_at"] = time.monotonic() - (cb.OPEN_DURATION_S + 1)
    assert cb.allow(key[0], key[1]) is True  # half-open, probe permitted

    # Successful probe closes the circuit
    cb.record_success(key[0], key[1])
    assert cb.allow(key[0], key[1]) is True


# ---------------------------------------------------------------------------
# Fix D — model fallback wrapper
# ---------------------------------------------------------------------------
def test_call_with_model_fallback_drops_failing_model(monkeypatch):
    gq = _import_gpu_queue()

    monkeypatch.setattr(
        gq, "select_available_model",
        lambda pref, tail: (pref, "http://fake-host:0"),
    )

    attempts = []

    class _Resp:
        def __init__(self, status):
            self.status_code = status
            self.text = ""

    def call_fn(model, host):
        attempts.append(model)
        if model == "qwen3:14b":
            return _Resp(500)
        return _Resp(200)

    result = gq.call_with_model_fallback("qwen3:14b", ["qwen3:8b"], call_fn)
    assert result.status_code == 200
    assert attempts == ["qwen3:14b", "qwen3:8b"]


def test_call_with_model_fallback_exhaustion_raises(monkeypatch):
    gq = _import_gpu_queue()

    monkeypatch.setattr(
        gq, "select_available_model",
        lambda pref, tail: (pref, "http://fake-host:0"),
    )

    import requests as _r

    def call_fn(model, host):
        raise _r.exceptions.ConnectionError("dead")

    with pytest.raises(gq.AllModelsFailedError):
        gq.call_with_model_fallback("a", ["b"], call_fn, max_retries=2)
