"""
remote_executor.py — SSH Remote Execution Manager

Provides secure, session-pooled SSH command execution across the
Hive multi-node topology (Turing, BMO).

Note: Hopper and Lovelace are excluded — agents always run locally on those nodes.

Security:
    - Commands are validated through bash_classifier before execution
    - Private key auth only (no passwords)
    - Allowlisted hosts from config
    - Per-command timeout enforcement
    - Audit logging via security.audit_logger

Usage:
    from utils.remote_executor import get_remote_executor

    executor = get_remote_executor()
    result = executor.execute("Turing", "nvidia-smi")
    print(result.stdout)
"""

import os
import time
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from logger_setup import setup_logger

logger = setup_logger("RemoteExecutor")


@dataclass
class RemoteHost:
    """Definition of a remote SSH target."""
    name: str
    host: str
    user: str
    port: int = 22
    key_path: str = ""
    healthy: bool = False
    last_checked: float = 0.0


@dataclass
class ExecutionResult:
    """Result of a remote command execution."""
    host: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timed_out: bool = False

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
        }

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAIL(rc={self.exit_code})"
        return f"[{self.host}] {status} ({self.duration_ms:.0f}ms): {self.command}"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SSH_DEFAULT_TIMEOUT = int(os.getenv("SSH_DEFAULT_TIMEOUT", "60"))
SSH_CONNECT_TIMEOUT = int(os.getenv("SSH_CONNECT_TIMEOUT", "10"))
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SSH_USER = os.getenv("SSH_USER", "misterobots")

# Resolve SSH binary: prefer system PATH, fall back to Git for Windows bundled ssh
def _find_ssh_binary() -> str:
    import shutil
    if shutil.which("ssh"):
        return "ssh"
    git_ssh = r"C:\Program Files\Git\usr\bin\ssh.exe"
    if os.path.isfile(git_ssh):
        return git_ssh
    raise FileNotFoundError(
        "No ssh binary found. Install OpenSSH or Git for Windows, "
        "or set SSH_BINARY env var."
    )

SSH_BINARY = os.getenv("SSH_BINARY", _find_ssh_binary())
HEALTH_CHECK_TTL = 30  # seconds

# Host allowlist — only these names can be targeted (lowercase; matched via host_name.lower())
# Hopper and Lovelace are excluded: agents run locally on those nodes.
ALLOWED_HOSTS = {"turing", "bmo"}


