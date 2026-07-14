"""Regression tests for the Friday/voice protected-lane fix in agents/utils/gpu_queue.py.

Covers:
- _is_protected_model matches only the configured voice model (no over-match onto
  qwen3:8b or the coder).
- evict_ollama() skips protected models (keep_alive=0 is never sent to them) while
  still evicting everything else, and the poll exits once only-protected remain.
- evict_ollama() leaves the SECONDARY host (Turing fast path) alone by default, and
  honours EVICT_SECONDARY_OLLAMA=true.
- Warm-pin: with WARM_PIN_PROTECTED_MODELS enabled, a resident protected model is
  re-pinned (keep_alive=-1); unpin_protected_models() hands it back (keep_alive=5m).

Redis/requests are monkeypatched so these run without external services.
"""

import importlib

import pytest


def _import_gpu_queue():
    import utils.gpu_queue as gq  # type: ignore
    importlib.reload(gq)
    return gq


class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


class _OllamaRecorder:
    """Fakes Ollama /api/ps (GET) and /api/generate (POST) across hosts.

    ps_by_host maps host -> list of model-name-lists returned on successive GETs
    (the final entry repeats once the earlier ones are consumed). Records every
    POST as (host, model, keep_alive) and every GET host."""

    def __init__(self, ps_by_host):
        self.ps_by_host = {h: list(v) for h, v in ps_by_host.items()}
        self.gets = []
        self.posts = []

    @staticmethod
    def _host(url):
        return url.rsplit("/api/", 1)[0]

    def get(self, url, timeout=None):
        host = self._host(url)
        self.gets.append(host)
        seq = self.ps_by_host.get(host, [[]])
        names = seq.pop(0) if len(seq) > 1 else (seq[0] if seq else [])
        return _FakeResp(200, {"models": [{"name": n} for n in names]})

    def post(self, url, json=None, timeout=None):
        self.posts.append((self._host(url), json.get("model"), json.get("keep_alive")))
        return _FakeResp(200, {})

    def keep_alives_for(self, model_substr):
        return [ka for (_h, m, ka) in self.posts if m and model_substr in m]


def _patch(gq, monkeypatch, rec, *, protected=("qwen3:14b",),
           evict_secondary=False, warm_pin=False,
           primary="http://primary:11434", secondary="http://secondary:11434"):
    monkeypatch.setattr(gq, "PROTECTED_OLLAMA_MODELS", frozenset(protected))
    monkeypatch.setattr(gq, "_EVICT_SECONDARY_OLLAMA", evict_secondary)
    monkeypatch.setattr(gq, "_WARM_PIN_PROTECTED", warm_pin)
    monkeypatch.setattr(gq, "OLLAMA_HOST", primary)
    monkeypatch.setattr(gq, "SECONDARY_OLLAMA_HOST", secondary)
    monkeypatch.setattr(gq.requests, "get", rec.get)
    monkeypatch.setattr(gq.requests, "post", rec.post)
    monkeypatch.setattr(gq.time, "sleep", lambda *a, **k: None)


# --- _is_protected_model ----------------------------------------------------

def test_is_protected_matches_only_voice_model(monkeypatch):
    gq = _import_gpu_queue()
    monkeypatch.setattr(gq, "PROTECTED_OLLAMA_MODELS", frozenset({"qwen3:14b"}))
    assert gq._is_protected_model("qwen3:14b")
    assert gq._is_protected_model("qwen3:14b-instruct-q4_K_M")
    assert not gq._is_protected_model("qwen3:8b")
    assert not gq._is_protected_model("qwen3-coder:30b")
    assert not gq._is_protected_model("gemma4:31b")
    assert not gq._is_protected_model("")


# --- evict skips the voice lane --------------------------------------------

def test_evict_skips_protected_model(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [
            ["qwen3:14b", "qwen3:8b", "gemma4:31b"],  # initial ps
            ["qwen3:14b"],                             # poll: only protected left
        ],
    })
    _patch(gq, monkeypatch, rec)
    gq.evict_ollama()

    assert 0 not in rec.keep_alives_for("qwen3:14b")   # voice never unloaded
    assert ("http://primary:11434", "qwen3:8b", 0) in rec.posts
    assert ("http://primary:11434", "gemma4:31b", 0) in rec.posts


# --- item 2: no collateral Turing eviction ----------------------------------

def test_evict_leaves_secondary_alone_by_default(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [["qwen3:8b"], []],
        "http://secondary:11434": [["qwen3:8b"], []],
    })
    _patch(gq, monkeypatch, rec, evict_secondary=False)
    gq.evict_ollama()
    assert "http://secondary:11434" not in rec.gets
    assert "http://primary:11434" in rec.gets


def test_evict_secondary_when_flag_set(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [["qwen3:8b"], []],
        "http://secondary:11434": [["llama3.2:3b"], []],
    })
    _patch(gq, monkeypatch, rec, evict_secondary=True)
    gq.evict_ollama()
    assert "http://secondary:11434" in rec.gets


# --- item 3: warm-pin + rollback -------------------------------------------

def test_warm_pin_pins_resident_protected_model(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [["qwen3:14b"], ["qwen3:14b"]],
    })
    _patch(gq, monkeypatch, rec, warm_pin=True)
    gq.evict_ollama()
    assert -1 in rec.keep_alives_for("qwen3:14b")     # pinned resident
    assert 0 not in rec.keep_alives_for("qwen3:14b")  # never evicted


def test_no_warm_pin_when_disabled(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [["qwen3:14b"], ["qwen3:14b"]],
    })
    _patch(gq, monkeypatch, rec, warm_pin=False)
    gq.evict_ollama()
    assert rec.keep_alives_for("qwen3:14b") == []     # neither evicted nor pinned


def test_unpin_restores_idle_unload(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({
        "http://primary:11434": [["qwen3:14b", "qwen3:8b"]],
    })
    _patch(gq, monkeypatch, rec)
    monkeypatch.setattr(gq, "_UNPIN_KEEP_ALIVE", "5m")
    gq.unpin_protected_models("http://primary:11434")
    assert "5m" in rec.keep_alives_for("qwen3:14b")
    assert rec.keep_alives_for("qwen3:8b") == []      # non-protected untouched


# --- warm-pin startup hook (main.py step 10) --------------------------------

def test_warm_pin_startup_hook_pins_when_enabled(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({})
    _patch(gq, monkeypatch, rec, warm_pin=True)
    gq.warm_pin_protected_models("http://primary:11434")
    assert -1 in rec.keep_alives_for("qwen3:14b")     # loaded + pinned from boot


def test_warm_pin_startup_hook_noop_when_disabled(monkeypatch):
    gq = _import_gpu_queue()
    rec = _OllamaRecorder({})
    _patch(gq, monkeypatch, rec, warm_pin=False)
    gq.warm_pin_protected_models("http://primary:11434")
    assert rec.posts == []                            # nothing loaded/pinned
