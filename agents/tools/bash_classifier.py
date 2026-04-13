"""
Bash Classifier — Rule-based safety classification for shell commands.

Classifies commands into risk levels:
  - SAFE:      Read-only, informational commands
  - CAUTION:   Commands that modify state but are generally recoverable
  - DANGEROUS: Commands that can cause data loss or system damage
  - BLOCKED:   Commands that match the security policy blocklist

Categories:
  - filesystem: File/directory operations
  - network:    Network operations (curl, wget, ssh, etc.)
  - process:    Process management (kill, pkill, etc.)
  - system:     System-level operations (systemctl, mount, etc.)
  - package:    Package management (apt, pip, npm, etc.)
  - info:       Read-only informational commands

Extends the existing security_policy.json command_blocklist with richer
classification semantics.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("BashClassifier")


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGEROUS = "DANGEROUS"
    BLOCKED = "BLOCKED"


class CommandCategory(str, Enum):
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    PROCESS = "process"
    SYSTEM = "system"
    PACKAGE = "package"
    INFO = "info"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    command: str
    risk_level: RiskLevel
    category: CommandCategory
    reasons: List[str] = field(default_factory=list)
    suggested_alternative: Optional[str] = None

    def __str__(self) -> str:
        reasons_str = "; ".join(self.reasons) if self.reasons else "no specific concerns"
        s = f"[{self.risk_level.value}] ({self.category.value}) {self.command!r} — {reasons_str}"
        if self.suggested_alternative:
            s += f" | Suggested: {self.suggested_alternative}"
        return s

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "risk_level": self.risk_level.value,
            "category": self.category.value,
            "reasons": self.reasons,
            "suggested_alternative": self.suggested_alternative,
        }


# ---------------------------------------------------------------------------
# Classification Rules
# ---------------------------------------------------------------------------

# Safe read-only commands
SAFE_COMMANDS = {
    "ls", "dir", "cat", "head", "tail", "less", "more", "wc", "file",
    "echo", "printf", "date", "cal", "uptime", "whoami", "hostname",
    "pwd", "which", "whereis", "type", "man", "help", "info",
    "env", "printenv", "set", "locale",
    "df", "du", "free", "top", "htop", "ps", "pgrep", "lsof",
    "uname", "arch", "lsb_release", "nproc", "lscpu", "lsmem",
    "ip", "ifconfig", "netstat", "ss", "ping", "traceroute", "dig", "nslookup", "host",
    "git status", "git log", "git diff", "git branch", "git remote", "git show",
    "docker ps", "docker images", "docker logs", "docker inspect",
    "python --version", "python3 --version", "node --version", "npm --version",
    "pip list", "pip show", "pip freeze",
}

# Category detection patterns: (pattern, category, risk, reason)
CATEGORY_RULES: List[tuple[str, CommandCategory, RiskLevel, str]] = [
    # Info / safe reads
    (r"^\s*(ls|dir|cat|head|tail|less|more|wc|file)\b", CommandCategory.INFO, RiskLevel.SAFE, "Read-only file inspection"),
    (r"^\s*(echo|printf|date|cal|uptime|whoami|hostname|pwd)\b", CommandCategory.INFO, RiskLevel.SAFE, "Informational output"),
    (r"^\s*(env|printenv|set|locale)\b", CommandCategory.INFO, RiskLevel.SAFE, "Environment inspection"),
    (r"^\s*(df|du|free|top|htop|ps|pgrep|lsof|nproc)\b", CommandCategory.INFO, RiskLevel.SAFE, "System monitoring"),
    (r"^\s*(uname|arch|lsb_release|lscpu|lsmem)\b", CommandCategory.INFO, RiskLevel.SAFE, "Hardware/OS info"),
    (r"^\s*(ip|ifconfig|netstat|ss)\b", CommandCategory.INFO, RiskLevel.SAFE, "Network inspection"),
    (r"^\s*(ping|traceroute|dig|nslookup|host)\b", CommandCategory.NETWORK, RiskLevel.SAFE, "Network diagnostics"),
    (r"^\s*git\s+(status|log|diff|branch|remote|show|tag)\b", CommandCategory.INFO, RiskLevel.SAFE, "Git read-only"),

    # Filesystem writes — CAUTION
    (r"^\s*(mkdir|touch|cp)\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Creates/copies files"),
    (r"^\s*mv\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Moves/renames files"),
    (r"^\s*chmod\b(?!.*\s+777)", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Changes file permissions"),
    (r"^\s*chown\b(?!.*\s+root)", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Changes file ownership"),
    (r"^\s*ln\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Creates symlinks"),
    (r"^\s*tar\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Archive operations"),
    (r"^\s*(zip|unzip|gzip|gunzip)\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Compression operations"),

    # Git writes — CAUTION
    (r"^\s*git\s+(add|commit|stash)\b", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Git state modification"),
    (r"^\s*git\s+(push|pull|merge|rebase|reset|checkout)\b", CommandCategory.FILESYSTEM, RiskLevel.DANGEROUS, "Git history-altering operation"),

    # Filesystem destructive — DANGEROUS
    (r"^\s*rm\b(?!.*\s+-[rRf])", CommandCategory.FILESYSTEM, RiskLevel.CAUTION, "Removes files (non-recursive)"),
    (r"^\s*rm\s+-[rRf]+", CommandCategory.FILESYSTEM, RiskLevel.BLOCKED, "Recursive/forced deletion"),
    (r">\s+/etc/", CommandCategory.FILESYSTEM, RiskLevel.BLOCKED, "Writes to /etc"),

    # Network — CAUTION/DANGEROUS
    (r"^\s*curl\b(?!.*\|\s*sh)", CommandCategory.NETWORK, RiskLevel.CAUTION, "HTTP request"),
    (r"^\s*wget\b", CommandCategory.NETWORK, RiskLevel.CAUTION, "File download"),
    (r"curl\s+.*\|\s*sh", CommandCategory.NETWORK, RiskLevel.BLOCKED, "Pipe-to-shell execution"),
    (r"^\s*ssh\b", CommandCategory.NETWORK, RiskLevel.CAUTION, "SSH connection"),
    (r"^\s*scp\b", CommandCategory.NETWORK, RiskLevel.CAUTION, "Secure copy"),
    (r"^\s*nc\s+-e", CommandCategory.NETWORK, RiskLevel.BLOCKED, "Netcat reverse shell"),

    # Process management — CAUTION/DANGEROUS
    (r"^\s*(kill|pkill|killall)\b", CommandCategory.PROCESS, RiskLevel.DANGEROUS, "Process termination"),
    (r"^\s*nohup\b", CommandCategory.PROCESS, RiskLevel.CAUTION, "Background process"),

    # System — DANGEROUS
    (r"^\s*systemctl\s+(start|stop|restart|enable|disable)\b", CommandCategory.SYSTEM, RiskLevel.DANGEROUS, "Service management"),
    (r"^\s*systemctl\s+(status|list-units)\b", CommandCategory.SYSTEM, RiskLevel.SAFE, "Service inspection"),
    (r"^\s*(mount|umount)\b", CommandCategory.SYSTEM, RiskLevel.DANGEROUS, "Filesystem mount"),
    (r"^\s*mkfs\b", CommandCategory.SYSTEM, RiskLevel.BLOCKED, "Disk formatting"),
    (r"^\s*dd\s+if=", CommandCategory.SYSTEM, RiskLevel.BLOCKED, "Direct disk write"),
    (r"^\s*(reboot|shutdown|poweroff|init\s+[0-6])\b", CommandCategory.SYSTEM, RiskLevel.BLOCKED, "System power control"),
    (r"^\s*chmod\s+777\b", CommandCategory.SYSTEM, RiskLevel.BLOCKED, "Overpermissive chmod"),
    (r"^\s*chown\s+root\b", CommandCategory.SYSTEM, RiskLevel.BLOCKED, "Ownership to root"),

    # Package management — CAUTION
    (r"^\s*(apt|apt-get|dnf|yum)\s+(install|update|upgrade)\b", CommandCategory.PACKAGE, RiskLevel.CAUTION, "Package installation"),
    (r"^\s*(apt|apt-get|dnf|yum)\s+remove\b", CommandCategory.PACKAGE, RiskLevel.DANGEROUS, "Package removal"),
    (r"^\s*pip\s+install\b", CommandCategory.PACKAGE, RiskLevel.CAUTION, "Python package install"),
    (r"^\s*pip\s+uninstall\b", CommandCategory.PACKAGE, RiskLevel.CAUTION, "Python package removal"),
    (r"^\s*npm\s+install\b", CommandCategory.PACKAGE, RiskLevel.CAUTION, "Node package install"),
    (r"^\s*npm\s+uninstall\b", CommandCategory.PACKAGE, RiskLevel.CAUTION, "Node package removal"),

    # Docker — CAUTION/DANGEROUS
    (r"^\s*docker\s+(ps|images|logs|inspect|stats)\b", CommandCategory.INFO, RiskLevel.SAFE, "Docker inspection"),
    (r"^\s*docker\s+(run|exec|build|pull)\b", CommandCategory.SYSTEM, RiskLevel.CAUTION, "Docker execution"),
    (r"^\s*docker\s+(rm|rmi|prune|stop|kill)\b", CommandCategory.SYSTEM, RiskLevel.DANGEROUS, "Docker destructive"),
    (r"^\s*docker-compose\s+(up|down|restart)\b", CommandCategory.SYSTEM, RiskLevel.CAUTION, "Compose lifecycle"),
]

# Additional blocklist from security_policy.json (loaded at init)
_POLICY_BLOCKLIST: List[str] = []


def _load_policy_blocklist() -> List[str]:
    """Load command blocklist from security_policy.json."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    policy_path = os.path.join(base_dir, "security_policy.json")
    try:
        with open(policy_path, "r") as f:
            policy = json.load(f)
        return policy.get("command_blocklist", [])
    except Exception as e:
        logger.warning(f"[BashClassifier] Could not load security_policy.json: {e}")
        return []


