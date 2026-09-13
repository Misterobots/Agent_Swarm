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
# GPU peer lock server — Lovelace hosts this on its agent_runtime port (8001).
# Turing sets GPU_LOCK_HOST=http://192.168.2.101:8001 in its docker env.
# GPU_LOCK_SECRET should be the same value on all nodes (optional but recommended).
GPU_LOCK_HOST        = os.getenv("GPU_LOCK_HOST",        f"http://{LOVELACE_IP}:8008")
# ---------------------------------------------------------------------------
# Model Specialization Map
#
# Hardware — Lovelace: 2× RTX 5060 Ti (16 GB each, 32 GB combined)
#            Turing:   RTX 3070 Ti (8 GB)
#
# Role → default model:
#   COORDINATOR  gemma4:e4b        (9 GB)  — resident planning/research model
#                                    holistic reasoning & steering questions
#   CODER        qwen3-coder:30b   (18 GB) — Qwen3 Coder; best code generation
#   ARCHITECT    qwen3-coder:30b   (18 GB) — code-solver default for the MarsRL
#                                    chat path (handlers/architect.py resolves
#                                    coder→ARCHITECT_MODEL). NOT the swarm
#                                    architect — see SWARM_ARCHITECT_MODEL below.
#   DEVOPS       qwen3-coder:30b   (18 GB) — infra scripts, Dockerfiles, YAML
#   PRIMARY /    qwen3.6:27b       (17 GB) — general Qwen3.6; conversation,
#   LIBRARIAN /                              research, documentation, analysis
#   RESEARCHER / gemma4:e4b        — installed Gemma reasoning model for
#   ANALYST                                  fast inference for parallel research
#                                            fan-out; falls back to PRIMARY.
#   ROUTER       qwen3:8b          (5 GB)  — lightweight; LLM router fallback
#   VERIFIER     qwen3:14b         (9 GB)  — verification pass; balanced quality
#
# All defaults can be overridden per-user via Team Builder or env vars.
# ---------------------------------------------------------------------------
PRIMARY_MODEL        = os.getenv("PRIMARY_MODEL",        "qwen3.6:27b")
ROUTER_MODEL         = os.getenv("ROUTER_MODEL",         "qwen3:8b")
COORDINATOR_MODEL    = os.getenv("COORDINATOR_MODEL",    "gemma4:e4b")
CODER_MODEL          = os.getenv("CODER_MODEL",          "qwen3-coder:30b")
ARCHITECT_MODEL      = os.getenv("ARCHITECT_MODEL",      "qwen3-coder:30b")
DEVOPS_MODEL         = os.getenv("DEVOPS_MODEL",         "qwen3-coder:30b")
LIBRARIAN_MODEL      = os.getenv("LIBRARIAN_MODEL",      PRIMARY_MODEL)
RESEARCHER_MODEL     = os.getenv("RESEARCHER_MODEL",     "gemma4:e4b")
ANALYST_MODEL        = os.getenv("ANALYST_MODEL",        "gemma4:e4b")
VERIFIER_MODEL       = os.getenv("VERIFIER_MODEL",       "qwen3:14b")

# Swarm architect runs a *reasoning* model (design/planning), decoupled from
# ARCHITECT_MODEL which is the MarsRL code-solver default.  Defaults to the
# coordinator's model so the planning phase (coordinator + architect) shares a
# single resident model load — no GPU swap between decompose and design.
SWARM_ARCHITECT_MODEL = os.getenv("SWARM_ARCHITECT_MODEL", "qwen3:14b")

# ---------------------------------------------------------------------------
# ExpertiseTemplate Database (swarm schema in langfuse DB)
# ---------------------------------------------------------------------------
TEMPLATE_DB_URL      = os.getenv("TEMPLATE_DB_URL",      f"postgresql://langfuse:langfuse@{HOPPER_IP}:5432/langfuse")


# ---------------------------------------------------------------------------
# Swarm Planning & Solving Limits
# ---------------------------------------------------------------------------
# These control the maximum iterations and/or time (in seconds) for planning and solving phases.
# Set to 0 for unlimited. Both can be set; the phase will stop at whichever comes first.
PLANNING_MAX_ITER = int(os.getenv("PLANNING_MAX_ITER", "0"))  # 0 = unlimited
PLANNING_MAX_TIME = int(os.getenv("PLANNING_MAX_TIME", "0"))  # seconds, 0 = unlimited
SOLVING_MAX_ITER = int(os.getenv("SOLVING_MAX_ITER", "2"))    # default 2 for MarsRL
SOLVING_MAX_TIME = int(os.getenv("SOLVING_MAX_TIME", "0"))    # seconds, 0 = unlimited

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
# TRAINING_NUM_EPOCHS, TRAINING_LEARNING_RATE, TRAINING_MAX_SEQ_LEN defined below (near TRAINING_WINDOW_*)

