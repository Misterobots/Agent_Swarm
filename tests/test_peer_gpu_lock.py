"""
Tests for the cross-host GPU peer lock system.

Three test groups:
  1. Lock server (api.gpu_lock) — unit tests of the FastAPI router via
     TestClient (no real network). Covers acquire, release, TTL expiry,
     double-acquire, wrong lock_id on release.

  2. Peer lock client (utils.peer_lock) — integration tests using a real
     httpserver (uvicorn + TestClient via threading) to verify the
     client's polling, timeout, and unavailable-server behaviour.

  3. request_lock() 3-tier fallback — monkey-patches Redis *and* the peer
     lock client to verify the fallback ladder:
       Tier 1 Redis OK → no peer lock call
       Tier 2 Redis down, peer lock up → peer lock used, in-proc semaphore held
       Tier 3 Redis down, peer lock unreachable → in-proc semaphore only
"""

import sys
import os
import threading
import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# Make sure agents/ is on the path (mirrors conftest.py)
# ---------------------------------------------------------------------------
_AGENTS = os.path.join(os.path.dirname(__file__), "..", "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)


# ============================================================
# Group 1: Lock server (TestClient, no real network)
# ============================================================

@pytest.fixture()
def lock_client(monkeypatch):
    """TestClient wrapping the GPU lock FastAPI router."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    # Reset server state between tests
    import api.gpu_lock as gl
    gl._state.clear()
    app = FastAPI()
    app.include_router(gl.router)
    monkeypatch.setattr(gl, "_SECRET", "")  # disable auth for tests
    return TestClient(app)


def test_acquire_free_lock(lock_client):
    lid = uuid.uuid4().hex
    r = lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid, "context": "image", "ttl": 60})
    assert r.status_code == 200
    body = r.json()
    assert body["acquired"] is True
    assert body["lock_id"] == lid
    assert body["holder_context"] == "image"


def test_acquire_when_held_returns_false(lock_client):
    lid1 = uuid.uuid4().hex
    lid2 = uuid.uuid4().hex
    lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid1, "context": "image", "ttl": 60})
    r = lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid2, "context": "text", "ttl": 60})
    assert r.status_code == 200
    body = r.json()
    assert body["acquired"] is False
    assert body["holder_context"] == "image"
    assert body["retry_after"] > 0


def test_release_by_holder(lock_client):
    lid = uuid.uuid4().hex
    lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid, "context": "image", "ttl": 60})
    r = lock_client.post("/internal/gpu-lock/release", json={"lock_id": lid})
    assert r.status_code == 200
    assert r.json()["released"] is True

    # Lock should be free now
    lid2 = uuid.uuid4().hex
    r2 = lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid2, "context": "text", "ttl": 60})
    assert r2.json()["acquired"] is True


def test_release_wrong_id_rejected(lock_client):
    lid = uuid.uuid4().hex
    lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid, "context": "image", "ttl": 60})
    r = lock_client.post("/internal/gpu-lock/release", json={"lock_id": "wrong_id"})
    assert r.status_code == 200
    assert r.json()["released"] is False
    assert r.json()["reason"] == "not_holder"


def test_ttl_expiry_allows_reacquire(lock_client):
    """A lease with a very short TTL should be auto-evicted on the next acquire call."""
    import api.gpu_lock as gl
    lid = uuid.uuid4().hex
    lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid, "context": "image", "ttl": 0.01})
    time.sleep(0.05)  # let the TTL expire

    lid2 = uuid.uuid4().hex
    r = lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid2, "context": "text", "ttl": 60})
    assert r.json()["acquired"] is True


def test_status_reflects_state(lock_client):
    r = lock_client.get("/internal/gpu-lock/status")
    assert r.status_code == 200
    assert r.json()["locked"] is False

    lid = uuid.uuid4().hex
    lock_client.post("/internal/gpu-lock/acquire", json={"lock_id": lid, "context": "compose", "ttl": 30})
    r = lock_client.get("/internal/gpu-lock/status")
    body = r.json()
    assert body["locked"] is True
    assert body["holder_context"] == "compose"
    assert body["remaining_s"] > 0


def test_auth_required_when_secret_set(monkeypatch):
    import api.gpu_lock as gl
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    gl._state.clear()
    monkeypatch.setattr(gl, "_SECRET", "supersecret")
    app = FastAPI()
    app.include_router(gl.router)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/internal/gpu-lock/acquire", json={"lock_id": "x", "context": "text", "ttl": 10})
    assert r.status_code == 401

    r2 = client.post(
        "/internal/gpu-lock/acquire",
        json={"lock_id": "x", "context": "text", "ttl": 10},
        headers={"X-GPU-Lock-Secret": "supersecret"},
    )
    assert r2.json()["acquired"] is True


# ============================================================
# Group 2: Peer lock client — concurrent serialisation test
# ============================================================
# We spin up a real in-process TestServer using threading so the
# synchronous peer_lock client can call it over the network.

class _ThreadedTestServer:
    """Runs a FastAPI app in a background thread via uvicorn.
    Provides a base_url (http://127.0.0.1:<port>).
    """
    def __init__(self):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._thread = None
        self._server = None

    def start(self):
        import uvicorn
        from fastapi import FastAPI
        import api.gpu_lock as gl
        gl._state.clear()
        app = FastAPI()
        app.include_router(gl.router)
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        # Wait for the server to be ready
        deadline = time.monotonic() + 5
        import requests as _r
        while time.monotonic() < deadline:
            try:
                _r.get(f"{self.base_url}/internal/gpu-lock/status", timeout=0.5)
                break
            except Exception:
                time.sleep(0.1)

    def stop(self):
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=3)


@pytest.fixture(scope="module")
def peer_server():
    srv = _ThreadedTestServer()
    srv.start()
    yield srv
    srv.stop()


def test_peer_lock_serializes_concurrent_threads(peer_server, monkeypatch):
    """Two threads using peer_lock on the same lock server must not overlap."""
    import utils.peer_lock as pl
    monkeypatch.setattr(pl, "GPU_LOCK_HOST", peer_server.base_url)
    monkeypatch.setattr(pl, "_ACQUIRE_URL", f"{peer_server.base_url}/internal/gpu-lock/acquire")
    monkeypatch.setattr(pl, "_RELEASE_URL", f"{peer_server.base_url}/internal/gpu-lock/release")
    monkeypatch.setattr(pl, "_STATUS_URL",  f"{peer_server.base_url}/internal/gpu-lock/status")

    inside = {"count": 0, "max": 0}
    lock = threading.Lock()
    errors = []

    def worker():
        try:
            with pl.peer_lock("image", timeout=30):
                with lock:
                    inside["count"] += 1
                    inside["max"] = max(inside["max"], inside["count"])
                time.sleep(0.1)
                with lock:
                    inside["count"] -= 1
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Worker errors: {errors}"
    assert inside["max"] == 1, (
        f"Peer lock failed to serialize — saw {inside['max']} concurrent holders"
    )


def test_peer_lock_unavailable_raises(monkeypatch):
    """If the lock server is not running, PeerLockUnavailableError is raised."""
    import utils.peer_lock as pl
    monkeypatch.setattr(pl, "_ACQUIRE_URL", "http://127.0.0.1:19999/internal/gpu-lock/acquire")
    monkeypatch.setattr(pl, "_CONN_TIMEOUT", 0.3)
    monkeypatch.setattr(pl, "_READ_TIMEOUT",  0.3)

    with pytest.raises(pl.PeerLockUnavailableError):
        with pl.peer_lock("text", timeout=5):
            pass  # should not reach here


# ============================================================
# Group 3: request_lock() 3-tier fallback
# ============================================================

def test_request_lock_tier1_redis_ok_no_peer_lock_call(monkeypatch):
    """When Redis is healthy, the peer lock should never be called."""
    import utils.gpu_queue as gq

    class _MockRedis:
        _zone = {}
        def ping(self): pass
        def set(self, k, v, nx=False, ex=None):
            if nx and k in self._zone:
                return False
            self._zone[k] = v
            return True
        def get(self, k): return self._zone.get(k)
        def delete(self, k): self._zone.pop(k, None)

    monkeypatch.setattr(gq, "get_redis_client", lambda: _MockRedis())
    peer_called = {"n": 0}

    import utils.peer_lock as pl
    original_peer_lock = pl.peer_lock

    from contextlib import contextmanager
    @contextmanager
    def spy_peer_lock(*a, **kw):
        peer_called["n"] += 1
        with original_peer_lock(*a, **kw):
            yield

    monkeypatch.setattr(pl, "peer_lock", spy_peer_lock)

    with gq.request_lock("text"):
        pass

    assert peer_called["n"] == 0, "Peer lock should NOT be called when Redis is healthy"


def test_request_lock_tier2_redis_down_peer_up(peer_server, monkeypatch):
    """When Redis is down but peer lock server is up, Tier 2 must serialise."""
    import utils.gpu_queue as gq
    import utils.peer_lock as pl

    class _DeadRedis:
        def ping(self): raise ConnectionError("Redis down")

    monkeypatch.setattr(gq, "get_redis_client", lambda: _DeadRedis())
    monkeypatch.setattr(pl, "GPU_LOCK_HOST", peer_server.base_url)
    monkeypatch.setattr(pl, "_ACQUIRE_URL", f"{peer_server.base_url}/internal/gpu-lock/acquire")
    monkeypatch.setattr(pl, "_RELEASE_URL", f"{peer_server.base_url}/internal/gpu-lock/release")
    monkeypatch.setattr(pl, "_STATUS_URL",  f"{peer_server.base_url}/internal/gpu-lock/status")

    # Reset server state
    import api.gpu_lock as gl
    gl._state.clear()

    inside = {"count": 0, "max": 0}
    lock = threading.Lock()

    def worker():
        with gq.request_lock("text"):
            with lock:
                inside["count"] += 1
                inside["max"] = max(inside["max"], inside["count"])
            time.sleep(0.05)
            with lock:
                inside["count"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert inside["max"] == 1, (
        f"Tier 2 peer lock failed to serialise — saw {inside['max']} concurrent holders"
    )


def test_request_lock_tier3_both_down_uses_inproc(monkeypatch):
    """When Redis AND peer lock server are both down, Tier 3 (in-proc) activates."""
    import utils.gpu_queue as gq
    import utils.peer_lock as pl

    class _DeadRedis:
        def ping(self): raise ConnectionError("Redis down")

    monkeypatch.setattr(gq, "get_redis_client", lambda: _DeadRedis())
    monkeypatch.setattr(pl, "_ACQUIRE_URL", "http://127.0.0.1:19998/nope")
    monkeypatch.setattr(pl, "_CONN_TIMEOUT", 0.2)
    monkeypatch.setattr(pl, "_READ_TIMEOUT",  0.2)

    # Should still yield without raising
    reached = {"v": False}
    with gq.request_lock("text"):
        reached["v"] = True

    assert reached["v"], "request_lock Tier 3 must still yield even when both Redis and peer lock are down"
