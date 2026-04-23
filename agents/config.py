"""
Centralized Network Configuration for the Agentic Hive.

All IP addresses and derived connection strings are loaded from
the project-root `network.env` file. This module is the ONLY place
Python agents should read network topology from.

Usage:
    from config import HOPPER_IP, AGNO_DB_URL, LANGFUSE_HOST
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
LOVELACE_IP  = os.getenv("LOVELACE_IP", os.getenv("LOVELACE_IP", "192.168.2.101"))
HOPPER_IP    = os.getenv("HOPPER_IP",    "192.168.2.102")
TURING_IP    = os.getenv("TURING_IP",  os.getenv("TURING_IP", "192.168.2.103"))
BMO_IP       = os.getenv("BMO_IP", "192.168.2.106")
IDRAC_IP     = os.getenv("IDRAC_IP",   "192.168.2.104")

# ---------------------------------------------------------------------------
# Derived Connection Strings
# ---------------------------------------------------------------------------
AGNO_DB_URL          = os.getenv("AGNO_DB_URL",          f"postgresql://agno:agno_password@{HOPPER_IP}:5432/agno_memory")
LANGFUSE_HOST        = os.getenv("LANGFUSE_HOST",        f"http://{HOPPER_IP}:3000")
MEMPALACE_URL        = os.getenv("MEMPALACE_URL",        f"http://{HOPPER_IP}:8200")
HOME_ASSISTANT_URL   = os.getenv("HOME_ASSISTANT_URL",   f"http://{HOME_ASSISTANT_IP}:8123")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", f"http://{TURING_IP}:11434")
OLLAMA_HOST          = os.getenv("OLLAMA_HOST",          "http://localhost:11434")
# ---------------------------------------------------------------------------
# Model Consolidation (TTFT Optimization)
# Primary model: qwen3:14b — handles code, conversation, coordination,
# research, documentation. Pinned in VRAM (keep_alive=-1) on GPU 0.
# BMO voice: qwen2.5:3b — lightweight, on-demand.
# Safety: llama-guard-3:8b — async on Turing.
# Vision: moondream — on-demand.
# ---------------------------------------------------------------------------
PRIMARY_MODEL        = os.getenv("PRIMARY_MODEL",        "qwen3:14b")
ROUTER_MODEL         = os.getenv("ROUTER_MODEL",         PRIMARY_MODEL)
ARCHITECT_MODEL      = os.getenv("ARCHITECT_MODEL",      PRIMARY_MODEL)
COORDINATOR_MODEL    = os.getenv("COORDINATOR_MODEL",    PRIMARY_MODEL)
LIBRARIAN_MODEL      = os.getenv("LIBRARIAN_MODEL",      PRIMARY_MODEL)

# ---------------------------------------------------------------------------
# ExpertiseTemplate Database (swarm schema in langfuse DB)
# ---------------------------------------------------------------------------
TEMPLATE_DB_URL      = os.getenv("TEMPLATE_DB_URL",      f"postgresql://langfuse:langfuse@{HOPPER_IP}:5432/langfuse")

# ---------------------------------------------------------------------------
# Training Pipeline Configuration
# ---------------------------------------------------------------------------
TRAINING_OUTPUT_DIR          = os.getenv("TRAINING_OUTPUT_DIR",          "/workspace/training_output")
TRAINING_DATASET_DIR         = os.getenv("TRAINING_DATASET_DIR",         "/workspace/training_data")
TRAINING_BASE_SOLVER         = os.getenv("TRAINING_BASE_SOLVER",         "Qwen/Qwen2.5-Coder-7B-Instruct")
TRAINING_BASE_ROUTER         = os.getenv("TRAINING_BASE_ROUTER",         "nvidia/Nemotron-Mini-4B-Instruct")
TRAINING_LORA_RANK           = int(os.getenv("TRAINING_LORA_RANK",       "64"))
TRAINING_LORA_ALPHA          = int(os.getenv("TRAINING_LORA_ALPHA",      "128"))
TRAINING_BATCH_SIZE          = int(os.getenv("TRAINING_BATCH_SIZE",      "2"))
TRAINING_GRADIENT_ACCUMULATION = int(os.getenv("TRAINING_GRADIENT_ACCUMULATION", "4"))

# ---------------------------------------------------------------------------
# Context Window Management
# ---------------------------------------------------------------------------
CONTEXT_WINDOWS: dict[str, int] = {
    "qwen3:14b": 40960,
    "qwen2.5-coder:14b": 32768,
    "qwen2.5-coder:14b-instruct-q4_k_m": 32768,
    "qwen3.5:9b": 32768,
    "nemotron-orchestrator:8b": 32768,
    "nemotron-mini": 4096,
    "qwen2.5:3b": 8192,
    "llama3.2:3b": 8192,
    "default": 8192,
}
COMPACT_AUTO_THRESHOLD = 0.95

# ---------------------------------------------------------------------------
# LLM Provider Configuration (multi-provider BYOK support)
# Local Ollama models are free for all users. External providers
# (Anthropic, GitHub Models, Gemini) require per-user connected keys.
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")          # default local provider
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL    = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6-20250514")
MCP_BRIDGE_ENABLED = os.getenv("MCP_BRIDGE_ENABLED", "false")
MCP_SERVER_NAME    = os.getenv("MCP_SERVER_NAME", "home-ai-lab")
MCP_BASE_URL       = os.getenv("MCP_BASE_URL", f"http://{HOPPER_IP}:8000")

# ---------------------------------------------------------------------------
# Skills & Tools Configuration (Phase 4)
# ---------------------------------------------------------------------------
SKILLS_ENABLED         = os.getenv("SKILLS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
BROWSER_MAX_CONTENT_BYTES = int(os.getenv("BROWSER_MAX_CONTENT_BYTES", str(512 * 1024)))
BROWSER_TIMEOUT        = int(os.getenv("BROWSER_TIMEOUT", "15"))
BROWSER_DOMAIN_ALLOWLIST = os.getenv("BROWSER_DOMAIN_ALLOWLIST", "")
BASH_CLASSIFIER_ENABLED = os.getenv("BASH_CLASSIFIER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# ---------------------------------------------------------------------------
# GitHub OAuth — Device Flow (Phase 1C)
# ---------------------------------------------------------------------------
GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
# 32-byte Fernet key (base64url). Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY   = os.getenv("TOKEN_ENCRYPTION_KEY", "")

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

# ---------------------------------------------------------------------------
# OpenClaude gRPC Configuration (Phase 6)
# ---------------------------------------------------------------------------
GRPC_SERVER_HOST       = os.getenv("GRPC_SERVER_HOST", TURING_IP)
GRPC_SERVER_PORT       = int(os.getenv("GRPC_SERVER_PORT", "50051"))
GRPC_GATEWAY_ENABLED   = os.getenv("GRPC_GATEWAY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
GRPC_TIMEOUT           = int(os.getenv("GRPC_TIMEOUT", "120"))
GRPC_MAX_WORKERS       = int(os.getenv("GRPC_MAX_WORKERS", "4"))
GRPC_AUTH_ENABLED      = os.getenv("GRPC_AUTH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
GRPC_AUTH_CACHE_TTL    = int(os.getenv("GRPC_AUTH_CACHE_TTL", "300"))

# Subscription-required models — users must connect their own API key to use these.
# Admin fallback: if ANTHROPIC_API_KEY env var is set, admins can still use it.
ADMIN_ONLY_MODELS: set[str] = {
    "claude-opus-4-20250514",
    "claude-sonnet-4-6-20250514",
    "claude-haiku-3-5-20241022",
}

# Models that any user can access if they have a connected provider key
SUBSCRIPTION_MODELS: dict[str, str] = {
    # model_id -> provider name (matches provider_keys.PROVIDERS)
    "claude-opus-4-20250514":      "anthropic",
    "claude-sonnet-4-6-20250514":   "anthropic",
    "claude-haiku-3-5-20241022":    "anthropic",
    "gemini-2.0-flash":             "google",
    "gemini-2.0-pro":               "google",
}

TRAINING_LEARNING_RATE       = float(os.getenv("TRAINING_LEARNING_RATE", "2e-5"))
TRAINING_NUM_EPOCHS          = int(os.getenv("TRAINING_NUM_EPOCHS",      "3"))
TRAINING_MAX_SEQ_LEN         = int(os.getenv("TRAINING_MAX_SEQ_LEN",    "8192"))
TRAINING_WINDOW_START        = int(os.getenv("TRAINING_WINDOW_START",    "2"))   # hour
TRAINING_WINDOW_END          = int(os.getenv("TRAINING_WINDOW_END",      "6"))   # hour
