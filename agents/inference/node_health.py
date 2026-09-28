"""
node_health.py — Ollama Node Health Monitor

Maintains a cached view of which Ollama nodes are alive and which models
are loaded on each. Uses lazy checking with a 30-second TTL — health is
only checked when a routing decision needs it.

Usage:
    from inference.node_health import get_node_monitor
    monitor = get_node_monitor()
    if monitor.is_healthy("http://192.168.2.103:11434"):
        ...
"""

import os
import time
import shutil
import logging
import subprocess
import requests
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30
CHECK_TIMEOUT_SECONDS = 3

# Node capacity comes from the deployment, not from a literal in this file. A
# runtime container normally has no GPU access at all, so it cannot measure the
# card it is reporting on; see _measure_visible_vram_mb for what it can do.
VRAM_ENV_BY_NAME = {"Lovelace": "LOVELACE_VRAM_MB", "Turing": "TURING_VRAM_MB"}

_VRAM_MEASURED: Optional[int] = None
_VRAM_MEASURED_ATTEMPTED = False


def _measure_visible_vram_mb() -> Optional[int]:
    """Total VRAM of the GPUs *this process* can see, or None if it sees none.

    Tries NVML first, then the nvidia-smi CLI. agent_runtime on Lovelace has
    neither the NVML shared library nor /dev/nvidia* nodes, so there this always
    returns None and only an explicit LOVELACE_VRAM_MB makes the number real.
    Cached because the answer cannot change within a process lifetime.
    """
    global _VRAM_MEASURED, _VRAM_MEASURED_ATTEMPTED
    if _VRAM_MEASURED_ATTEMPTED:
        return _VRAM_MEASURED
    _VRAM_MEASURED_ATTEMPTED = True

    try:
        import pynvml
        pynvml.nvmlInit()
        total_bytes = sum(
            pynvml.nvmlDeviceGetMemoryInfo(
                pynvml.nvmlDeviceGetHandleByIndex(i)
            ).total
            for i in range(pynvml.nvmlDeviceGetCount())
        )
        if total_bytes > 0:
            _VRAM_MEASURED = int(total_bytes // (1024 * 1024))
            logger.debug(f"[NodeHealth] NVML measured {_VRAM_MEASURED} MiB")
            return _VRAM_MEASURED
    except Exception:
        pass

    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run(
                [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=CHECK_TIMEOUT_SECONDS,
            ).stdout
            per_gpu = [int(line.strip()) for line in out.splitlines() if line.strip().isdigit()]
            if per_gpu:
                _VRAM_MEASURED = sum(per_gpu)
                logger.debug(f"[NodeHealth] nvidia-smi measured {_VRAM_MEASURED} MiB")
                return _VRAM_MEASURED
        except Exception:
            pass

    logger.debug("[NodeHealth] no GPU visible to this process; capacity must be configured")
    return None


def _host_is_local(host: str) -> bool:
    """True only for a loopback Ollama — the sole case where this process's own
    GPUs are the GPUs being reported on. A sibling container on the same machine
    (e.g. http://ollama:11434) is deliberately excluded: nothing here can prove
    it shares the card, so measuring for it would be a guess."""
    try:
        hostname = (urlparse(host).hostname or "").lower()
    except Exception:
        return False
    return hostname in ("localhost", "::1", "0.0.0.0") or hostname.startswith("127.")


def _resolve_node_vram(name: str, host: str) -> Tuple[Optional[int], str]:
    """(vram_mb, source) for a node: configured capacity wins, then a real
    measurement when the node is loopback-local, else unknown.

    Unknown is reported as None rather than a plausible default — a wrong integer
    here is indistinguishable from a right one downstream, which is how the old
    hardcoded single-card sizes came to be read as the box's real limit.
    """
    env_key = VRAM_ENV_BY_NAME.get(name)
    configured = ((os.getenv(env_key) or "").strip()) if env_key else ""
    if configured.isdigit() and int(configured) > 0:
        return int(configured), "configured"
    if _host_is_local(host):
        measured = _measure_visible_vram_mb()
        if measured:
            return measured, "measured"
    return None, "unknown"


@dataclass
class NodeStatus:
    host: str
    name: str
    vram_mb: Optional[int] = None
    vram_source: str = "unknown"  # configured | measured | unknown
    healthy: bool = False
    loaded_models: List[str] = field(default_factory=list)
    available_models: List[str] = field(default_factory=list)
    last_checked: float = 0.0


class NodeHealthMonitor:
    """
    Lazy-cached health monitor for Ollama inference nodes.
    Checks node health on demand, caches results for CACHE_TTL_SECONDS.
    """

    def __init__(self, nodes: Optional[Dict[str, NodeStatus]] = None):
        if nodes:
            self.nodes = nodes
        else:
            self.nodes = self._build_default_nodes()

    def _build_default_nodes(self) -> Dict[str, NodeStatus]:
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        secondary_host = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")

        def build(host: str, name: str) -> NodeStatus:
            vram_mb, vram_source = _resolve_node_vram(name, host)
            return NodeStatus(host=host, name=name, vram_mb=vram_mb,
                              vram_source=vram_source)

        nodes = {ollama_host: build(ollama_host, "Lovelace")}
        if secondary_host and secondary_host != ollama_host:
            nodes[secondary_host] = build(secondary_host, "Turing")
        return nodes

    def check_node(self, host: str) -> NodeStatus:
        """Ping an Ollama node and update its cached status."""
        status = self.nodes.get(host)
        if not status:
            vram_mb, vram_source = _resolve_node_vram("unknown", host)
            status = NodeStatus(host=host, name="unknown", vram_mb=vram_mb,
                                vram_source=vram_source)
            self.nodes[host] = status

        now = time.time()
        if now - status.last_checked < CACHE_TTL_SECONDS:
            return status

        # Check /api/tags (available models on disk)
        try:
            resp = requests.get(
                f"{host}/api/tags", timeout=CHECK_TIMEOUT_SECONDS
            )
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                status.available_models = [
                    m.get("name", "") for m in models_data
                ]
                status.healthy = True
            else:
                status.healthy = False
        except Exception:
            status.healthy = False
            status.last_checked = now
            logger.warning(f"[NodeHealth] {status.name} ({host}) is DOWN")
            return status

        # Check /api/ps (models currently loaded in VRAM)
        try:
            resp = requests.get(
                f"{host}/api/ps", timeout=CHECK_TIMEOUT_SECONDS
            )
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                status.loaded_models = [
                    m.get("name", "") for m in models_data
                ]
        except Exception:
            status.loaded_models = []

        status.last_checked = now
        logger.debug(
            f"[NodeHealth] {status.name}: healthy={status.healthy}, "
            f"loaded={len(status.loaded_models)}, "
            f"available={len(status.available_models)}"
        )
        return status

    def is_healthy(self, host: str) -> bool:
        """Returns cached health status, refreshing if stale."""
        status = self.check_node(host)
        return status.healthy

    def get_hosts_with_model(self, model_name: str) -> List[str]:
        """Returns healthy hosts that have this model available on disk."""
        results = []
        for host, status in self.nodes.items():
            self.check_node(host)
            if not status.healthy:
                continue
            if _model_matches(model_name, status.available_models):
                results.append(host)
        return results

    def get_hosts_with_model_loaded(self, model_name: str) -> List[str]:
        """Returns healthy hosts that have this model currently in VRAM."""
        results = []
        for host, status in self.nodes.items():
            self.check_node(host)
            if not status.healthy:
                continue
            if _model_matches(model_name, status.loaded_models):
                results.append(host)
        return results

    def get_all_statuses(self) -> List[dict]:
        """Returns all node statuses as dicts (for API responses)."""
        for host in self.nodes:
            self.check_node(host)
        return [
            {
                "name": s.name,
                "host": s.host,
                "healthy": s.healthy,
                "vram_mb": s.vram_mb,
                "vram_source": s.vram_source,
                "loaded_models": s.loaded_models,
                "available_models": s.available_models,
                "last_checked": s.last_checked,
            }
            for s in self.nodes.values()
        ]


def _model_matches(query: str, model_list: List[str]) -> bool:
    """Check if a model name matches any in a list (fuzzy prefix match)."""
    query_base = query.split(":")[0] if ":" in query else query
    for m in model_list:
        if query in m or query_base in m:
            return True
    return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_monitor: Optional[NodeHealthMonitor] = None


def get_node_monitor() -> NodeHealthMonitor:
    """Returns a shared NodeHealthMonitor instance (lazy init)."""
    global _monitor
    if _monitor is None:
        _monitor = NodeHealthMonitor()
    return _monitor