def _ensure_policy_loaded():
    global _POLICY_BLOCKLIST
    if not _POLICY_BLOCKLIST:
        _POLICY_BLOCKLIST = _load_policy_blocklist()


# ---------------------------------------------------------------------------
# Primary API
# ---------------------------------------------------------------------------

def classify_command(command: str) -> ClassificationResult:
    """Classify a bash command for safety.

    Returns a ClassificationResult with risk_level, category, and reasons.
    """
    _ensure_policy_loaded()

    command = command.strip()
    if not command:
        return ClassificationResult(
            command=command,
            risk_level=RiskLevel.SAFE,
            category=CommandCategory.UNKNOWN,
            reasons=["Empty command"],
        )

    reasons: List[str] = []
    worst_risk = RiskLevel.SAFE
    detected_category = CommandCategory.UNKNOWN
    suggested_alt: Optional[str] = None

    # 1. Check security policy blocklist first
    for pattern in _POLICY_BLOCKLIST:
        if re.search(pattern, command):
            return ClassificationResult(
                command=command,
                risk_level=RiskLevel.BLOCKED,
                category=CommandCategory.UNKNOWN,
                reasons=[f"Matches security policy blocklist: {pattern}"],
            )

    # 2. Apply category rules (first match per category wins)
    for pattern, category, risk, reason in CATEGORY_RULES:
        if re.search(pattern, command, re.IGNORECASE):
            reasons.append(reason)
            detected_category = category
            if _risk_ordinal(risk) > _risk_ordinal(worst_risk):
                worst_risk = risk
            break  # First matching rule determines category + base risk

    # 3. Additional risk escalation heuristics
    # Pipe chains increase risk
    if "|" in command:
        pipe_count = command.count("|")
        if pipe_count >= 3:
            reasons.append(f"Complex pipe chain ({pipe_count} pipes)")
            if _risk_ordinal(worst_risk) < _risk_ordinal(RiskLevel.CAUTION):
                worst_risk = RiskLevel.CAUTION

    # Subshell execution
    if "$(" in command or "`" in command:
        reasons.append("Contains command substitution")
        if _risk_ordinal(worst_risk) < _risk_ordinal(RiskLevel.CAUTION):
            worst_risk = RiskLevel.CAUTION

    # Redirect to sensitive paths
    if re.search(r">\s*/dev/", command):
        reasons.append("Redirects to /dev/*")
        worst_risk = RiskLevel.DANGEROUS

    # Eval / exec
    if re.search(r"\beval\b|\bexec\b", command):
        reasons.append("Uses eval/exec — dynamic command execution")
        worst_risk = RiskLevel.DANGEROUS

    # sudo escalation
    if re.search(r"^\s*sudo\b", command):
        reasons.append("Elevated privileges via sudo")
        if _risk_ordinal(worst_risk) < _risk_ordinal(RiskLevel.DANGEROUS):
            worst_risk = RiskLevel.DANGEROUS

    # If no rule matched, it's unknown
    if not reasons:
        reasons.append("Unrecognized command — manual review recommended")
        worst_risk = RiskLevel.CAUTION

    return ClassificationResult(
        command=command,
        risk_level=worst_risk,
        category=detected_category,
        reasons=reasons,
        suggested_alternative=suggested_alt,
    )


def is_safe(command: str) -> bool:
    """Quick check: is the command SAFE risk level?"""
    return classify_command(command).risk_level == RiskLevel.SAFE


def is_blocked(command: str) -> bool:
    """Quick check: is the command BLOCKED?"""
    return classify_command(command).risk_level == RiskLevel.BLOCKED


def _risk_ordinal(risk: RiskLevel) -> int:
    return {RiskLevel.SAFE: 0, RiskLevel.CAUTION: 1, RiskLevel.DANGEROUS: 2, RiskLevel.BLOCKED: 3}[risk]