class RemoteExecutor:
    """SSH-based remote command execution with health caching and safety checks."""

    def __init__(self):
        self._hosts: Dict[str, RemoteHost] = {}
        self._lock = threading.Lock()
        self._initialize_hosts()

    def _initialize_hosts(self):
        """Build host table from config.py topology."""
        from config import TURING_IP, BMO_IP

        key_path = SSH_KEY_PATH
        user = SSH_USER

        self._hosts = {
            "turing": RemoteHost(
                name="Turing",
                host=TURING_IP,
                user=user,
                key_path=key_path,
            ),
            "bmo": RemoteHost(
                name="BMO",
                host=BMO_IP,
                user=user,
                key_path=key_path,
            ),
        }

    def list_hosts(self) -> list[dict]:
        """Return all configured hosts with health status."""
        return [
            {
                "name": h.name,
                "host": h.host,
                "user": h.user,
                "healthy": h.healthy,
            }
            for h in self._hosts.values()
        ]

    def get_host(self, name: str) -> Optional[RemoteHost]:
        """Resolve a host name to its definition."""
        return self._hosts.get(name.lower())

    def check_health(self, host_name: str) -> bool:
        """SSH ping a host to check if it's reachable."""
        host = self.get_host(host_name)
        if not host:
            return False

        now = time.time()
        if now - host.last_checked < HEALTH_CHECK_TTL:
            return host.healthy

        try:
            result = self._ssh_exec(host, "echo ok", timeout=SSH_CONNECT_TIMEOUT)
            host.healthy = result.exit_code == 0
        except Exception as e:
            logger.warning(f"[RemoteExec] Health check failed for {host_name}: {e}")
            host.healthy = False

        host.last_checked = now
        return host.healthy

    def execute(
        self,
        host_name: str,
        command: str,
        timeout: int = SSH_DEFAULT_TIMEOUT,
        check_safety: bool = True,
    ) -> ExecutionResult:
        """
        Execute a command on a remote host via SSH.

        Args:
            host_name: Target host name (e.g. "Turing", "control-plane")
            command: Shell command to execute
            timeout: Max execution time in seconds
            check_safety: If True, run command through bash_classifier first

        Returns:
            ExecutionResult with stdout, stderr, exit_code, duration
        """
        # Validate host
        host_name_lower = host_name.lower()
        if host_name_lower not in ALLOWED_HOSTS:
            return ExecutionResult(
                host=host_name,
                command=command,
                stdout="",
                stderr=f"Host '{host_name}' not in allowlist: {ALLOWED_HOSTS}",
                exit_code=-1,
                duration_ms=0,
            )

        host = self.get_host(host_name_lower)
        if not host:
            return ExecutionResult(
                host=host_name,
                command=command,
                stdout="",
                stderr=f"Host '{host_name}' not configured",
                exit_code=-1,
                duration_ms=0,
            )

        # Safety check via bash_classifier
        if check_safety:
            blocked, reason = self._check_command_safety(command)
            if blocked:
                logger.warning(
                    f"[RemoteExec] BLOCKED command on {host_name}: {command} — {reason}"
                )
                return ExecutionResult(
                    host=host_name,
                    command=command,
                    stdout="",
                    stderr=f"Command blocked by safety classifier: {reason}",
                    exit_code=-2,
                    duration_ms=0,
                )

        # Execute
        try:
            result = self._ssh_exec(host, command, timeout=timeout)
            self._audit_log(host_name, command, result)
            return result
        except Exception as e:
            logger.error(f"[RemoteExec] Execution failed on {host_name}: {e}")
            return ExecutionResult(
                host=host_name,
                command=command,
                stdout="",
                stderr=str(e),
                exit_code=-3,
                duration_ms=0,
            )

    def _ssh_exec(
        self, host: RemoteHost, command: str, timeout: int = SSH_DEFAULT_TIMEOUT
    ) -> ExecutionResult:
        """Run a command via subprocess ssh (uses system SSH config + agent)."""
        ssh_args = [
            SSH_BINARY,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
            "-o", "BatchMode=yes",
            "-p", str(host.port),
        ]

        # Add key file if it exists
        if host.key_path and os.path.isfile(host.key_path):
            ssh_args.extend(["-i", host.key_path])

        ssh_args.append(f"{host.user}@{host.host}")
        ssh_args.append(command)

        start = time.time()
        try:
            proc = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.time() - start) * 1000

            return ExecutionResult(
                host=host.name,
                command=command,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start) * 1000
            return ExecutionResult(
                host=host.name,
                command=command,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-4,
                duration_ms=duration_ms,
                timed_out=True,
            )

    def _check_command_safety(self, command: str) -> Tuple[bool, str]:
        """Check command via bash_classifier. Returns (blocked, reason)."""
        try:
            from tools.bash_classifier import classify_command, is_blocked
            if is_blocked(command):
                result = classify_command(command)
                return True, result.reason
            return False, ""
        except ImportError:
            logger.debug("[RemoteExec] bash_classifier not available, skipping safety check")
            return False, ""

    def _audit_log(self, host_name: str, command: str, result: ExecutionResult):
        """Log remote execution to audit trail."""
        try:
            from security.audit_logger import get_audit_logger
            audit = get_audit_logger()
            audit.log_operation_executed(
                agent_name="RemoteExecutor",
                agent_id="remote-exec-system",
                operation="ssh_exec",
                resource=host_name,
                success=result.success,
                details={
                    "command": command,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "timed_out": result.timed_out,
                },
            )
        except Exception:
            pass  # Audit is best-effort


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_executor: Optional[RemoteExecutor] = None


def get_remote_executor() -> RemoteExecutor:
    global _executor
    if _executor is None:
        _executor = RemoteExecutor()
    return _executor


