"""
bridge.py — Cross-Machine Agent Bridge

Provides a relay layer for transparent cross-node agent operations.
A bridge client on one node can invoke agent APIs on another node,
routing through the Hive network topology.

Features:
    - Transparent request proxying to remote Hive API endpoints
    - Health-aware target selection (prefer healthy nodes)
    - Async task submission to remote nodes
    - Job status tracking across nodes
    - File transfer between nodes via SFTP/SCP

Usage:
    from utils.bridge import get_bridge

    bridge = get_bridge()
    result = bridge.submit_task("Turing", "Run nvidia-smi and report GPU usage")
    status = bridge.get_job_status(result["job_id"])
"""

import os
import time
import json
import uuid
import logging
import threading
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from logger_setup import setup_logger

logger = setup_logger("Bridge")


@dataclass
class BridgeNode:
    """A remote Hive node reachable via HTTP API."""
    name: str
    api_url: str
    healthy: bool = False
    last_checked: float = 0.0


@dataclass
class RemoteJob:
    """Tracks a job submitted to a remote node."""
    job_id: str
    target_node: str
    task: str
    status: str = "submitted"  # submitted, running, completed, failed, timeout
    result: Optional[str] = None
    error: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "target_node": self.target_node,
            "task": self.task,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "submitted_at": self.submitted_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BRIDGE_TIMEOUT = int(os.getenv("BRIDGE_TIMEOUT", "30"))
BRIDGE_HEALTH_TTL = 30  # seconds


class Bridge:
    """Cross-machine agent relay with job tracking."""

    def __init__(self):
        self._nodes: Dict[str, BridgeNode] = {}
        self._jobs: Dict[str, RemoteJob] = {}
        self._lock = threading.Lock()
        self._initialize_nodes()

    def _initialize_nodes(self):
        """Build node map from config topology."""
        from config import LOVELACE_IP, HOPPER_IP, TURING_IP

        # Each Hive node runs the swarm API on port 8000
        api_port = os.getenv("HIVE_API_PORT", "8000")

        self._nodes = {
            "Lovelace": BridgeNode(
                name="Lovelace",
                api_url=f"http://{LOVELACE_IP}:{api_port}",
            ),
            "control-plane": BridgeNode(
                name="control-plane",
                api_url=f"http://{HOPPER_IP}:{api_port}",
            ),
            "Turing": BridgeNode(
                name="Turing",
                api_url=f"http://{TURING_IP}:{api_port}",
            ),
        }

    def list_nodes(self) -> list[dict]:
        """Return all bridge nodes with health status."""
        return [
            {
                "name": n.name,
                "api_url": n.api_url,
                "healthy": n.healthy,
            }
            for n in self._nodes.values()
        ]

    def check_health(self, node_name: str) -> bool:
        """Ping a remote node's API health endpoint."""
        node = self._nodes.get(node_name.lower())
        if not node:
            return False

        now = time.time()
        if now - node.last_checked < BRIDGE_HEALTH_TTL:
            return node.healthy

        try:
            import requests
            resp = requests.get(
                f"{node.api_url}/",
                timeout=5,
            )
            node.healthy = resp.status_code == 200
        except Exception as e:
            logger.warning(f"[Bridge] Health check failed for {node_name}: {e}")
            node.healthy = False

        node.last_checked = now
        return node.healthy

    def check_all_health(self) -> Dict[str, bool]:
        """Ping all nodes and return health map."""
        return {name: self.check_health(name) for name in self._nodes}

    def submit_task(
        self,
        target_node: str,
        task: str,
        intent: Optional[str] = None,
        timeout: int = BRIDGE_TIMEOUT,
    ) -> dict:
        """
        Submit a task to a remote node's async task endpoint.

        Args:
            target_node: Name of the remote node (e.g. "Turing")
            task: Task description or command
            intent: Optional intent override
            timeout: HTTP request timeout

        Returns:
            dict with job_id, status, and any immediate result
        """
        node_name = target_node.lower()
        node = self._nodes.get(node_name)
        if not node:
            return {"error": f"Unknown node: {target_node}", "status": "failed"}

        job_id = str(uuid.uuid4())
        job = RemoteJob(job_id=job_id, target_node=node_name, task=task)

        with self._lock:
            self._jobs[job_id] = job

        try:
            import requests
            payload = {
                "task": task,
                "source": "bridge",
            }
            if intent:
                payload["intent"] = intent

            resp = requests.post(
                f"{node.api_url}/v1/task/async",
                json=payload,
                timeout=timeout,
            )

            if resp.status_code == 200:
                job.status = "running"
                job.result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                return job.to_dict()
            else:
                job.status = "failed"
                job.error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                return job.to_dict()

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error(f"[Bridge] Task submission to {node_name} failed: {e}")
            return job.to_dict()

    def proxy_request(
        self,
        target_node: str,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        timeout: int = BRIDGE_TIMEOUT,
    ) -> dict:
        """
        Proxy an arbitrary API request to a remote node.

        Args:
            target_node: Name of the target node
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g. "/v1/models")
            json_body: JSON body for POST/PUT
            timeout: Request timeout

        Returns:
            dict with status_code, body, and headers
        """
        node = self._nodes.get(target_node.lower())
        if not node:
            return {"error": f"Unknown node: {target_node}", "status_code": -1}

        try:
            import requests as req_lib
            url = f"{node.api_url}{path}"
            resp = req_lib.request(
                method=method.upper(),
                url=url,
                json=json_body,
                timeout=timeout,
            )

            body = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                body = resp.json()
            else:
                body = resp.text

            return {
                "status_code": resp.status_code,
                "body": body,
                "target_node": target_node,
                "url": url,
            }
        except Exception as e:
            return {
                "error": str(e),
                "status_code": -1,
                "target_node": target_node,
            }

    def transfer_file(
        self,
        source_node: str,
        dest_node: str,
        source_path: str,
        dest_path: str,
    ) -> dict:
        """
        Transfer a file between nodes via SCP.

        Uses the SSH Remote Executor's host definitions for auth.
        """
        try:
            from utils.remote_executor import get_remote_executor, SSH_CONNECT_TIMEOUT, SSH_KEY_PATH, SSH_USER

            executor = get_remote_executor()

            # Resolve destination host
            dest_host = executor.get_host(dest_node)
            if not dest_host:
                return {"error": f"Unknown destination: {dest_node}", "success": False}

            scp_args = [
                "scp",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
                "-o", "BatchMode=yes",
            ]

            if dest_host.key_path and os.path.isfile(dest_host.key_path):
                scp_args.extend(["-i", dest_host.key_path])

            # For now, only support local → remote transfers
            scp_args.append(source_path)
            scp_args.append(f"{dest_host.user}@{dest_host.host}:{dest_path}")

            result = subprocess.run(
                scp_args,
                capture_output=True,
                text=True,
                timeout=120,
            )

            return {
                "success": result.returncode == 0,
                "source": f"{source_node}:{source_path}",
                "dest": f"{dest_node}:{dest_path}",
                "stderr": result.stderr if result.returncode != 0 else "",
            }

        except Exception as e:
            return {"error": str(e), "success": False}

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Look up a previously submitted job."""
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def list_jobs(self, status_filter: Optional[str] = None) -> list[dict]:
        """List all tracked jobs, optionally filtered by status."""
        jobs = self._jobs.values()
        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]
        return [j.to_dict() for j in jobs]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_bridge: Optional[Bridge] = None


def get_bridge() -> Bridge:
    global _bridge
    if _bridge is None:
        _bridge = Bridge()
    return _bridge


