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

import time
import logging
import requests
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30
CHECK_TIMEOUT_SECONDS = 3


@dataclass
class NodeStatus:
    host: str
    name: str
    vram_mb: int
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
        import os
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        secondary_host = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")

        nodes = {
            ollama_host: NodeStatus(
                host=ollama_host, name="Lovelace", vram_mb=16384
            ),
        }
        if secondary_host and secondary_host != ollama_host:
            nodes[secondary_host] = NodeStatus(
                host=secondary_host, name="Turing", vram_mb=8192
            )
        return nodes

    def check_node(self, host: str) -> NodeStatus:
        """Ping an Ollama node and update its cached status."""
        status = self.nodes.get(host)
        if not status:
            status = NodeStatus(host=host, name="unknown", vram_mb=0)
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


