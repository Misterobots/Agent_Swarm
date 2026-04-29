"""
AUTO_REPAIR_DAEMON — Automatically detect and fix common infrastructure issues.

This daemon monitors critical services and automatically repairs common issues:
- Authentik database index corruption
- Container restarts for crashed services
- Database connection pool exhaustion
- Network connectivity issues

Run as a background service or scheduled task.
"""

import os
import sys
import time
import logging
import socket
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dataclasses import dataclass, field

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "auto_repair.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AutoRepair")

# Node configuration
TURING_IP = os.getenv("TURING_IP", "192.168.2.103")
HOPPER_IP = os.getenv("HOPPER_IP", "192.168.2.102")
LOVELACE_IP = os.getenv("LOVELACE_IP", "192.168.2.101")
SSH_USER = "misterobots"
SSH_BIN = "C:\\Windows\\System32\\OpenSSH\\ssh.exe"

# Authentik database credentials
AUTHENTIK_DB_USER = os.getenv("AUTHENTIK_DB_USER", "misterobots")
AUTHENTIK_DB_PASSWORD = os.getenv("AUTHENTIK_DB_PASSWORD", "")

# Check intervals (seconds)
CHECK_INTERVAL = int(os.getenv("AUTO_REPAIR_CHECK_INTERVAL", "300"))  # 5 minutes
REPAIR_COOLDOWN = int(os.getenv("AUTO_REPAIR_COOLDOWN", "600"))  # 10 minutes between repairs


@dataclass
class RepairAction:
    """Represents a repair action taken by the daemon."""
    timestamp: datetime
    issue_type: str
    service: str
    action: str
    success: bool
    details: str = ""


@dataclass
class ServiceHealth:
    """Represents the health status of a service."""
    name: str
    node: str
    healthy: bool
    container: Optional[str] = None
    error_message: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.now)