# Maps archetype name → grpo_trainer config.
# "target" must match grpo_trainer.py --target choices: "solver" | "router".
ARCHETYPE_TRAINING_CONFIGS: dict[str, dict] = {
    "coder": {
        "base_model": TRAINING_BASE_SOLVER,
        "target": "solver",
        "description": "Code quality and reasoning specialist (Qwen2.5-Coder)",
    },
    "coordinator": {
        "base_model": TRAINING_BASE_SOLVER,
        "target": "solver",
        "description": "Multi-agent coordination and planning",
    },
    "researcher": {
        "base_model": TRAINING_BASE_SOLVER,
        "target": "solver",
        "description": "Deep research and document analysis",
    },
    "router": {
        "base_model": TRAINING_BASE_ROUTER,
        "target": "router",
        "description": "Semantic routing and intent classification (Nemotron-Mini)",
    },
}

# ---------------------------------------------------------------------------
# Context Window Management
# ---------------------------------------------------------------------------
# MEASURED 2026-09-13 on Lovelace (2x RTX 5060 Ti).  The shared Ollama lane was returned to
# count:all, so the pool is 29.7 GiB across both cards instead of one card's ~14.5 GiB.
# Each value is ~80% of the model's measured ceiling in the "dense" zone (~28.3 GiB: Friday's
# brain and voice-engine evicted, STT resident).  Method: load at num_ctx 8192 and 65536, read
# /api/ps size, take the delta -> exact KV bytes/token and fixed overhead.
#
#   model              weights   KV/token   measured ceiling
#   qwen3-coder:30b     17.28G     58 KiB    ~195K
#   qwen3.6:27b         16.22G     53 KiB    ~132K
#   gemma4:31b          18.50G     61 KiB    ~108K
#   deepseek-r1:32b     18.49G    340 KiB     ~32K  (KV quantization is not engaging for it)
#   qwen3:14b            8.64G     52 KiB    model-native 40960 binds before VRAM does
#   qwen3:8b             4.87G     44 KiB    model-native 40960 binds before VRAM does
#
# A model at or above gpu_queue.LARGE_MODEL_BYTES (15 GiB) only fits these windows in the
# "dense" zone, so its request_lock call site MUST pass model= — otherwise the swarm asks for a
# window the normal lane (~17.9 GiB with the voice stack resident) cannot hold, and spills to CPU.
#
# Keep in sync with CODE_GATEWAY_NUM_CTX_MAP in execution_plane/docker-compose.yml — the same
# table for OpenAI-speaking clients, which cannot send num_ctx themselves.
CONTEXT_WINDOWS: dict[str, int] = {
    # Gemma
    # Was 4096: "a 32K KV cache terminates the llama runner" — true when this lane had ONE 16 GB
    # card and the 18.5 GiB of weights already overflowed it.  With both cards, measured live at
    # num_ctx 65536: 25.69 GiB, 100% on GPU.  The 4K workaround is obsolete.
    "gemma4:31b": 81920,
    "gemma4:26b": 32768,        # not measured
    # Qwen3 family
    "qwen3-coder:30b": 163840,
    "qwen3.8:27b": 122880,      # capped by llama.cpp #27756's ~129,864-token EOS cliff, NOT VRAM
    "qwen3.6:27b": 98304,
    "qwen3.5:9b": 16384,        # not measured
    "qwen3:14b": 40960,         # model-native
    "qwen3:8b": 40960,          # model-native
    # Qwen2.5 family
    "qwen2.5-coder:14b": 16384,
    "qwen2.5-coder:14b-instruct-q4_k_m": 16384,
    "qwen2.5-coder:7b": 8192,
    # Reasoning / other
    "phi4-reasoning:14b": 16384,
    "deepseek-r1:32b": 32768,   # measured ceiling: 28.49 GiB at 32K, spills by 48K
    # Hugging Face catalog entries (native/deployment context advertised by
    # their model cards; they require a compatible remote serving backend).
    "IFM/K2-Horizon-32B": 524288,
    "IFM/K2-Horizon-7B": 524288,
    "inclusionAI/Ling-3.0-tiny": 262144,
    "minicpm-v:latest": 8192,
    "llama3.2:3b": 8192,
    "default": 8192,
}
COMPACT_AUTO_THRESHOLD = 0.95


def get_ollama_options(model_name: str, **extra) -> dict:
    """Return Ollama API options with the per-model context window from CONTEXT_WINDOWS."""
    ctx = CONTEXT_WINDOWS.get(model_name, CONTEXT_WINDOWS["default"])
    return {"num_ctx": ctx, **extra}

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
