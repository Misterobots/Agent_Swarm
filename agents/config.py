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
JUSTIN_PC_IP      = os.getenv("JUSTIN_PC_IP",      "192.168.2.101")
CONTROL_NODE_IP    = os.getenv("CONTROL_NODE_IP",    "192.168.2.102")
R730_IP            = os.getenv("R730_IP",            "192.168.2.103")
IDRAC_IP           = os.getenv("IDRAC_IP",           "192.168.2.104")

# ---------------------------------------------------------------------------
# Derived Connection Strings
# ---------------------------------------------------------------------------
AGNO_DB_URL          = os.getenv("AGNO_DB_URL",          f"postgresql://agno:agno_password@{CONTROL_NODE_IP}:5432/agno_memory")
LANGFUSE_HOST        = os.getenv("LANGFUSE_HOST",        f"http://{CONTROL_NODE_IP}:3000")
HOME_ASSISTANT_URL   = os.getenv("HOME_ASSISTANT_URL",   f"http://{HOME_ASSISTANT_IP}:8123")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", f"http://{R730_IP}:11434")
OLLAMA_HOST          = os.getenv("OLLAMA_HOST",          "http://localhost:11434")
ROUTER_MODEL         = os.getenv("ROUTER_MODEL",         "nemotron-mini")
ARCHITECT_MODEL      = os.getenv("ARCHITECT_MODEL",      "qwen2.5-coder:14b-instruct-q4_k_m")
LIBRARIAN_MODEL      = os.getenv("LIBRARIAN_MODEL",      "llama3.2:3b")

# ---------------------------------------------------------------------------
# ExpertiseTemplate Database (swarm schema in langfuse DB)
# ---------------------------------------------------------------------------
TEMPLATE_DB_URL      = os.getenv("TEMPLATE_DB_URL",      f"postgresql://langfuse:langfuse_password@{CONTROL_NODE_IP}:5432/langfuse")

# ---------------------------------------------------------------------------
# Training defaults
# ---------------------------------------------------------------------------
TRAINING_OUTPUT_DIR           = os.getenv("TRAINING_OUTPUT_DIR",           "/workspace/training_output")
TRAINING_BASE_SOLVER          = os.getenv("TRAINING_BASE_SOLVER",          "nvidia/Nemotron-Mini-4B-Instruct")
TRAINING_LORA_RANK            = int(os.getenv("TRAINING_LORA_RANK",        "16"))
TRAINING_LORA_ALPHA           = int(os.getenv("TRAINING_LORA_ALPHA",       "32"))
TRAINING_BATCH_SIZE           = int(os.getenv("TRAINING_BATCH_SIZE",       "1"))
TRAINING_GRADIENT_ACCUMULATION = int(os.getenv("TRAINING_GRADIENT_ACCUMULATION", "8"))
TRAINING_LEARNING_RATE        = float(os.getenv("TRAINING_LEARNING_RATE",  "5e-6"))
TRAINING_NUM_EPOCHS           = int(os.getenv("TRAINING_NUM_EPOCHS",       "3"))
TRAINING_MAX_SEQ_LEN          = int(os.getenv("TRAINING_MAX_SEQ_LEN",     "2048"))