class AutoRepairDaemon:
    """Main auto-repair daemon class."""
    
    def __init__(self):
        self.repair_history: List[RepairAction] = []
        self.last_repair_time: Dict[str, datetime] = {}
        self.consecutive_failures: Dict[str, int] = {}
        
    def run_ssh_command(self, node_ip: str, command: str) -> Tuple[bool, str]:
        """Execute a command on a remote node via SSH."""
        try:
            ssh_cmd = [
                SSH_BIN,
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                f"{SSH_USER}@{node_ip}",
                command
            ]
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "SSH command timed out"
        except Exception as e:
            return False, f"SSH error: {str(e)}"
    
    def check_tcp_port(self, host: str, port: int, timeout: float = 3.0) -> bool:
        """Check if a TCP port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def check_http_endpoint(self, url: str, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """Check if an HTTP endpoint is responding."""
        try:
            response = requests.get(url, timeout=timeout, verify=False)
            return response.status_code < 500, None
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection error: {str(e)[:100]}"
        except Exception as e:
            return False, f"Error: {str(e)[:100]}"
    
    def check_authentik_health(self) -> ServiceHealth:
        """Check Authentik service health."""
        logger.info("Checking Authentik health...")
        
        # Check if Authentik is responding
        url = f"http://{TURING_IP}:9000/-/health/live/"
        healthy, error = self.check_http_endpoint(url)
        
        if healthy:
            return ServiceHealth(
                name="Authentik",
                node="Turing",
                healthy=True,
                container="authentik"
            )
        
        # Check container logs for database corruption
        success, logs = self.run_ssh_command(
            TURING_IP,
            'docker logs --tail 50 authentik 2>&1 | grep -i "unexpected zero page"'
        )
        
        has_corruption = success and "unexpected zero page" in logs
        
        return ServiceHealth(
            name="Authentik",
            node="Turing",
            healthy=False,
            container="authentik",
            error_message="Database corruption detected" if has_corruption else error
        )
    
    def repair_authentik_database(self) -> RepairAction:
        """Repair Authentik database by running REINDEX."""
        logger.warning("Attempting to repair Authentik database...")
        
        if not AUTHENTIK_DB_PASSWORD:
            return RepairAction(
                timestamp=datetime.now(),
                issue_type="database_corruption",
                service="authentik",
                action="reindex_database",
                success=False,
                details="AUTHENTIK_DB_PASSWORD not configured"
            )
        
        # Run full REINDEX on authentik database
        reindex_cmd = (
            f'docker exec -e PGPASSWORD={AUTHENTIK_DB_PASSWORD} authentik-postgres '
            f'psql -U {AUTHENTIK_DB_USER} -d authentik -c "REINDEX DATABASE authentik;"'
        )
        
        success, output = self.run_ssh_command(TURING_IP, reindex_cmd)
        
        if success and "REINDEX" in output:
            # Restart Authentik container
            logger.info("REINDEX successful, restarting Authentik...")
            restart_success, restart_output = self.run_ssh_command(
                TURING_IP,
                "docker restart authentik"
            )
            
            if restart_success:
                logger.info("Authentik database repaired and container restarted")
                time.sleep(10)  # Wait for container to start
                
                return RepairAction(
                    timestamp=datetime.now(),
                    issue_type="database_corruption",
                    service="authentik",
                    action="reindex_database",
                    success=True,
                    details="Database reindexed and container restarted"
                )
            else:
                return RepairAction(
                    timestamp=datetime.now(),
                    issue_type="database_corruption",
                    service="authentik",
                    action="reindex_database",
                    success=False,
                    details=f"REINDEX succeeded but restart failed: {restart_output}"
                )
        else:
            return RepairAction(
                timestamp=datetime.now(),
                issue_type="database_corruption",
                service="authentik",
                action="reindex_database",
                success=False,
                details=f"REINDEX failed: {output}"
            )
    
    def check_postgres_health(self) -> ServiceHealth:
        """Check PostgreSQL health."""
        logger.info("Checking PostgreSQL health...")
        
        # Check if PostgreSQL port is open
        if self.check_tcp_port(HOPPER_IP, 5432):
            return ServiceHealth(
                name="PostgreSQL",
                node="Hopper",
                healthy=True,
                container="postgres"
            )
        else:
            return ServiceHealth(
                name="PostgreSQL",
                node="Hopper",
                healthy=False,
                container="postgres",
                error_message="Port 5432 not responding"
            )
    
    def restart_container(self, node_ip: str, container_name: str) -> RepairAction:
        """Restart a Docker container."""
        logger.warning(f"Restarting container {container_name} on node...")
        
        success, output = self.run_ssh_command(
            node_ip,
            f"docker restart {container_name}"
        )
        
        if success:
            logger.info(f"Container {container_name} restarted successfully")
            time.sleep(5)  # Wait for container to start
        
        return RepairAction(
            timestamp=datetime.now(),
            issue_type="container_failure",
            service=container_name,
            action="restart_container",
            success=success,
            details=output if not success else "Container restarted"
        )
    
    def check_redis_health(self) -> ServiceHealth:
        """Check Redis health."""
        logger.info("Checking Redis health...")
        
        if self.check_tcp_port(HOPPER_IP, 6379):
            return ServiceHealth(
                name="Redis",
                node="Hopper",
                healthy=True,
                container="redis"
            )
        else:
            return ServiceHealth(
                name="Redis",
                node="Hopper",
                healthy=False,
                container="redis",
                error_message="Port 6379 not responding"
            )
    
    def check_langfuse_health(self) -> ServiceHealth:
        """Check Langfuse health."""
        logger.info("Checking Langfuse health...")
        
        url = f"http://{HOPPER_IP}:3000/api/public/health"
        healthy, error = self.check_http_endpoint(url)
        
        return ServiceHealth(
            name="Langfuse",
            node="Hopper",
            healthy=healthy,
            container="langfuse",
            error_message=error
        )
    
    def should_repair(self, service_name: str) -> bool:
        """Check if enough time has passed since last repair attempt."""
        last_repair = self.last_repair_time.get(service_name)
        
        if last_repair is None:
            return True
        
        elapsed = (datetime.now() - last_repair).total_seconds()
        return elapsed >= REPAIR_COOLDOWN
    
    def perform_health_check_and_repair(self):
        """Main health check and repair logic."""
        logger.info("=" * 60)
        logger.info("Starting health check cycle...")
        
        # Check all critical services
        services_to_check = [
            (self.check_authentik_health, self.repair_authentik_database),
            (self.check_postgres_health, lambda: self.restart_container(HOPPER_IP, "postgres")),
            (self.check_redis_health, lambda: self.restart_container(HOPPER_IP, "redis")),
            (self.check_langfuse_health, lambda: self.restart_container(HOPPER_IP, "langfuse")),
        ]
        
        for check_func, repair_func in services_to_check:
            try:
                health = check_func()
                logger.info(f"{health.name} on {health.node}: {'[OK] Healthy' if health.healthy else '[FAIL] Unhealthy'}")
                
                if not health.healthy:
                    logger.warning(f"{health.name} issue detected: {health.error_message}")
                    
                    # Check if we should attempt repair
                    if self.should_repair(health.name):
                        logger.info(f"Attempting auto-repair for {health.name}...")
                        
                        action = repair_func()
                        self.repair_history.append(action)
                        self.last_repair_time[health.name] = action.timestamp
                        
                        if action.success:
                            logger.info(f"[OK] Repair successful: {action.details}")
                            self.consecutive_failures[health.name] = 0
                        else:
                            logger.error(f"[FAIL] Repair failed: {action.details}")
                            self.consecutive_failures[health.name] = \
                                self.consecutive_failures.get(health.name, 0) + 1
                            
                            # Alert if too many consecutive failures
                            if self.consecutive_failures[health.name] >= 3:
                                logger.critical(
                                    f"ALERT: {health.name} has failed 3+ consecutive repair attempts. "
                                    "Manual intervention required!"
                                )
                    else:
                        last_repair = self.last_repair_time[health.name]
                        cooldown_remaining = REPAIR_COOLDOWN - (datetime.now() - last_repair).total_seconds()
                        logger.info(f"Skipping repair (cooldown: {int(cooldown_remaining)}s remaining)")
                
            except Exception as e:
                logger.error(f"Error during health check/repair: {e}", exc_info=True)
        
        logger.info("Health check cycle complete")
        logger.info("=" * 60)
    
    def print_repair_summary(self):
        """Print a summary of recent repair actions."""
        if not self.repair_history:
            logger.info("No repairs performed yet")
            return
        
        recent = [a for a in self.repair_history if (datetime.now() - a.timestamp) < timedelta(hours=24)]
        
        if recent:
            logger.info(f"\n{'='*60}")
            logger.info(f"Repair Summary (Last 24 hours): {len(recent)} actions")
            logger.info(f"{'='*60}")
            
            for action in recent[-10:]:  # Show last 10
                status = "[OK]" if action.success else "[FAIL]"
                logger.info(
                    f"{status} {action.timestamp.strftime('%H:%M:%S')} | "
                    f"{action.service} | {action.action} | {action.details[:50]}"
                )
    
    def run(self):
        """Main daemon loop."""
        logger.info("Auto-Repair Daemon starting...")
        logger.info(f"Check interval: {CHECK_INTERVAL}s")
        logger.info(f"Repair cooldown: {REPAIR_COOLDOWN}s")
        logger.info(f"Monitoring nodes: Turing={TURING_IP}, Hopper={HOPPER_IP}, Lovelace={LOVELACE_IP}")
        
        try:
            while True:
                try:
                    self.perform_health_check_and_repair()
                except Exception as e:
                    logger.error(f"Error in health check cycle: {e}", exc_info=True)
                
                # Print summary every 6 hours
                if len(self.repair_history) > 0 and len(self.repair_history) % 72 == 0:
                    self.print_repair_summary()
                
                logger.info(f"Sleeping for {CHECK_INTERVAL}s until next check...")
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Auto-Repair Daemon shutting down...")
            self.print_repair_summary()


def main():
    """Entry point."""
    # Load environment variables from .env if present
    env_file = os.path.join(os.path.dirname(__file__), "..", "turing_gateway", ".env")
    if os.path.exists(env_file):
        logger.info(f"Loading environment from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    daemon = AutoRepairDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
