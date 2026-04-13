"""
Centralized Network Configuration for the Agentic Hive.

All IP addresses and derived connection strings are loaded from
the project-root `network.env` file. This module is the ONLY place
Python agents should read network topology from.

Usage:
    from config import CONTROL_NODE_IP, AGNO_DB_URL, LANGFUSE_HOST
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate and load network.env
# ---------------------------------------------------------------------------
# network.env lives at the repo root.  In Docker the repo is mounted at
# /workspace, and agents live at /app/agents.  We try both locations.

_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "network.env",   # repo-relative
    Path("/workspace/network.env"),                            # Docker mount
]

def _load_network_env():
    """Parse network.env into os.environ (won't overwrite existing vars)."""
    for candidate in _CANDIDATES:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        # setdefault: real env vars always win
                        os.environ.setdefault(key.strip(), value.strip())
            return
    # If network.env doesn't exist, rely on environment variables already set

_load_network_env()

# ---------------------------------------------------------------------------
# Node IPs
# ---------------------------------------------------------------------------
HOME_ASSISTANT_IP = os.getenv("HOME_ASSISTANT_IP", "192.168.2.100")
EXECUTION_NODE_IP  = os.getenv("EXECUTION_NODE_IP", os.getenv("JUSTIN_PC_IP", "192.168.2.101"))
CONTROL_NODE_IP    = os.getenv("CONTROL_NODE_IP",    "192.168.2.102")
GATEWAY_NODE_IP    = os.getenv("GATEWAY_NODE_IP",  os.getenv("R730_IP", "192.168.2.103"))
IDRAC_IP           = os.getenv("IDRAC_IP",           "192.168.2.104")

# ---------------------------------------------------------------------------
# Derived Connection Strings
# ---------------------------------------------------------------------------
AGNO_DB_URL          = os.getenv("AGNO_DB_URL",          f"postgresql://agno:agno_password@{CONTROL_NODE_IP}:5432/agno_memory")
LANGFUSE_HOST        = os.getenv("LANGFUSE_HOST",        f"http://{CONTROL_NODE_IP}:3000")
MEMPALACE_URL        = os.getenv("MEMPALACE_URL",        f"http://{CONTROL_NODE_IP}:8200")
HOME_ASSISTANT_URL   = os.getenv("HOME_ASSISTANT_URL",   f"http://{HOME_ASSISTANT_IP}:8123")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", f"http://{GATEWAY_NODE_IP}:11434")
OLLAMA_HOST          = os.getenv("OLLAMA_HOST",          "http://localhost:11434")
ROUTER_MODEL         = os.getenv("ROUTER_MODEL",         "nemotron-mini")
ARCHITECT_MODEL      = os.getenv("ARCHITECT_MODEL",      "qwen2.5-coder:14b-instruct-q4_k_m")
COORDINATOR_MODEL    = os.getenv("COORDINATOR_MODEL",    "qwen3:14b")
LIBRARIAN_MODEL      = os.getenv("LIBRARIAN_MODEL",      "llama3.2:3b")

# ---------------------------------------------------------------------------
# ExpertiseTemplate Database (swarm schema in langfuse DB)
# ---------------------------------------------------------------------------
TEMPLATE_DB_URL      = os.getenv("TEMPLATE_DB_URL",      f"postgresql://langfuse:langfuse@{CONTROL_NODE_IP}:5432/langfuse")

# ---------------------------------------------------------------------------
# Training Pipeline Configuration
# ---------------------------------------------------------------------------
TRAINING_OUTPUT_DIR          = os.getenv("TRAINING_OUTPUT_DIR",          "/workspace/training_output")
TRAINING_DATASET_DIR         = os.getenv("TRAINING_DATASET_DIR",         "/workspace/training_data")
TRAINING_BASE_SOLVER         = os.getenv("TRAINING_BASE_SOLVER",         "Qwen/Qwen2.5-Coder-7B-Instruct")
TRAINING_BASE_ROUTER         = os.getenv("TRAINING_BASE_ROUTER",         "nvidia/Nemotron-Mini-4B-Instruct")
TRAINING_LORA_RANK           = int(os.getenv("TRAINING_LORA_RANK",       "16"))
TRAINING_LORA_ALPHA          = int(os.getenv("TRAINING_LORA_ALPHA",      "32"))
TRAINING_BATCH_SIZE          = int(os.getenv("TRAINING_BATCH_SIZE",      "1"))
TRAINING_GRADIENT_ACCUMULATION = int(os.getenv("TRAINING_GRADIENT_ACCUMULATION", "8"))

# ---------------------------------------------------------------------------
# Context Window Management
# ---------------------------------------------------------------------------
CONTEXT_WINDOWS: dict[str, int] = {
    "qwen2.5-coder:14b": 32768,
    "qwen2.5-coder:14b-instruct-q4_k_m": 32768,
    "qwen3.5:9b": 32768,
    "qwen3:14b": 40960,
    "nemotron-mini": 4096,
    "llama3.2:3b": 8192,
    "default": 8192,
}
COMPACT_AUTO_THRESHOLD = 0.95

# ---------------------------------------------------------------------------
# LLM Provider Configuration (multi-provider support)
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")          # "ollama" | "anthropic"
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL    = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6-20250514")
MCP_BRIDGE_ENABLED = os.getenv("MCP_BRIDGE_ENABLED", "false")
MCP_SERVER_NAME    = os.getenv("MCP_SERVER_NAME", "home-ai-lab")
MCP_BASE_URL       = os.getenv("MCP_BASE_URL", f"http://{CONTROL_NODE_IP}:8000")

# ---------------------------------------------------------------------------
# Skills & Tools Configuration (Phase 4)
# ---------------------------------------------------------------------------
SKILLS_ENABLED         = os.getenv("SKILLS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
BROWSER_MAX_CONTENT_BYTES = int(os.getenv("BROWSER_MAX_CONTENT_BYTES", str(512 * 1024)))
BROWSER_TIMEOUT        = int(os.getenv("BROWSER_TIMEOUT", "15"))
BROWSER_DOMAIN_ALLOWLIST = os.getenv("BROWSER_DOMAIN_ALLOWLIST", "")
BASH_CLASSIFIER_ENABLED = os.getenv("BASH_CLASSIFIER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# ---------------------------------------------------------------------------
# Remote & Multi-Node Configuration (Phase 5)
# ---------------------------------------------------------------------------
SSH_DEFAULT_TIMEOUT    = int(os.getenv("SSH_DEFAULT_TIMEOUT", "60"))
SSH_CONNECT_TIMEOUT    = int(os.getenv("SSH_CONNECT_TIMEOUT", "10"))
SSH_KEY_PATH           = os.getenv("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SSH_USER               = os.getenv("SSH_USER", "misterobots")
BRIDGE_ENABLED         = os.getenv("BRIDGE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
BRIDGE_TIMEOUT         = int(os.getenv("BRIDGE_TIMEOUT", "30"))
DAEMON_MAX_WORKERS     = int(os.getenv("DAEMON_MAX_WORKERS", "20"))
DAEMON_ENABLED         = os.getenv("DAEMON_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TRIGGER_ENABLED        = os.getenv("TRIGGER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TRIGGER_TICK_INTERVAL  = int(os.getenv("TRIGGER_TICK_INTERVAL", "15"))
WORKFLOW_STATE_DIR     = os.getenv("WORKFLOW_STATE_DIR", "/workspace/workflow_state")

# Admin-only models — only users with security_level >= L3_ADMIN may select these
ADMIN_ONLY_MODELS: set[str] = {
    "claude-opus-4-20250514",
    "claude-sonnet-4-6-20250514",
    "claude-haiku-3-5-20241022",
}

TRAINING_LEARNING_RATE       = float(os.getenv("TRAINING_LEARNING_RATE", "5e-6"))
TRAINING_NUM_EPOCHS          = int(os.getenv("TRAINING_NUM_EPOCHS",      "3"))
TRAINING_MAX_SEQ_LEN         = int(os.getenv("TRAINING_MAX_SEQ_LEN",    "4096"))
TRAINING_WINDOW_START        = int(os.getenv("TRAINING_WINDOW_START",    "2"))   # hour
TRAINING_WINDOW_END          = int(os.getenv("TRAINING_WINDOW_END",      "6"))   # hour
