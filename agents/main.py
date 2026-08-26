
import logging
import sys
import os
import json
import uuid
import time
import functools
import threading
import hashlib
import hmac
import ipaddress
import socket
import base64
import re
from urllib.parse import urlparse

# Root logger configuration — most modules in this codebase call
# logging.getLogger(__name__) directly rather than logger_setup.setup_logger(),
# which means (with no handler ever attached to the root logger) their INFO-level
# logs never reached container stdout at all: Python's logging module falls back
# to a WARNING-only "handler of last resort" for any logger with no handler in
# its chain. That silently swallowed things like "table ready"/"provisioned"/
# "checked out" confirmations from every *_store.py and dev_files/dev_projects
# module — real operational signal, not noise, and exactly what's needed to
# keep sight of what a request actually did instead of just its final response.
# force=True guarantees this applies regardless of what uvicorn's own default
# logging config already touched on root. setup_logger()-based loggers
# (logger_setup.py) set propagate=False specifically so they don't ALSO bubble
# up here and print twice.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

# Ensure agents dir is in path
if "/app/agents" not in sys.path:
    sys.path.append("/app/agents")
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
import uvicorn
from contextlib import asynccontextmanager
from metrics import AGENT_STATE
from prometheus_client import make_asgi_app
from logger_setup import setup_logger
from mcp.server import get_mcp_server
from mcp.schema import MCPRpcRequest
from mcp.transport import ok_response, error_response, internal_error

logger = setup_logger("Main")
from dispatcher import dispatcher, Event, EventType
from church import handle_task_event
# Top-level logging removed to prevent startup crashes

# --- API Models ---
class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    task: str
    source: str = "api"

class TaskResponse(BaseModel): # Added TaskResponse
    model_config = ConfigDict(extra="allow")
    status: str
    result: str

# --- Security ---
from security import SpiffeAuthMiddleware, get_spiffe_auth, require_spiffe_id, SpiffeJWTBearer
from security.authorization_middleware import AuthorizationMiddleware
from fastapi import Depends

# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Startup
        print("DEBUG: Entering lifespan...")
        logger.info("Initializing Swarm Engine...")
        
        # 0. Initialize SPIFFE Auth (if available) - DISABLED for stability check
        # try:
        #     print("DEBUG: Checking SPIFFE Auth...")
        #     auth = get_spiffe_auth()
        #     if auth.is_available:
        #         # Attempt to fetch SVID to warm up cache and verify connection
        #         print("DEBUG: SPIFFE Available, fetching ID...")
        #         identity = auth.get_spiffe_id()
        #         if identity:
        #             logger.info(f"🔑 SPIFFE Identity Verified: {identity}")
        #         else:
        #             logger.warning("⚠️ SPIFFE Identity NOT available (Check agent socket)")
        #     else:
        #         logger.info("ℹ️ SPIFFE Auth not enabled (py-spiffe not found)")
        # except Exception as e:
        #     logger.error(f"Failed to initialize SPIFFE auth: {e}")
        #     print(f"DEBUG: SPIFFE Error: {e}")

        # 1. Register Routers to Dispatcher
        logger.info("Registering Swarm Event Handlers...")
        dispatcher.register(EventType.USER_TASK, handle_task_event)

        # 2. Reset Metrics
        print("DEBUG: Resetting Metrics...")
        AGENT_STATE.labels(agent_name="Router").set(1)
        AGENT_STATE.labels(agent_name="Security").set(1)
        AGENT_STATE.labels(agent_name="Architect").set(1)

        # 3. Initialize ExpertiseTemplate Registry + Async Updater
        template_updater = None
        try:
            from expertise.template_registry import get_template_registry
            from expertise.async_template_updater import AsyncTemplateUpdater

            print("DEBUG: Initializing Template Registry...")
            registry = get_template_registry()
            if registry.initialize():
                logger.info("ExpertiseTemplate registry initialized (schema + seed data)")
                template_updater = AsyncTemplateUpdater(registry)
                await template_updater.start()
                logger.info("Async Template Updater started")
            else:
                logger.warning("Template registry DB unavailable — running without templates")
        except ImportError as e:
            logger.warning(f"Template system not available: {e}")
        except Exception as e:
            logger.warning(f"Template system init failed (non-fatal): {e}")

        # 4. Initialize Skill Registry (Phase 4 — Superpowers skills)
        try:
            from skill_loader import initialize_skills
            skill_count = initialize_skills()
            logger.info(f"Skill Registry initialized: {skill_count} skills loaded")
        except ImportError as e:
            logger.warning(f"Skill loader not available: {e}")
        except Exception as e:
            logger.warning(f"Skill loader init failed (non-fatal): {e}")

        # 5. Initialize Daemon Registry (Phase 5 — persistent background workers)
        daemon_reg = None
        try:
            from daemon_registry import get_daemon_registry
            daemon_reg = get_daemon_registry()
            logger.info(f"Daemon Registry initialized: {daemon_reg.count()} workers")
        except ImportError as e:
            logger.warning(f"Daemon registry not available: {e}")
        except Exception as e:
            logger.warning(f"Daemon registry init failed (non-fatal): {e}")

        # 6. Initialize Trigger Scheduler (Phase 5 — cron/interval/once triggers)
        trigger_sched = None
        try:
            from trigger_scheduler import get_trigger_scheduler
            trigger_sched = get_trigger_scheduler()
            trigger_sched.start()
            trigger_sched.load_persisted()
            logger.info(f"Trigger Scheduler started: {trigger_sched.count()} triggers")
        except ImportError as e:
            logger.warning(f"Trigger scheduler not available: {e}")
        except Exception as e:
            logger.warning(f"Trigger scheduler init failed (non-fatal): {e}")

        # 7. Initialize Conversation Store (cross-device sync)
        try:
            from conversation_store import init_table as _init_conv_table
            _init_conv_table()
        except Exception as e:
            logger.warning(f"Conversation store init failed (non-fatal): {e}")

        # 7b. Initialize Goals Store
        try:
            from goals import init_tables as _init_goals_tables
            _init_goals_tables()
        except Exception as e:
            logger.warning(f"Goals store init failed (non-fatal): {e}")

        # 7e. Initialize User Prefs Store (cross-device onboarding/prefs sync)
        try:
            from prefs_store import init_table as _init_prefs_table
            _init_prefs_table()
        except Exception as e:
            logger.warning(f"Prefs store init failed (non-fatal): {e}")

        # 7c. Initialize Dev Sessions Store
        try:
            from dev_sessions import store as _dev_sessions_store
            _dev_sessions_store.init_tables()
        except Exception as e:
            logger.warning(f"Dev sessions store init failed (non-fatal): {e}")

        # Durable neutral-history checkpoints for interrupted DevHarness turns.
        try:
            from dev_harness import checkpoints as _dev_checkpoint_store
            _dev_checkpoint_store.init_table()
        except Exception as e:
            logger.warning(f"Dev checkpoint store init failed (non-fatal): {e}")

        # 7d. Initialize Dev Projects Store
        try:
            from dev_projects import store as _dev_projects_store
            _dev_projects_store.init_tables()
        except Exception as e:
            logger.warning(f"Dev projects store init failed (non-fatal): {e}")

        # 7f. Initialize Swarm Run Store (mobile task-board history)
        try:
            from swarm_run_store import init_table as _init_swarm_run_table
            _init_swarm_run_table()
        except Exception as e:
            logger.warning(f"Swarm run store init failed (non-fatal): {e}")

        # 7g. Initialize Swarm Run Repo Store (New Task composer repo/branch metadata)
        try:
            from swarm_run_repo_store import init_table as _init_swarm_run_repo_table
            _init_swarm_run_repo_table()
        except Exception as e:
            logger.warning(f"Swarm run repo store init failed (non-fatal): {e}")

        # 7g3. Initialize Swarm Run Local Project Store (blank/local project metadata)
        try:
            from swarm_run_local_store import init_table as _init_swarm_run_local_table
            _init_swarm_run_local_table()
        except Exception as e:
            logger.warning(f"Swarm run local store init failed (non-fatal): {e}")

        # 7g2. Initialize GitHub Push Audit Store (gated push/PR trail)
        try:
            from github_push_audit_store import init_table as _init_push_audit_table
            _init_push_audit_table()
        except Exception as e:
            logger.warning(f"GitHub push audit store init failed (non-fatal): {e}")

        # 7g4. Initialize GitHub Publish Audit Store (blank project -> new repo trail)
        try:
            from github_publish_audit_store import init_table as _init_publish_audit_table
            _init_publish_audit_table()
        except Exception as e:
            logger.warning(f"GitHub publish audit store init failed (non-fatal): {e}")

        # 7h. Task queue reconciliation — a crash mid-task otherwise leaves a
        # phantom 'running'/'queued' row AND (once the workspace lock is in
        # play) a Redis lock nothing will ever release, silently freezing all
        # future task creation. Mark stale rows failed BEFORE clearing the
        # lock/queue so the two stay consistent.
        try:
            import swarm_run_store as _swarm_run_store_reconcile
            from coordination import task_queue as _task_queue_reconcile
            _fixed = _swarm_run_store_reconcile.reconcile_stale_runs()
            _task_queue_reconcile.clear_all()
            if _fixed:
                logger.warning(f"Task queue reconciliation: marked {_fixed} stale run(s) failed on startup.")
        except Exception as e:
            logger.warning(f"Task queue reconciliation failed (non-fatal): {e}")

        # 7h2. Session container orphan sweep — must run AFTER the reconciliation
        # above (session_sandbox.cleanup_orphans()'s own docstring documents this
        # ordering): by the time this runs, reconcile_stale_runs()/clear_all()
        # have already ensured nothing legitimately holds a session container
        # from before this restart, so every dev-task-* container found here is
        # a leak from an unclean shutdown, not a live run.
        try:
            from coordination.session_sandbox import cleanup_orphans as _cleanup_session_orphans
            _reaped = _cleanup_session_orphans()
            if _reaped:
                logger.warning(f"Session container reconciliation: reaped {_reaped} orphaned container(s) on startup.")
        except Exception as e:
            logger.warning(f"Session container orphan sweep failed (non-fatal): {e}")

        # 7g. Initialize GitHub Push Tokens Store (fine-grained PAT for repo-write
        # access, Phase C of the Codex-task-composer plan — structurally separate
        # from github_oauth.py's swarm.github_oauth_tokens table)
        try:
            from github_push_tokens import init_table as _init_github_push_table
            _init_github_push_table()
        except Exception as e:
            logger.warning(f"GitHub push tokens store init failed (non-fatal): {e}")

        # 8. Clean up orphaned training runs (status='running' but server restarted)
        try:
            from config import TEMPLATE_DB_URL
            import psycopg2
            conn = psycopg2.connect(TEMPLATE_DB_URL)
            cur = conn.cursor()
            cur.execute(
                "UPDATE swarm.training_runs SET status='failed', "
                "error_message='Interrupted by server restart', completed_at=NOW() "
                "WHERE status='running'"
            )
            cleaned = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            if cleaned:
                logger.warning(f"Cleaned up {cleaned} orphaned training run(s) stuck in 'running' state")
        except Exception as e:
            logger.warning(f"Training run cleanup failed (non-fatal): {e}")

        # 9. Start training-run watchdog (reconciles silent asyncio task crashes)
        import asyncio as _asyncio
        training_watchdog = _asyncio.create_task(_training_watchdog_loop())

        # 10. Warm-pin protected (voice) models so the lane is instant from boot.
        #     No-op unless WARM_PIN_PROTECTED_MODELS is enabled; runs off-thread so
        #     a cold multi-GB load never delays startup (see utils/gpu_queue.py).
        try:
            import threading as _threading
            from utils.gpu_queue import warm_pin_protected_models as _warm_pin
            _threading.Thread(target=_warm_pin, name="warm-pin-protected",
                              daemon=True).start()
            logger.info("Warm-pin startup hook scheduled (no-op unless WARM_PIN_PROTECTED_MODELS set)")
        except Exception as e:
            logger.warning(f"Warm-pin startup hook skipped (non-fatal): {e}")

        print("DEBUG: Startup Complete. Yielding...")
        logger.info("Swarm Engine Online. Waiting for events...")
        yield
        # Shutdown
        training_watchdog.cancel()
        logger.info("Shutting down Swarm Engine...")
        if trigger_sched:
            trigger_sched.stop()
            logger.info("Trigger Scheduler stopped")
        if daemon_reg:
            daemon_reg.stop_all()
            logger.info("Daemon Registry stopped")
        if template_updater:
            await template_updater.stop()
            logger.info("Async Template Updater stopped")
    except Exception:
        import traceback
        traceback.print_exc()
        raise

# --- App Definition ---
app = FastAPI(lifespan=lifespan, title="Home AI Lab Swarm API")
mcp_server = get_mcp_server()

# Goals router
try:
    from goals.routes import router as goals_router
    app.include_router(goals_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Goals router not loaded: {_e}")

# Dev workspace routers (F1 sessions, F2 files, F3 projects)
try:
    from dev_sessions.routes import router as dev_sessions_router
    app.include_router(dev_sessions_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Dev sessions router not loaded: {_e}")

try:
    from dev_files.routes import router as dev_files_router
    app.include_router(dev_files_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Dev files router not loaded: {_e}")

try:
    from dev_projects.routes import router as dev_projects_router
    app.include_router(dev_projects_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Dev projects router not loaded: {_e}")


# Remote pairing — WebSocket relay for cross-instance session sharing
try:
    from pairing.routes import router as pairing_router
    app.include_router(pairing_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Pairing router not loaded: {_e}")

# GPU peer lock router — Lovelace hosts this so all agent_runtimes (including
# remote ones on Turing etc.) can acquire the cross-host GPU mutex even when
# Redis is unavailable.  Mounted at /internal/gpu-lock/*.
try:
    from api.gpu_lock import router as gpu_lock_router
    app.include_router(gpu_lock_router)
    import logging as _logging
    _logging.getLogger("main").info("GPU peer lock server active at /internal/gpu-lock/")
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"GPU lock router not loaded: {_e}")

# Mission Control operational mutations. Keep host-affecting actions isolated
# from this application entry point; read-only fleet endpoints remain inline
# temporarily and will move with the broader Ops API aggregation work.
try:
    from ops.routes import router as ops_router
    app.include_router(ops_router)
except Exception as _e:
    import logging as _logging
    _logging.getLogger("main").warning(f"Ops router not loaded: {_e}")

# Staged rollout: parse mode logs policy mismatches without blocking,
# soft/hard modes enforce endpoint-class policy in AuthorizationMiddleware.
app.add_middleware(AuthorizationMiddleware)

# --- Global Exception Handler (To capture crashes before uvicorn swallows them) ---
from fastapi import Request
from fastapi.responses import JSONResponse, Response, HTMLResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ GLOBAL CRASH: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Swarm Error", "details": str(exc)},
    )

# Mount Prometheus Metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Friday external image attachments are intentionally served on a separate route from
# /delivered_artifacts.  Traefik exposes only this route, and each request must carry
# an HMAC signature plus an expiry.  A dedicated secret may be configured later; the
# HA token is a safe shared fallback because both trusted runtime containers already
# receive it and it is never sent to the client.
_FRIDAY_IMAGE_SIGNING_SECRET = os.getenv(
    "FRIDAY_IMAGE_SIGNING_SECRET", os.getenv("HOME_ASSISTANT_TOKEN", "")
)


@app.get("/v1/public-artifacts/{filename}")
async def serve_signed_public_artifact(filename: str, exp: int, sig: str):
    """Serve one generated artifact only when its signed delivery URL is valid."""
    if not _FRIDAY_IMAGE_SIGNING_SECRET:
        raise HTTPException(status_code=503, detail="Image delivery signing is not configured")
    if exp < int(time.time()):
        raise HTTPException(status_code=403, detail="Image delivery link has expired")
    if exp > int(time.time()) + 7 * 24 * 60 * 60:
        raise HTTPException(status_code=403, detail="Invalid image delivery expiry")
    if os.path.basename(filename) != filename:
        raise HTTPException(status_code=400, detail="Invalid artifact name")

    payload = f"{filename}:{exp}".encode("utf-8")
    expected = hmac.new(
        _FRIDAY_IMAGE_SIGNING_SECRET.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=403, detail="Invalid image delivery signature")

    artifact_dir = "/workspace/delivered_artifacts"
    full_path = os.path.normpath(os.path.join(artifact_dir, filename))
    if not full_path.startswith(f"{artifact_dir}{os.sep}") or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(full_path, media_type="image/png")

# Mount Delivered Artifacts for remote downloading (Satellite)
if os.path.exists("/workspace/delivered_artifacts"):
    app.mount("/delivered_artifacts", StaticFiles(directory="/workspace/delivered_artifacts"), name="artifacts")

# Mount User Projects — agents write web apps here; served at /projects/<name>/
os.makedirs("/workspace/user_projects", exist_ok=True)
app.mount("/projects", StaticFiles(directory="/workspace/user_projects", html=True), name="projects")

# Mount CAD artifacts (.scad + .stl) for browser download
_CAD_ARTIFACTS_DIR = os.getenv("CAD_OUTPUT_DIR", "/workspace/cad_artifacts")
os.makedirs(_CAD_ARTIFACTS_DIR, exist_ok=True)
app.mount("/files/cad", StaticFiles(directory=_CAD_ARTIFACTS_DIR), name="cad_artifacts")

# --- Direct File Serving for Voice Samples (StaticFiles mount was unreliable) ---
from fastapi.responses import FileResponse
from fastapi import HTTPException
from pathlib import Path

@app.get("/voice_samples/{filename}")
async def serve_voice_sample(filename: str):
    """Serve pre-recorded BMO voice samples to the satellite."""
    sample_dir = Path("/app/agents/bmo_voice/voice_samples").resolve()

    try:
        requested = (sample_dir / filename).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Block path traversal outside of sample directory.
    if sample_dir not in requested.parents and requested != sample_dir:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Direct match
    if requested.is_file():
        return FileResponse(str(requested), media_type="audio/wav")
    
    # Case-insensitive fallback
    if sample_dir.is_dir():
        for f in os.listdir(sample_dir):
            if f.lower() == filename.lower():
                candidate = (sample_dir / f).resolve()
                if sample_dir in candidate.parents and candidate.is_file():
                    return FileResponse(str(candidate), media_type="audio/wav")
    
    print(f"⚠️ Voice sample not found: {requested} (dir exists: {sample_dir.is_dir()})")
    raise HTTPException(status_code=404, detail=f"Sample not found: {filename}")

# --- Endpoints ---
@app.get("/")
async def root():
    import subprocess
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd="/workspace", stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        git_sha = "unknown"

    redis_mode = "connected"
    try:
        if dispatcher.redis_available and hasattr(dispatcher.redis, 'ping'):
            dispatcher.redis.ping()
        else:
            redis_mode = "in-memory"
    except Exception:
        redis_mode = "unavailable"

    return {
        "status": "online",
        "system": "Home AI Lab Swarm",
        "redis": redis_mode,
        "commit": git_sha,
    }

@app.get("/api/v1/identity")
async def get_my_identity(request: Request, auth_claims: dict = Depends(SpiffeJWTBearer(auto_error=False))):
    """
    Identity self-inspection endpoint.
    Returns caller identity from Authentik headers (preferred), JWT-ACE token, or anonymous.
    Public so the UI can call it without a token.
    """
    auth = get_spiffe_auth()
    my_id = auth.get_spiffe_id()

    # Priority 1: Authentik forward-auth headers (set by Traefik)
    authentik_user = request.headers.get("X-authentik-username")
    if authentik_user:
        groups = _authentik_groups(request)
        is_admin = _request_is_admin(request)
        caller = {
            "username": authentik_user,
            "email": request.headers.get("X-authentik-email", ""),
            "name": request.headers.get("X-authentik-name", authentik_user),
            "uid": request.headers.get("X-authentik-uid", ""),
            "groups": groups,
            "security_level": "L3_ADMIN" if is_admin else "L2_USER",
            "auth_source": "authentik",
        }
        return {
            "my_spiffe_id": my_id,
            "caller_identity": caller,
            "spiffe_available": auth.is_available,
        }

    # Priority 2: Try the middleware-attached agent card (JWT-ACE)
    agent_card = getattr(request.state, "agent_card", None)

    # If middleware skipped auth (public endpoint), try manual token extraction
    if not agent_card:
        bearer = request.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            try:
                from security.token_issuer import get_token_validator
                validator = get_token_validator()
                agent_card = validator.validate_token(bearer[7:])
            except Exception:
                pass  # Invalid token — fall through to anonymous

    if agent_card:
        caller = {
            "agent_name": getattr(agent_card, "agent_name", "unknown"),
            "security_level": getattr(agent_card, "security_level", "L1_PUBLIC"),
            "activated_capabilities": getattr(agent_card, "activated_capabilities", []),
            "user_id": getattr(agent_card, "user_id", None),
        }
    elif auth_claims:
        caller = auth_claims
    else:
        caller = "anonymous"

    return {
        "my_spiffe_id": my_id,
        "caller_identity": caller,
        "spiffe_available": auth.is_available
    }

@app.post("/api/v1/task")
async def submit_task(request: TaskRequest):
    """
    Async Task Submission.
    Returns immediately with 202 Accepted.
    Task runs in background thread via Dispatcher.
    """
    logger.info(f"Received task from {request.source}")
    
    event = Event(
        type=EventType.USER_TASK,
        payload={"task": request.task},
        source=request.source
    )
    
    # The dispatcher handles threading/concurrency
    dispatcher.emit(event)
    
    return {"status": "accepted", "message": "Task queued for execution"}

# --- OpenAI-Compatible Chat Endpoint (For VS Code Extensions) ---
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str
    content: str

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: List[ChatMessage]
    model: str = "default"
    stream: bool = False
    session_id: Optional[str] = None  # conversation ID for multi-turn history
    memory_enabled: bool = False      # opt-in cross-session memory recall
    user_id: Optional[str] = None     # preferred owner key for user-scoped storage
    skill: Optional[str] = None       # routing hint: general|code|devops|data|creative|research|explain
    style: Optional[str] = None       # response style: default|concise|explanatory|formal|technical|casual
    research_mode: bool = False       # deep multi-step reasoning mode
    ultraplan_mode: bool = False       # plan-only mode: decompose task, no execution
    ultrathink_mode: bool = False      # deep reasoning with visible chain-of-thought
    attachments: Optional[List[dict]] = None  # file attachments [{name, mimeType, data, size}]
    dev_mode: bool = False            # Phase 2: enable AI agentic coding tools in dev workspace
    dev_permission_mode: Optional[str] = None  # dev harness gate: default|plan|acceptEdits|bypass (plan = read-only until approved)
    dev_resume: bool = False          # resume a checkpoint after explicitly replaying interrupted tools
    grounding_web: bool = False       # inject live web search results (requires governance permission)
    grounding_docs: bool = False      # inject knowledge-base document chunks (requires governance permission)
    grounding_file: bool = False      # inject local workspace file content (requires governance permission)
    already_steered: bool = False     # skip nuance gate (True when user has already answered a steering question)
    swarm_mode: bool = False          # route through Lamport multi-agent coordinator
    design_mode: bool = False         # route through Open Design Studio
    workshop_mode: bool = False       # route through Product Workshop (Grill Me)
    solving_max_iter: Optional[int] = None  # MarsRL max iterations (0 = unlimited, overrides config)
    solving_max_time: Optional[int] = None  # MarsRL max time in seconds (0 = unlimited, overrides config)
    # Developer-mode granular per-agent budgets. Each overrides the overall budget for that agent.
    solving_solver_n_drafts: Optional[int] = None       # Best-of-N solver drafts (1–10; UI exposes 1–3)
    solving_solver_max_time: Optional[int] = None       # Per-call solver wall-clock (seconds)
    solving_verifier_n_runs: Optional[int] = None       # N-way verifier consensus (1 = single pass)
    solving_verifier_max_time: Optional[int] = None     # Per-call verifier wall-clock (seconds)
    solving_corrector_n_passes: Optional[int] = None    # N sequential corrector passes per round
    solving_corrector_max_time: Optional[int] = None    # Per-call corrector wall-clock (seconds)
    current_project_id: Optional[str] = None            # Active dev project ID (injects .memex/notes.md into system prompt)
    active_file: Optional[str] = None                   # Currently open file path in the dev workspace editor


# Model choice is available to authenticated users, but the submitted value
# must still be one of the curated, user-facing models.  The browser picker is
# a convenience only; API callers can otherwise submit arbitrary model IDs.
_DEFAULT_CHAT_MODEL = os.getenv("MEMEX_DEFAULT_MODEL", "qwen3:14b")
_DEFAULT_MODEL_ALIASES = {"", "default", "memex-default", "Home-AI-Swarm", "swarm-standard"}


def _authentik_groups(request: Request) -> list[str]:
    """Normalize Authentik group headers from Traefik/Next/Electron hops."""
    return [group.strip() for group in re.split(r"[|,]", request.headers.get("X-authentik-groups", "")) if group.strip()]


def _request_is_admin(request: Request) -> bool:
    """Only an Authentik group assertion grants model-administration access."""
    return any("admin" in group.lower() for group in _authentik_groups(request))


def _apply_model_policy(request: ChatRequest, http_request: Request) -> None:
    """Resolve aliases and reject internal, unknown, or unavailable model IDs."""
    requested = (request.model or "").strip()
    if requested in _DEFAULT_MODEL_ALIASES:
        request.model = _DEFAULT_CHAT_MODEL
        return

    from model_registry import get_model
    spec = get_model(requested)
    if not spec or not spec.roles:
        raise HTTPException(status_code=400, detail="Selected model is not available for chat.")
    if not spec.available:
        raise HTTPException(
            status_code=503,
            detail=f"{requested} is not available on this runtime.",
        )
    request.model = requested


# ---------------------------------------------------------------------------
# MemPalace HTTP extraction — calls the FastAPI service for durable storage
# ---------------------------------------------------------------------------
import httpx as _httpx

_MEMPALACE_API_URL = os.getenv("MEMPALACE_API_URL", "http://192.168.2.102:8200")


async def _mempalace_extract_http(conversation: str, owner_id: str | None = None) -> int:
    """POST conversation text to the MemPalace /v1/extract endpoint.

    Returns the number of memories extracted, or 0 on failure.
    """
    payload: dict = {"conversation": conversation}
    if owner_id:
        payload["owner_id"] = owner_id
    try:
        async with _httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{_MEMPALACE_API_URL}/v1/extract",
                json=payload,
            )
        if resp.status_code == 200:
            memories = resp.json()
            return len(memories) if isinstance(memories, list) else 0
        else:
            logger.warning(
                "[MemPalace] Extraction returned %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return 0
    except Exception as exc:
        logger.warning("[MemPalace] HTTP extraction failed: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Phase 2 — Tool approval store (in-process, single asyncio event loop)
# ---------------------------------------------------------------------------

import asyncio as _asyncio

# Per-call approval state: call_id -> asyncio.Event (set when decision arrives)
_approval_events: dict[str, _asyncio.Event] = {}
# Per-call decision: call_id -> True (approved) | False (denied)
_approval_decisions: dict[str, bool] = {}
# Per-call owner binding.  Approval IDs are opaque, but they are still
# untrusted input: only the owner that received the pending call may decide it.
_approval_owners: dict[str, str] = {}

# Per-user auto-approve rules:
#   key = uid, value = set of tool names (or "all") that are auto-approved
# "session" scope lives here (cleared on restart).
# "workspace" scope is persisted to a simple JSON file on the same volume.
_session_auto_approve: dict[str, set[str]] = {}

_WORKSPACE_AUTO_APPROVE_FILE = "/workspace/.hivecode_auto_approve.json"


def _load_workspace_auto_approve() -> dict[str, list[str]]:
    """Load workspace-scoped auto-approve rules from the JSON file, if present."""
    try:
        import json as _json
        with open(_WORKSPACE_AUTO_APPROVE_FILE, "r") as f:
            return _json.load(f)
    except Exception:
        return {}


def _save_workspace_auto_approve(data: dict[str, list[str]]) -> None:
    try:
        import json as _json
        with open(_WORKSPACE_AUTO_APPROVE_FILE, "w") as f:
            _json.dump(data, f)
    except Exception as e:
        logger.warning(f"[dev_mode] Could not save workspace auto-approve rules: {e}")


def _is_auto_approved(uid: str, tool_name: str) -> bool:
    """Return True if the tool is auto-approved for this user (session or workspace)."""
    session_rules = _session_auto_approve.get(uid, set())
    if "all" in session_rules or tool_name in session_rules:
        return True
    workspace_rules = _load_workspace_auto_approve()
    ws_set = set(workspace_rules.get(uid, []))
    return "all" in ws_set or tool_name in ws_set


def _apply_auto_approve(uid: str, tool_name: str, scope: str) -> None:
    """Persist an auto-approve rule for a user+tool at the given scope."""
    if scope == "session":
        _session_auto_approve.setdefault(uid, set()).add(tool_name)
    elif scope == "workspace":
        data = _load_workspace_auto_approve()
        existing = set(data.get(uid, []))
        existing.add(tool_name)
        data[uid] = list(existing)
        _save_workspace_auto_approve(data)
    elif scope == "all_session":
        _session_auto_approve.setdefault(uid, set()).add("all")
    elif scope == "all_workspace":
        data = _load_workspace_auto_approve()
        existing = set(data.get(uid, []))
        existing.add("all")
        data[uid] = list(existing)
        _save_workspace_auto_approve(data)


# ---------------------------------------------------------------------------
# Dev tool definitions — canonical list lives in dev_harness/tool_defs.py so
# coordination/devharness_worker.py can import it without pulling in FastAPI.
# ---------------------------------------------------------------------------

from dev_harness.tool_defs import DEV_TOOL_DEFINITIONS  # noqa: E402


def _resolve_owner_id(payload_user_id: Optional[str], request: Request) -> Optional[str]:
    """Resolve a stable owner identifier from request payload or authenticated context."""
    # DEBUG: Log all headers to understand what's being received
    auth_headers = {
        "X-authentik-uid": request.headers.get("X-authentik-uid", ""),
        "X-authentik-username": request.headers.get("X-authentik-username", ""),
        "X-authentik-email": request.headers.get("X-authentik-email", ""),
    }
    logger.debug(f"[owner_id] payload={payload_user_id}, headers={auth_headers}")
    
    # Prefer the authenticated, human-readable username as the CANONICAL owner id.
    # This MUST precede payload_user_id: the UI sometimes sends an opaque uid hash as
    # the payload user_id, which previously won here and fragmented a single user's
    # memories across {username, uid-hash} silos — so recall (owner-scoped) only ever
    # saw one silo. Username-first keeps every authenticated request for a given user
    # on one owner_id. (owner_id canonicalization, 2026-07.)
    authentik_user = request.headers.get("X-authentik-username", "").strip()
    if authentik_user:
        logger.info(f"[owner_id] Resolved from X-authentik-username: {authentik_user}")
        return authentik_user

    if payload_user_id:
        logger.info(f"[owner_id] Resolved from payload: {payload_user_id}")
        return payload_user_id

    authentik_uid = request.headers.get("X-authentik-uid", "").strip()
    if authentik_uid:
        logger.info(f"[owner_id] Resolved from X-authentik-uid: {authentik_uid}")
        return authentik_uid

    agent_card = getattr(request.state, "agent_card", None)
    if not agent_card:
        return None

    explicit_user_id = getattr(agent_card, "user_id", None)
    if explicit_user_id:
        return explicit_user_id

    metadata = getattr(agent_card, "metadata", {}) or {}
    owner_id = metadata.get("user_id") or metadata.get("owner_id")
    if owner_id:
        return owner_id

    token_profile = getattr(request.state, "token_profile", None)
    if token_profile == "user" and getattr(agent_card, "session_id", None):
        session_owner = f"session:{agent_card.session_id}"
        logger.info(f"[owner_id] Resolved from session: {session_owner}")
        return session_owner

    logger.warning("[owner_id] Could not resolve owner_id - returning None (memories will be stored as 'swarm')")
    return None


# ---------------------------------------------------------------------------
# Phase 2 — Tool approval endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/dev/approve/{call_id}")
async def approve_tool_call(call_id: str, http_request: Request):
    """
    Approve a pending tool call from the AI agent.
    Optional JSON body: {"auto": "none" | "session" | "workspace"}
    """
    try:
        body = await http_request.json()
    except Exception:
        body = {}
    auto_scope = body.get("auto", "none")
    tool_name = body.get("tool_name", "")
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"

    pending_owner = _approval_owners.get(call_id)
    if pending_owner is None:
        raise HTTPException(status_code=404, detail="Approval request not found or expired")
    if pending_owner != uid:
        logger.warning(f"[dev_approve] rejected cross-owner approval call_id={call_id} uid={uid}")
        raise HTTPException(status_code=403, detail="Approval request belongs to another owner")

    if auto_scope != "none" and tool_name:
        _apply_auto_approve(uid, tool_name, auto_scope)

    _approval_decisions[call_id] = True
    _approval_owners.pop(call_id, None)
    event = _approval_events.pop(call_id, None)
    if event:
        event.set()
    logger.info(f"[dev_approve] call_id={call_id} uid={uid} auto={auto_scope} approved")
    return {"ok": True}


@app.post("/api/v1/dev/deny/{call_id}")
async def deny_tool_call(call_id: str, http_request: Request):
    """Deny a pending tool call from the AI agent."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    pending_owner = _approval_owners.get(call_id)
    if pending_owner is None:
        raise HTTPException(status_code=404, detail="Approval request not found or expired")
    if pending_owner != uid:
        logger.warning(f"[dev_approve] rejected cross-owner denial call_id={call_id} uid={uid}")
        raise HTTPException(status_code=403, detail="Approval request belongs to another owner")

    _approval_decisions[call_id] = False
    _approval_owners.pop(call_id, None)
    event = _approval_events.pop(call_id, None)
    if event:
        event.set()
    logger.info(f"[dev_approve] call_id={call_id} uid={uid} denied")
    return {"ok": True}


@app.get("/api/v1/dev/auto-approve")
async def get_auto_approve_rules(http_request: Request):
    """Return the current auto-approve rules for the calling user."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    session_rules = list(_session_auto_approve.get(uid, set()))
    ws_data = _load_workspace_auto_approve()
    workspace_rules = ws_data.get(uid, [])
    return {"session": session_rules, "workspace": workspace_rules}


@app.delete("/api/v1/dev/auto-approve")
async def clear_auto_approve_rules(http_request: Request):
    """Clear all auto-approve rules for the calling user (session + workspace)."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    _session_auto_approve.pop(uid, None)
    ws_data = _load_workspace_auto_approve()
    ws_data.pop(uid, None)
    _save_workspace_auto_approve(ws_data)
    return {"ok": True}


def _checkpoint_public_view(row: dict) -> dict:
    data = row.get("data") or {}
    from dev_harness.replay_policy import public_call
    return {
        "session_id": row.get("session_id"),
        "status": row.get("status"),
        "turn": row.get("turn", 0),
        "updated_at": row.get("updated_at", 0),
        "model": data.get("model"),
        "permission_mode": data.get("permission_mode"),
        "pending_tools": [
            public_call(item) for item in (data.get("pending_tools") or [])
            if isinstance(item, dict)
        ],
        "error": data.get("error", ""),
    }


class DevReplayRequest(BaseModel):
    call_id: str
    confirm: bool = False


class TaskMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    scope: str | None = None
    branch: str | None = None
    prompt: str | None = None


_DEV_REPLAY_LOCKS: dict[str, threading.Lock] = {}
_DEV_REPLAY_LOCKS_GUARD = threading.Lock()


def _serialize_dev_replay(handler):
    """Serialize replay per owner/session so two requests cannot consume one call."""
    @functools.wraps(handler)
    async def wrapped(session_id, body, http_request):
        uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
        key = f"{uid}:{session_id}"
        with _DEV_REPLAY_LOCKS_GUARD:
            lock = _DEV_REPLAY_LOCKS.setdefault(key, threading.Lock())
        await _asyncio.get_running_loop().run_in_executor(None, lock.acquire)
        try:
            return await handler(session_id, body, http_request)
        finally:
            lock.release()


@app.get("/api/v1/dev/checkpoints")
async def list_dev_checkpoints(http_request: Request):
    """List incomplete DevHarness checkpoints for the authenticated owner."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    from dev_harness.checkpoints import list_recovery_required
    return {"checkpoints": [_checkpoint_public_view(row) for row in list_recovery_required(uid)]}


@app.get("/api/v1/dev/checkpoints/{session_id}")
async def get_dev_checkpoint(session_id: str, http_request: Request):
    """Inspect one owner-scoped checkpoint without exposing other owners."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    from dev_harness.checkpoints import get_checkpoint
    row = get_checkpoint(uid, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return _checkpoint_public_view(row)


@app.post("/api/v1/dev/checkpoints/{session_id}/replay")
@_serialize_dev_replay
async def replay_dev_checkpoint_tool(
    session_id: str,
    body: DevReplayRequest,
    http_request: Request,
):
    """Explicitly replay the next owner-approved recorded tool call.

    Calls are dispatched only after owner, confirmation, permission, and exact
    recorded-order checks. Sandbox tools use the container executor, read-only
    MCP tools use the mounted MCP safety stack, and Task calls reconstruct the
    existing subagent adapter with the checkpoint's model and container.
    """
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to replay a tool call")

    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    from dev_harness.checkpoints import get_checkpoint, save_checkpoint

    row = get_checkpoint(uid, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    data = row.get("data") or {}
    for prior in list(data.get("replay_results") or []):
        if prior.get("call_id") == body.call_id:
            return {
                "ok": True,
                "session_id": session_id,
                "call_id": body.call_id,
                "tool_name": prior.get("name"),
                "output": prior.get("output", ""),
                "file_changes": prior.get("file_changes", []),
                "is_error": bool(prior.get("is_error", False)),
                "status": row.get("status"),
                "next_call_id": (data.get("pending_tools") or [{}])[0].get("call_id"),
            }
    if row.get("status") not in {"awaiting_tools", "recovery_required"}:
        raise HTTPException(
            status_code=409,
            detail=f"Checkpoint is not awaiting replay (status={row.get('status')})",
        )

    pending = data.get("pending_tools") or []
    if not pending or not isinstance(pending[0], dict):
        raise HTTPException(status_code=409, detail="Checkpoint has no replayable pending tool")
    call = pending[0]
    from dev_harness.replay_policy import category, validate_next
    policy_ok, policy_reason = validate_next(
        pending=pending,
        call_id=body.call_id,
        owner_id=uid,
        requested_owner_id=uid,
        permission_mode=data.get("permission_mode") or "default",
        is_admin=_request_is_admin(http_request),
        confirm=body.confirm,
    )
    if not policy_ok:
        raise HTTPException(status_code=409, detail=policy_reason)
    if call.get("call_id") != body.call_id:
        raise HTTPException(
            status_code=409,
            detail=f"Replay must proceed in recorded tool-call order; expected call_id={call.get('call_id')}",
        )

    tool_name = call.get("tool_name") or call.get("name")
    args = call.get("args")
    tool_category = category(call)
    if not isinstance(tool_name, str) or not isinstance(args, dict):
        raise HTTPException(
            status_code=409,
            detail=f"Tool {tool_name!r} has an invalid recorded replay payload",
        )

    permission_mode = data.get("permission_mode") or "default"
    if permission_mode == "bypass" and not _request_is_admin(http_request):
        raise HTTPException(status_code=403, detail="Admin authorization is required to replay a bypass-mode tool")
    from dev_harness.permissions import PermissionGate
    allowed, reason = PermissionGate(permission_mode).check(tool_name)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    container_name = data.get("container_name")
    if container_name is not None and not isinstance(container_name, str):
        raise HTTPException(status_code=409, detail="Checkpoint container identity is invalid")
    if container_name and not re.fullmatch(r"(?:dev-task-[A-Za-z0-9_.-]+|dev_sandbox)", container_name):
        raise HTTPException(status_code=409, detail="Checkpoint container identity is not a sandbox container")

    try:
        loop = _asyncio.get_running_loop()
        if tool_category == "sandbox":
            output, file_changes = await loop.run_in_executor(
                None,
                _exec_with_sink,
                tool_name,
                args,
                container_name,
            )
        elif tool_category == "mcp":
            output = await loop.run_in_executor(None, _run_mcp_tool, uid, tool_name, args)
            file_changes = []
        elif tool_category == "task":
            gate = PermissionGate(permission_mode)
            output, emitted = await _run_subagent(
                uid,
                data.get("model") or _DEFAULT_CHAT_MODEL,
                args.get("description", ""),
                args.get("prompt", ""),
                args.get("subagent_type", "general"),
                gate,
                container_name=container_name,
            )
            file_changes = [
                chunk.data for chunk in emitted
                if getattr(chunk, "type", None) == "file_change" and getattr(chunk, "data", None)
            ]
        else:
            raise ValueError(f"Unsupported replay category: {tool_category}")
        is_error = False
    except Exception as exc:
        output = f"Replay failed: {exc}"
        file_changes = []
        is_error = True

    replayed = list(data.get("replay_results") or [])
    replayed.append({
        "call_id": call["call_id"],
        "name": tool_name,
        "output": str(output),
        "is_error": is_error,
        "file_changes": file_changes,
    })
    pending = pending[1:]
    data["pending_tools"] = pending
    data["replay_results"] = replayed

    if pending:
        status = "recovery_required"
    else:
        from dev_harness.history import History, ToolResult
        try:
            restored = History.from_checkpoint(data["history"])
            restored.add_tool_results([
                ToolResult(
                    item["call_id"], item["name"], item["output"], bool(item.get("is_error", False))
                )
                for item in replayed
            ])
            data["history"] = restored.to_checkpoint()
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Checkpoint history cannot be restored: {exc}")
        data.pop("replay_results", None)
        status = "ready_to_resume"

    saved = save_checkpoint(
        uid,
        session_id,
        status=status,
        turn=int(row.get("turn") or 0),
        data=data,
    )
    if not saved:
        raise HTTPException(status_code=503, detail="Replay ran but its result could not be durably recorded")
    return {
        "ok": True,
        "session_id": session_id,
        "call_id": body.call_id,
        "tool_name": tool_name,
        "output": str(output),
        "file_changes": file_changes,
        "is_error": is_error,
        "status": status,
        "next_call_id": pending[0].get("call_id") if pending else None,
    }


@app.get("/v1/models")
async def list_models(request: Request):
    """
    OpenAI-compatible /v1/models.
    Returns local swarm models + any provider models for which the user has
    a connected account (GitHub OAuth token or API key via provider_keys).

    Durability note: adding a new provider to provider_keys.PROVIDERS
    automatically surfaces it here — no edit to this function needed.
    """
    try:
        _ts = int(time.time())
        base_models = [{
            "id": "Home-AI-Swarm", "object": "model", "created": _ts,
            "owned_by": "MarsRL", "label": "Memex default",
            "description": f"Current default: {_DEFAULT_CHAT_MODEL}",
        }]
        # A curated operational catalog is safer than accepting arbitrary
        # Ollama names. This remains independent from role assignments.
        from model_registry import get_user_selectable_models
        for spec in get_user_selectable_models():
            base_models.append({
                "id": spec.name, "object": "model", "created": _ts,
                "owned_by": "MarsRL", "label": spec.name,
                "description": spec.description, "available": spec.available,
            })

        uid = request.headers.get("X-authentik-uid", "").strip()
        if uid:
            # ── GitHub Models (OAuth device flow) ────────────────────────────
            try:
                from github_oauth import get_token
                from providers.github_models_provider import GITHUB_MODELS
                if get_token(uid):
                    for m in GITHUB_MODELS:
                        base_models.append({
                            "id": m["id"],
                            "object": "model",
                            "created": _ts,
                            "owned_by": "github",
                            "label": m.get("label", m["id"]),
                            "context_window": m.get("context"),
                        })
                    logger.info(f"list_models: added {len(GITHUB_MODELS)} GitHub models for uid={uid}")
            except Exception as e:
                logger.warning(f"list_models: GitHub models error: {e}", exc_info=True)

            # ── API-key providers (Anthropic, Google, etc.) ──────────────────
            # Data-driven loop: iterates provider_keys.PROVIDERS so new
            # providers added there appear automatically without touching this code.
            try:
                from provider_keys import get_key, PROVIDERS as _PROVIDERS
                for provider_id, provider_info in _PROVIDERS.items():
                    try:
                        rec = get_key(uid, provider_id)
                        if not rec:
                            continue
                        catalog = provider_info.get("models", [])

                        # NVIDIA: filter to models the user's key is entitled
                        # to call (NVIDIA returns 404 for un-entitled models,
                        # so we ping each one). Cached per user.
                        if provider_id == "nvidia" and catalog:
                            try:
                                from providers.nvidia_entitlement import accessible_models
                                ids = [m["id"] for m in catalog]
                                allowed = accessible_models(uid, ids, rec.get_api_key())
                                catalog = [m for m in catalog if m["id"] in allowed]
                            except Exception as _e:
                                logger.warning(f"list_models: nvidia entitlement check failed: {_e}")

                        added = 0
                        for m in catalog:
                            base_models.append({
                                "id": m["id"],
                                "object": "model",
                                "created": _ts,
                                "owned_by": provider_id,
                                "label": m.get("label", m["id"]),
                                "context_window": m.get("context"),
                            })
                            added += 1
                        logger.info(
                            f"list_models: added {added} {provider_id} models for uid={uid}"
                        )
                    except Exception as _e:
                        logger.warning(
                            f"list_models: error checking {provider_id} key for uid={uid}: {_e}"
                        )
            except Exception as e:
                logger.warning(f"list_models: provider_keys error: {e}", exc_info=True)

        return {"object": "list", "data": base_models}
    except Exception as e:
        logger.error(f"Error in list_models: {e}", exc_info=True)
        raise


@app.get("/v1/models/ollama")
async def list_ollama_models():
    """
    List Ollama models available across all nodes for the Team Builder UI.
    Queries both OLLAMA_HOST (Turing) and SECONDARY_OLLAMA_HOST (Lovelace) so that
    large models stored on Lovelace's 32 GB VRAM appear as available.
    """
    import requests as _requests
    from config import OLLAMA_HOST, SECONDARY_OLLAMA_HOST
    from model_registry import MODELS, get_user_selectable_models

    # Gather pulled model names from all Ollama nodes
    pulled: set[str] = set()
    errors: list[str] = []
    for label, host in [("execution-plane", OLLAMA_HOST), ("control-plane", SECONDARY_OLLAMA_HOST)]:
        try:
            r = _requests.get(f"{host}/api/tags", timeout=3)
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    pulled.add(m.get("name", ""))
        except Exception as e:
            errors.append(f"{label}: {str(e)[:80]}")
            logger.warning(f"[models/ollama] Could not reach {label} ({host}): {e}")

    # Update availability flags — mark available if present on ANY node
    for name, spec in MODELS.items():
        if name in pulled:
            spec.available = True

    selectable = get_user_selectable_models()
    return {
        "models": [m.to_dict() for m in selectable],
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Team Builder API  (role → model configuration per user)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/v1/team-builder/config")
async def team_builder_get_config(request: Request):
    """Load the authenticated user's team builder configuration."""
    uid = request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    from team_builder import get_team_config
    return get_team_config(uid)


@app.post("/v1/team-builder/config")
async def team_builder_save_config(request: Request):
    """Save the authenticated user's team builder configuration."""
    uid = request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        config = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    from team_builder import save_team_config
    try:
        save_team_config(uid, config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "saved", "roles": list(config.keys())}


@app.delete("/v1/team-builder/config")
async def team_builder_delete_config(request: Request):
    """Reset the authenticated user's team builder configuration to defaults."""
    uid = request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    from team_builder import clear_team_config
    deleted = clear_team_config(uid)
    return {"status": "reset", "was_configured": deleted}


# ---------------------------------------------------------------------------
# Dev workspace agentic harness (Phase 0) — provider-neutral coding loop.
# Replaces the bespoke dev branch inside github_stream(); handles dev_mode for
# ANY model (local Ollama default, with GitHub/Claude escalation).
# ---------------------------------------------------------------------------

def _dev_sse(model: str, delta: dict) -> str:
    """Frame a delta as an OpenAI chat.completion.chunk SSE line (the shape the
    UI's sse-parser/use-chat-stream already understands)."""
    import json as _json
    return "data: " + _json.dumps({
        "id": "chatcmpl-dev",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }) + "\n\n"


def _normalize_todos(raw) -> list[dict]:
    """Coerce model-supplied todos to [{content, status[, activeForm]}]."""
    valid = {"pending", "in_progress", "completed"}
    out: list[dict] = []
    for item in (raw or []):
        if isinstance(item, str):
            if item.strip():
                out.append({"content": item.strip(), "status": "pending"})
            continue
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("task") or item.get("title") or "").strip()
        if not content:
            continue
        status = str(item.get("status") or "pending").strip().lower()
        if status not in valid:
            status = "pending"
        todo = {"content": content, "status": status}
        if item.get("activeForm"):
            todo["activeForm"] = str(item["activeForm"])
        out.append(todo)
    return out


def _handle_todowrite(args: dict):
    """Harness tool: record a todo list and emit a `todo` SSE event.

    Returns (result_str, [StreamChunk]) — the loop yields the extra chunk.
    """
    from dev_harness.history import StreamChunk
    todos = _normalize_todos(args.get("todos"))
    done = sum(1 for t in todos if t["status"] == "completed")
    chunk = StreamChunk(type="todo", content="", data={"todos": todos})
    return f"Updated todo list ({done}/{len(todos)} complete).", [chunk]


def _exec_with_sink(tool_name: str, args: dict, container_name: str | None = None):
    """Run a sandbox tool with a thread-local file_change sink so writes/edits
    surface as file_change events. Runs on the executor thread (where the
    thread-local sink must live). Returns (result_str, [file_change event dicts]).

    container_name (may be None — see coordination/sandbox_identity.py) scopes
    this call to a specific per-session Docker container instead of the shared
    default; set on the same executor thread this function itself runs on,
    same bracketing pattern as the file_change sink two lines below."""
    from tools.sandbox_ops import execute_tool as _sandbox_execute
    from tools.file_change_sink import set_file_change_sink
    from coordination.sandbox_identity import set_current_container
    collected: list[dict] = []
    set_file_change_sink(collected.append)
    set_current_container(container_name)
    try:
        result = _sandbox_execute(tool_name, args)
    finally:
        set_file_change_sink(None)
        set_current_container(None)
    return result, collected


_SUBAGENT_SYSTEM = """\
You are a HiveCode subagent ({subagent_type}). You have the same sandbox tools \
(read_file, write_file, edit_file, list_directory, glob, grep, run_command, git, \
TodoWrite) scoped to /workspace. Complete the delegated task autonomously, then \
end with a concise summary of what you did and any findings the parent agent \
needs. You cannot spawn further subagents."""

_MAX_SUBAGENT_ITERS = 12


def _brief(obj, n: int = 80) -> str:
    s = str(obj)
    return s if len(s) <= n else s[: n] + "…"


async def _run_subagent(uid: str, model: str, description: str, prompt: str,
                        subagent_type: str, gate, container_name: str | None = None):
    """Spawn a child DevHarness for a delegated task.

    Returns (summary, [chunks]) where chunks are the agent_event trace plus
    forwarded file_change events.  The child runs autonomously (no interactive
    approval — the user already approved the Task spawn) but still under the
    permission gate + MAESTRO guard, and cannot spawn further subagents.

    container_name (may be None — see coordination/sandbox_identity.py):
    a Task subagent always inherits its caller's already-resolved session
    container rather than resolving one of its own.
    """
    from dev_harness.history import History, UserMessage, StreamChunk
    from dev_harness.loop import DevHarness
    from dev_harness.router import ModelRouter

    sub_type = subagent_type or "general"
    sys = _SUBAGENT_SYSTEM.format(subagent_type=sub_type)
    child_history = History(system=sys, turns=[UserMessage(prompt or description or "")])

    try:
        primary, targets = _build_dev_providers(model, uid)
    except Exception as e:
        return f"Subagent could not start: {e}", []
    child_router = ModelRouter(primary=primary, escalation_targets=targets)
    # No Task tool for the child — hard depth cap of 1.
    child_tools = [t for t in DEV_TOOL_DEFINITIONS if t["function"]["name"] != "Task"]

    async def _child_exec(cid, tname, targs):
        if tname == "TodoWrite":
            res, _ = _handle_todowrite(targs)
            return res
        loop = _asyncio.get_event_loop()
        result, fcs = await loop.run_in_executor(None, _exec_with_sink, tname, targs, container_name)
        if fcs:
            return result, [StreamChunk(type="file_change", data=e["content"]) for e in fcs]
        return result

    agent = f"subagent:{sub_type}"
    emitted: list = [StreamChunk(type="agent_event",
                                 content=f"Started: {_brief(description or prompt, 120)}",
                                 agent_name=agent, event_type="status")]
    parts: list[str] = []
    try:
        async for ch in DevHarness(max_iterations=_MAX_SUBAGENT_ITERS).run(
            child_history, child_tools, _child_exec, child_router, gate=gate
        ):
            if ch.type == "content":
                parts.append(ch.content)
            elif ch.type == "tool_start":
                emitted.append(StreamChunk(type="agent_event",
                                           content=f"{ch.tool_name}({_brief(ch.tool_input)})",
                                           agent_name=agent, event_type="tool"))
            elif ch.type == "tool_result":
                emitted.append(StreamChunk(type="agent_event", content=_brief(ch.content, 200),
                                           agent_name=agent, event_type="tool_result"))
            elif ch.type == "file_change":
                emitted.append(ch)  # forward edits so diffs/chips render in parent
            elif ch.type == "agent_event":
                emitted.append(ch)  # child escalation notices
    except Exception as e:
        logger.error(f"[dev_harness] subagent failed: {e}", exc_info=True)
        emitted.append(StreamChunk(type="agent_event", content=f"Subagent error: {e}",
                                   agent_name=agent, event_type="error"))
        return f"Subagent ({sub_type}) failed: {e}", emitted

    summary = "".join(parts).strip() or "(subagent produced no summary)"
    emitted.append(StreamChunk(type="agent_event", content="Finished.",
                               agent_name=agent, event_type="status"))
    return summary, emitted


# ---------------------------------------------------------------------------
# Mounted MCP (non-fs) tools — reuse the ToolHookRegistry safety stack
# (capability check + content_trust scan + audit) under a minted dev card.
# Dev fs/terminal tools stay on the sandbox substrate; only non-fs tools mount.
# All imports are lazy so a missing dep (jwt/web_browser) never breaks startup.
# ---------------------------------------------------------------------------

# dev tool name -> (ToolHookRegistry name, required capability)
_DEV_MCP_TOOLS = {
    "web_search": ("hive.browser.search", "browser_search"),
    "web_fetch": ("hive.browser.fetch", "browser_fetch"),
}
_DEV_MCP_ALIASES = {
    "hive.browser.search": "web_search",
    "hive.browser.fetch": "web_fetch",
}


def _dev_mcp_registry():
    """Lazily build + cache one ToolHookRegistry for mounted dev MCP tools."""
    reg = getattr(_dev_mcp_registry, "_reg", None)
    if reg is None:
        from mcp.tool_hooks import ToolHookRegistry
        reg = ToolHookRegistry()
        _dev_mcp_registry._reg = reg
    return reg


def _run_mcp_tool(uid: str, dev_name: str, args: dict) -> str:
    """Execute a mounted MCP tool via ToolHookRegistry under a minted dev card.

    Reuses the registry's capability enforcement + content_trust scan + audit.
    Lazy imports + broad except: a missing dep or runtime error returns a clean
    error string rather than breaking the harness.
    """
    canonical_name = _DEV_MCP_ALIASES.get(dev_name, dev_name)
    mapping = _DEV_MCP_TOOLS.get(canonical_name)
    if not mapping:
        return f"Unknown MCP tool: {dev_name}"
    hive_name, _cap = mapping
    try:
        from security.token_issuer import EphemeralAgentCard, get_token_issuer
        caps = sorted({c for (_n, c) in _DEV_MCP_TOOLS.values()})
        card = EphemeralAgentCard(
            template_id="hivecode_dev", template_version="1.0",
            agent_name=f"HiveCode_{uid}", activated_capabilities=caps,
            security_level="L2_USER", user_id=uid, session_id=uid, expiry_hours=2,
        )
        token = get_token_issuer().issue_token(card)
        result = _dev_mcp_registry().execute(hive_name, args, f"Bearer {token}")
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        body = "\n".join(t for t in texts if t) or "(no output)"
        return ("Error: " + body) if result.get("isError") else body
    except Exception as e:
        logger.error(f"[dev_harness] MCP tool {dev_name} failed: {e}", exc_info=True)
        return f"MCP tool error: {e}"


def _try_make_dev_github(uid: str, model: str | None):
    """GitHub provider adapter if the user has a connected token, else None."""
    try:
        from github_oauth import get_token
        if not get_token(uid):
            return None
        from providers.github_models_provider import GitHubProvider, GITHUB_MODELS
        return GitHubProvider(user_id=uid, model=model or GITHUB_MODELS[0]["id"])
    except Exception as e:
        logger.warning(f"[dev_harness] GitHub provider unavailable: {e}")
        return None


def _try_make_dev_anthropic(model: str | None):
    """Anthropic provider adapter if the SDK + key are present, else None."""
    try:
        from providers.anthropic_provider import AnthropicProvider, is_available
        if not is_available():
            return None
        return AnthropicProvider(model=model)  # None -> ANTHROPIC_MODEL default
    except Exception as e:
        logger.warning(f"[dev_harness] Anthropic provider unavailable: {e}")
        return None


def _build_dev_providers(model: str, uid: str):
    """Resolve (primary, [escalation_targets]) for a dev request.

    Primary follows the selected model: a GitHub/Anthropic model selects that
    cloud provider; anything else (incl. local Ollama models, which resolve to
    provider=None) uses the local Ollama adapter.  Escalation targets are the
    available cloud providers, excluding the primary.
    """
    from providers.registry import provider_for
    _p = provider_for(model)

    github = _try_make_dev_github(uid, model if _p == "github" else None)
    anthropic = _try_make_dev_anthropic(model if _p == "anthropic" else None)

    if _p == "github" and github is not None:
        return github, [t for t in (anthropic,) if t]
    if _p == "anthropic" and anthropic is not None:
        return anthropic, [t for t in (github,) if t]

    from providers.ollama_provider import OllamaProvider
    primary = OllamaProvider(model=model)
    return primary, [t for t in (github, anthropic) if t]


async def _dev_harness_stream(
    request: "ChatRequest", uid: str, *, bypass_allowed: bool = False
):
    """SSE generator wrapping DevHarness.run(); reuses the existing approval store."""
    from prompts.hivecode import HIVECODE_SYSTEM_PROMPT
    from dev_harness.history import History, StreamChunk
    from dev_harness.loop import DevHarness
    from dev_harness.router import ModelRouter
    from dev_harness.permissions import PermissionGate

    # The public Desktop route traverses Cloudflare.  A cold model load or a
    # per-session sandbox provision can take longer than its origin-first-byte
    # deadline, which otherwise turns a healthy Code request into a 524 before
    # the user sees anything.  Yield immediately so the proxy and client both
    # know this stream is alive.
    yield _dev_sse(request.model, {
        "type": "status",
        "content": "Preparing Code workspace…",
    })

    checkpoint_session_id = request.session_id or uid
    stored_checkpoint = None
    stored_checkpoint_data: dict = {}
    if request.dev_resume:
        from dev_harness.checkpoints import get_checkpoint
        stored_checkpoint = get_checkpoint(uid, checkpoint_session_id)
        if not stored_checkpoint or stored_checkpoint.get("status") != "ready_to_resume":
            status = stored_checkpoint.get("status") if stored_checkpoint else "missing"
            yield _dev_sse(request.model, {
                "type": "error",
                "content": f"Dev checkpoint is not ready to resume (status={status}).",
            })
            yield "data: [DONE]\n\n"
            return
        stored_checkpoint_data = stored_checkpoint.get("data") or {}

    # Slash command: /plan in the latest user message activates plan mode for
    # this turn (strip the prefix before the model sees it).
    perm_mode = request.dev_permission_mode or stored_checkpoint_data.get("permission_mode") or "default"
    msgs = [{"role": m.role, "content": m.content} for m in request.messages]
    if not request.dev_resume and msgs and msgs[-1].get("role") == "user":
        _last = (msgs[-1].get("content") or "").lstrip()
        if _last.startswith("/plan"):
            perm_mode = "plan"
            msgs[-1]["content"] = _last[len("/plan"):].lstrip() or "Investigate the request and propose a plan."

    # `bypass` is intentionally not a client-selectable permission escalation.
    # The UI may request it, but only an authenticated administrator may use it;
    # all other callers fall back to the ordinary approval path.
    if perm_mode == "bypass" and not bypass_allowed:
        logger.warning("[dev_harness] rejected bypass permission mode for non-admin uid=%s", uid)
        perm_mode = "default"

    if request.dev_resume:
        try:
            history = History.from_checkpoint(stored_checkpoint_data["history"])
        except (KeyError, TypeError, ValueError) as exc:
            yield _dev_sse(request.model, {
                "type": "error",
                "content": f"Dev checkpoint history is invalid: {exc}",
            })
            yield "data: [DONE]\n\n"
            return
    else:
        history = History.from_openai_messages(msgs, system=HIVECODE_SYSTEM_PROMPT)

    try:
        primary, targets = _build_dev_providers(request.model, uid)
    except Exception as e:
        logger.error(f"[dev_harness] provider init failed: {e}", exc_info=True)
        yield _dev_sse(request.model, {"type": "error", "content": f"Dev harness init failed: {e}"})
        yield "data: [DONE]\n\n"
        return

    router = ModelRouter(primary=primary, escalation_targets=targets)
    logger.info(
        f"[dev_harness] uid={uid} model={request.model} primary={primary.name} "
        f"targets={[t.name for t in targets]}"
    )

    class _Approval:
        """Bridges the loop's approval gate to the existing uid-keyed store."""

        def __init__(self, permission_gate):
            self.permission_gate = permission_gate

        def needs(self, tool_name: str) -> bool:
            # TodoWrite is pure planning — never needs approval.  Task DOES
            # (spawning an autonomous subagent is a significant action).
            if tool_name == "TodoWrite":
                return False
            if self.permission_gate.auto_approve(tool_name):
                return False
            return not _is_auto_approved(uid, tool_name)

        async def wait(self, call_id: str) -> str:
            event = _asyncio.Event()
            _approval_events[call_id] = event
            _approval_owners[call_id] = uid
            try:
                await _asyncio.wait_for(event.wait(), timeout=120.0)
            except _asyncio.TimeoutError:
                _approval_decisions.pop(call_id, None)
                return "timeout"
            finally:
                # The endpoint removes these on a decision; the finally block
                # handles timeout, client disconnect, and unexpected errors.
                _approval_events.pop(call_id, None)
                _approval_owners.pop(call_id, None)
            return "approved" if _approval_decisions.pop(call_id, False) else "denied"

    gate = PermissionGate(mode=perm_mode)

    # Per-session container this dev-mode chat turn's sandbox tool calls
    # target — same session_sandbox.py mechanism the composer/swarm path
    # uses (coordination/orchestrator.py), keyed by session_id (falls back
    # to uid) rather than a coordination_id so it outlives a single turn and
    # is reused across an entire /dev conversation (ensure_session_container
    # is idempotent — no idle-timeout teardown by design, see Design
    # Decision 2's "open questions" section; the startup orphan sweep is the
    # only v1 reaper). SESSION_SANDBOX_ENABLED off (or setup failing to
    # resolve a project) leaves this None, falling back to the shared
    # default container — unchanged prior behavior.
    container_name: str | None = stored_checkpoint_data.get("container_name") if request.dev_resume else None
    from coordination.orchestrator import SESSION_SANDBOX_ENABLED as _SESSION_SANDBOX_ENABLED
    if _SESSION_SANDBOX_ENABLED and not container_name:
        try:
            from dev_projects import store as _dev_projects_store
            from dev_projects.repo_context import build_repo_context
            from coordination.session_sandbox import ensure_session_container
            from coordination.sandbox_identity import set_current_container
            from coordination.workspace_ops import checkout_repo_branch

            _project = None
            if request.current_project_id:
                _project = _dev_projects_store.get_project(request.current_project_id, uid)
            if not _project:
                # No project selected — same default as pre-redesign behavior,
                # now backed by an isolated per-session live_repo container
                # instead of the shared one.
                _project = _dev_projects_store.get_or_create_live_repo_project(uid)

            _mode = "live_repo" if _project.get("source") == "live_repo" else "ephemeral"
            _session_key = request.session_id or uid
            container_name, _dh_created = ensure_session_container(_session_key, mode=_mode)

            # Clone into the container only once, right after it's first
            # created — ensure_session_container's idempotency means later
            # turns in the same conversation reuse it as-is, so re-cloning
            # on every turn would be both wasteful and pointless.
            if _dh_created and _mode == "ephemeral" and _project.get("git_url"):
                set_current_container(container_name)
                try:
                    _rc = build_repo_context(_project)
                    checkout_repo_branch(_rc["git_url"], _rc["branch"], _rc["base_branch"])
                finally:
                    set_current_container(None)
        except Exception as e:
            logger.error(f"[dev_harness] session container setup failed: {e}", exc_info=True)
            yield _dev_sse(request.model, {"type": "error", "content": f"Dev session setup failed: {e}"})
            yield "data: [DONE]\n\n"
            return

    async def _tool_executor(call_id: str, tool_name: str, args: dict):
        # Harness meta tools — handled here, not dispatched to the sandbox.
        if tool_name == "TodoWrite":
            return _handle_todowrite(args)
        if tool_name == "Task":
            return await _run_subagent(
                uid, request.model, args.get("description", ""),
                args.get("prompt", ""), args.get("subagent_type", "general"), gate,
                container_name=container_name,
            )
        if tool_name == "kb_search":
            loop = _asyncio.get_event_loop()
            from tools.kb_tool import kb_search as _kb_search
            return await loop.run_in_executor(
                None, _kb_search, args.get("query", ""), args.get("limit", 5)
            )
        if tool_name in _DEV_MCP_TOOLS:
            loop = _asyncio.get_event_loop()
            return await loop.run_in_executor(None, _run_mcp_tool, uid, tool_name, args)
        loop = _asyncio.get_event_loop()
        result, fcs = await loop.run_in_executor(None, _exec_with_sink, tool_name, args, container_name)
        if fcs:
            return result, [StreamChunk(type="file_change", data=e["content"]) for e in fcs]
        return result

    async def _checkpoint(status: str, turn: int, pending_tools: list[dict], error: str) -> bool:
        """Persist neutral history off-loop; false means fail closed."""
        from dev_harness.checkpoints import save_checkpoint

        payload = {
            "version": 1,
            "session_id": checkpoint_session_id,
            "model": request.model,
            "permission_mode": perm_mode,
            "container_name": container_name,
            "history": history.to_checkpoint(),
            "pending_tools": pending_tools,
            "error": error,
        }
        loop = _asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: save_checkpoint(
                uid,
                checkpoint_session_id,
                status=status,
                turn=turn,
                data=payload,
            ),
        )

    if not await _checkpoint("running", 0, [], ""):
        yield _dev_sse(request.model, {
            "type": "error",
            "content": "Dev session checkpoint unavailable; execution stopped safely.",
        })
        yield "data: [DONE]\n\n"
        return

    try:
        # Ollama's tool-capable call is deliberately non-streaming so we can
        # receive a complete tool-call envelope.  That means cold model loads
        # otherwise look like a frozen Code tab.  State the phase up front and
        # report elapsed waits below without cancelling useful work.
        yield _dev_sse(request.model, {
            "type": "status",
            "content": f"Workspace ready. Waiting for {request.model}…",
        })
        stream = DevHarness().run(
            history, DEV_TOOL_DEFINITIONS, _tool_executor, router,
            approval=_Approval(gate), gate=gate, checkpoint=_checkpoint,
        ).__aiter__()
        pending_chunk = _asyncio.ensure_future(stream.__anext__())
        waited_seconds = 0
        wait_notices = {15, 45, 90, 180}
        while True:
            # Do not cancel the in-flight model/tool call when the timeout
            # elapses.  Instead, keep the public SSE response alive until its
            # next real event arrives.
            done, _ = await _asyncio.wait({pending_chunk}, timeout=15.0)
            if not done:
                waited_seconds += 15
                if waited_seconds in wait_notices:
                    yield _dev_sse(request.model, {
                        "type": "status",
                        "content": (
                            f"Still waiting for {request.model} "
                            f"({waited_seconds}s). The model may be loading or queued."
                        ),
                    })
                else:
                    yield ": keepalive\n\n"
                continue
            try:
                chunk = pending_chunk.result()
            except StopAsyncIteration:
                break
            pending_chunk = _asyncio.ensure_future(stream.__anext__())
            delta: dict = {"type": chunk.type, "content": chunk.content}
            if chunk.tool_name:
                delta["tool_name"] = chunk.tool_name
            if chunk.tool_input is not None:
                delta["tool_input"] = chunk.tool_input
            if chunk.tool_call_id:
                delta["tool_call_id"] = chunk.tool_call_id
            if chunk.type == "tool_result":
                delta["tool_output"] = chunk.content
            if chunk.agent_name:
                delta["agent_name"] = chunk.agent_name
            if chunk.event_type:
                delta["event_type"] = chunk.event_type
            if chunk.data is not None:
                delta["content"] = chunk.data  # structured payload (e.g. todo)
            yield _dev_sse(request.model, delta)
    except Exception as e:
        logger.error(f"[dev_harness] stream error: {e}", exc_info=True)
        try:
            await _checkpoint("failed", 0, [], str(e))
        except Exception:
            logger.warning("[dev_harness] failed to persist error checkpoint", exc_info=True)
        yield _dev_sse(request.model, {"type": "error", "content": f"Dev harness error: {e}"})
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# SSE event allowlists — single source of truth for the streaming loop below.
# Any new rich event type must be added HERE (both mode-blocks reference these)
# and taught to the UI parser at ui/src/lib/utils/sse-parser.ts.
# ---------------------------------------------------------------------------
# Rich typed events forwarded verbatim (delta = full update dict) in BOTH modes.
_RICH_EVENT_TYPES = frozenset({
    "clarification_request", "clarification_card", "media_attachment",
    "set_preview_url", "preview_unavailable", "design_artifact", "cad_artifact",
    "suggested_followups", "workshop_questions", "workflow_next_steps",
    "agent_event", "file_change",
    # queue/VRAM status, tool lifecycle, and DevHarness todos — the UI already
    # parses and renders these; they were previously dropped here at the allowlist.
    "model_queue_status", "tool_start", "tool_progress", "tool_result", "todo",
})
# UI-routing signals forwarded only in non-standard mode (standard mode handles
# status/thought/plan individually above the allowlist).
_NONSTANDARD_SIGNAL_TYPES = frozenset({
    "status", "thought", "log", "plan",
    "turn_boundary", "turn_metadata", "continuation", "stream_mode",
})


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, http_request: Request):
    """
    Standard Chat API to allow external tools (Open-WebUI, VS Code) to talk to the Swarm.
    """
    from fastapi.responses import StreamingResponse
    from church import chat_swarm
    import json
    import asyncio

    _apply_model_policy(request, http_request)

    # --- Dev workspace agentic harness (handles dev_mode for ANY model) ---
    # Must precede the provider_for() dispatch below: local Ollama models resolve
    # to provider=None and would otherwise fall through to the swarm path, never
    # reaching the coding loop.  DevHarness picks Ollama/GitHub/Anthropic itself.
    if request.dev_mode and request.stream:
        _dev_uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
        return StreamingResponse(
            _dev_harness_stream(
                request,
                _dev_uid,
                bypass_allowed=_request_is_admin(http_request),
            ), media_type="text/event-stream"
        )

    # Route GitHub Models requests directly to the GitHubModelsProvider
    from providers.registry import provider_for
    _provider = provider_for(request.model)
    if _provider == "github":
        uid = http_request.headers.get("X-authentik-uid", "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="GitHub Models requires an authenticated Authentik session")
        try:
            from providers.github_models_provider import GitHubModelsProvider
        except ImportError as e:
            raise HTTPException(status_code=503, detail=f"GitHub Models provider unavailable: {e}")

        msgs = [{"role": m.role, "content": m.content} for m in request.messages]
        provider = GitHubModelsProvider(user_id=uid, model=request.model)

        if request.stream:
            async def github_stream():
                import time

                # NOTE: dev_mode (agentic coding) is handled upstream by
                # _dev_harness_stream() before the provider dispatch, so this
                # branch only serves non-agentic GitHub Models chat.

                # --- Standard (non-agentic) GitHub Models streaming ---
                for chunk in provider.generate_stream(msgs):
                    sse = {
                        "id": "chatcmpl-github",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [{"index": 0, "delta": {"content": chunk.content, "type": chunk.type}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(sse)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(github_stream(), media_type="text/event-stream")
        else:
            chunk = provider.generate(msgs)
            return {
                "id": "chatcmpl-github",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": chunk.content}, "finish_reason": "stop"}],
            }

    # Route NVIDIA NIM requests directly to the NvidiaProvider
    if _provider == "nvidia":
        uid = http_request.headers.get("X-authentik-uid", "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="NVIDIA NIM requires an authenticated session")
        try:
            from providers.nvidia_provider import NvidiaProvider
        except ImportError as e:
            raise HTTPException(status_code=503, detail=f"NVIDIA provider unavailable: {e}")

        msgs = [{"role": m.role, "content": m.content} for m in request.messages]
        provider = NvidiaProvider(user_id=uid, model=request.model)

        if request.stream:
            async def nvidia_stream():
                import time
                for chunk in provider.generate_stream(msgs):
                    sse = {
                        "id": "chatcmpl-nvidia",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [{"index": 0, "delta": {"content": chunk.content, "type": chunk.type}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(sse)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(nvidia_stream(), media_type="text/event-stream")
        else:
            chunk = provider.generate(msgs)
            return {
                "id": "chatcmpl-nvidia",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": chunk.content}, "finish_reason": "stop"}],
            }

    # Route Google Gemini requests directly to the GoogleProvider
    if request.model.startswith("gemini-"):
        uid = http_request.headers.get("X-authentik-uid", "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="Google Gemini requires an authenticated session")
        try:
            from providers.google_provider import GoogleProvider
        except ImportError as e:
            raise HTTPException(status_code=503, detail=f"Google provider unavailable: {e}")

        msgs = [{"role": m.role, "content": m.content} for m in request.messages]
        provider = GoogleProvider(user_id=uid, model=request.model)

        if request.stream:
            async def google_stream():
                import time
                for chunk in provider.generate_stream(msgs):
                    sse = {
                        "id": "chatcmpl-google",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [{"index": 0, "delta": {"content": chunk.content, "type": chunk.type}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(sse)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(google_stream(), media_type="text/event-stream")
        else:
            chunk = provider.generate(msgs)
            return {
                "id": "chatcmpl-google",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": chunk.content}, "finish_reason": "stop"}],
            }

    # Extract history (all but the last message), convert Pydantic models to dicts
    history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]
    # Extract latest prompt
    last_msg = request.messages[-1].content
    
    # Check for "Standard Mode" (OpenAI Compatibility)
    # Suppresses internal logs/status updates
    is_standard_mode = request.model.startswith("swarm-") or request.model == "default"
    owner_id = _resolve_owner_id(request.user_id, http_request)
    
    if request.stream:
        async def stream_generator():
            # Get generator from the swarm router
            import logging
            logger = logging.getLogger("uvicorn")
            try:
                gen = chat_swarm(
                    last_msg,
                    session_id=request.session_id or "default_session",
                    history=history,
                    memory_enabled=request.memory_enabled,
                    owner_id=owner_id,
                    model=request.model,
                    skill=request.skill,
                    style=request.style,
                    research_mode=request.research_mode,
                    ultraplan_mode=request.ultraplan_mode,
                    ultrathink_mode=request.ultrathink_mode,
                    attachments=request.attachments,
                    grounding_web=request.grounding_web,
                    grounding_docs=request.grounding_docs,
                    grounding_file=request.grounding_file,
                    already_steered=request.already_steered,
                    swarm_mode=request.swarm_mode,
                    design_mode=request.design_mode,
                    workshop_mode=request.workshop_mode,
                    dev_mode=request.dev_mode,
                    solving_max_iter=request.solving_max_iter,
                    solving_max_time=request.solving_max_time,
                    solving_solver_n_drafts=request.solving_solver_n_drafts,
                    solving_solver_max_time=request.solving_solver_max_time,
                    solving_verifier_n_runs=request.solving_verifier_n_runs,
                    solving_verifier_max_time=request.solving_verifier_max_time,
                    solving_corrector_n_passes=request.solving_corrector_n_passes,
                    solving_corrector_max_time=request.solving_corrector_max_time,
                    current_project_id=request.current_project_id,
                    active_file=request.active_file,
                )
            except Exception as e:
                logger.error(f"[Stream] chat_swarm init failed: {e}")
                yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':0,'model':request.model,'choices':[{'index':0,'delta':{'content':f'Error: {e}'},'finish_reason':None}]})}\n\n"
                yield "data: [DONE]\n\n"
                return

            update_count = 0
            response_parts = []  # Collect response text for memory extraction
            _in_think_block = False  # Track <think> tag state across chunks
            _input_chars  = sum(len(m.get("content") or "") for m in history or []) + len(last_msg)
            _output_chars = 0

            # Run church.py's synchronous generator in a background thread so the
            # asyncio event loop stays free during long LLM calls.  Without this,
            # the loop is blocked for 10–120 s and Cloudflare/Traefik (100 s timeout)
            # kills the connection before the first token arrives.
            import asyncio as _aio_sg
            import threading as _thr_sg
            _loop = _aio_sg.get_running_loop()
            _update_q: _aio_sg.Queue = _aio_sg.Queue(maxsize=64)
            _GEN_DONE = object()  # sentinel — signals the generator is exhausted

            def _gen_worker():
                try:
                    for _u in gen:
                        _aio_sg.run_coroutine_threadsafe(_update_q.put(_u), _loop).result()
                except Exception as _exc:
                    _aio_sg.run_coroutine_threadsafe(
                        _update_q.put({"type": "error", "content": f"Stream error: {_exc}"}),
                        _loop,
                    ).result()
                finally:
                    _aio_sg.run_coroutine_threadsafe(_update_q.put(_GEN_DONE), _loop).result()

            _thr_sg.Thread(target=_gen_worker, daemon=True, name="church-stream").start()

            try:
                while True:
                    try:
                        update = await _aio_sg.wait_for(_update_q.get(), timeout=30.0)
                    except _aio_sg.TimeoutError:
                        # SSE comment — ignored by clients but resets Cloudflare/Traefik idle timer
                        yield ": keepalive\n\n"
                        continue
                    if update is _GEN_DONE:
                        break
                    update_count += 1
                    logger.debug(f"[Stream] update #{update_count}: {update}")
                    # Update is expected to be a dict: {"type": ..., "content": ...}
                    if not isinstance(update, dict):
                        continue

                    msg_type = update.get("type", "response")
                    raw_content = update.get("content", "")
                    # DEBUG: log swarm-type events at INFO level
                    if msg_type in ("swarm_phase", "swarm_worker_created", "swarm_task_list"):
                        logger.info(f"[Stream] SWARM_EVENT: type={msg_type!r} is_standard={is_standard_mode} content={repr(raw_content)[:80]}")

                    # --- Parse <think>...</think> tags in message/response chunks ---
                    # Always active so qwen3's natural reasoning is shown
                    # in the ThinkingIndicator, not leaked as raw text.
                    if msg_type in ("message", "response") and raw_content:
                        import re
                        parts = re.split(r'(<think>|</think>)', raw_content)
                        sub_updates = []
                        for part in parts:
                            if part == '<think>':
                                _in_think_block = True
                                continue
                            elif part == '</think>':
                                _in_think_block = False
                                continue
                            if part:
                                sub_updates.append(("thought" if _in_think_block else msg_type, part))
                        if not sub_updates:
                            continue
                        # Process each sub-chunk through the normal pipeline
                        for sub_type, sub_content in sub_updates:
                            _update = dict(update)
                            _update["type"] = sub_type
                            _update["content"] = sub_content
                            # Re-assign for the rest of the loop iteration
                            msg_type = sub_type
                            raw_content = sub_content

                            # Yield the sub-chunk (duplicated logic for think sub-chunks)
                            if sub_type == "thought":
                                thought_chunk = {
                                    "id": "chatcmpl-swarm",
                                    "object": "chat.completion.chunk",
                                    "created": 1234567890,
                                    "model": request.model,
                                    "choices": [{"index": 0, "delta": {"content": sub_content, "type": "thought"}, "finish_reason": None}]
                                }
                                yield f"data: {json.dumps(thought_chunk)}\n\n"
                            else:
                                # Fall through to normal content handling below
                                break
                        else:
                            # All sub-chunks were thoughts, skip normal processing
                            continue

                    # Reset content for this iteration (prevent stale content from previous)
                    content = ""

                    # Heartbeat: orchestrator liveness ping with no content. Dropping
                    # it (as before) silently reset the 30 s keepalive timer above
                    # without ever putting bytes on the wire, so long swarm phases
                    # could stall past Cloudflare/Traefik's ~100 s idle timeout.
                    # Convert it into a real SSE keepalive comment instead.
                    if msg_type == "heartbeat":
                        yield ": keepalive\n\n"
                        continue

                    # --- SWARM THEATER EVENTS (unconditional — both modes) ---
                    # Handled before the is_standard_mode split so swarm events
                    # always produce typed deltas regardless of which model is used.
                    if msg_type in ("swarm_phase", "swarm_worker_created", "swarm_task_list"):
                        # Blank content — narrative text comes from message-type events
                        swarm_delta: dict = {"type": msg_type, "content": ""}
                        for _k in ("phase_num", "phase_name", "total_phases",
                                   "worker_id", "role", "pioneer_name",
                                   "pioneer_full_name", "pioneer_motto",
                                   "task", "phase", "workers"):
                            if _k in update:
                                swarm_delta[_k] = update[_k]
                        yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':int(time.time()),'model':request.model,'choices':[{'index':0,'delta':swarm_delta,'finish_reason':None}]})}\n\n"
                        continue

                    # In standard mode, forward status/thought as typed chunks;
                    # only yield assistant segments, errors, status, and thoughts.
                    if is_standard_mode:

                        if msg_type == "status":
                            status_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": {"content": raw_content, "type": "status"}, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(status_chunk)}\n\n"
                            continue

                        if msg_type == "thought":
                            thought_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": {"content": raw_content, "type": "thought"}, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(thought_chunk)}\n\n"
                            continue

                        if msg_type == "plan":
                            plan_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": {"content": raw_content, "type": "plan"}, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(plan_chunk)}\n\n"
                            continue

                        if msg_type == "tool_call":
                            tool_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "content": raw_content,
                                        "type": "tool_call",
                                        "tool_name": update.get("tool_name"),
                                        "tool_input": update.get("tool_input"),
                                        "tool_call_id": update.get("tool_call_id"),
                                    },
                                    "finish_reason": None,
                                }],
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                            continue

                        if msg_type in _RICH_EVENT_TYPES:
                            # Graceful-degradation fallback: rich events carry their
                            # payload in structured fields, but give clarification cards
                            # a human-readable `content` (the question) so a text-only or
                            # lossy client still shows something instead of an empty drop.
                            if msg_type == "clarification_card" and not update.get("content"):
                                _clar = update.get("clarification") or {}
                                update = {**update, "content": _clar.get("question", "Input needed")}
                            rich_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": update, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(rich_chunk)}\n\n"
                            continue

                        if msg_type not in ["message", "response", "error"]:
                            continue

                        content = raw_content
                    else:
                        # Non-standard mode: still send status/thought/log as
                        # typed chunks so the React UI can route them to the
                        # ThinkingIndicator / thought-trace instead of
                        # rendering them as message text.
                        # turn_boundary / turn_metadata / continuation /
                        # stream_mode are UI-routing signals — forward as
                        # typed chunks so the hook handles them, not the
                        # content appender.
                        if msg_type in (_NONSTANDARD_SIGNAL_TYPES | _RICH_EVENT_TYPES):
                            typed_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": update, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(typed_chunk)}\n\n"
                            continue
                        elif msg_type == "error":
                            content = f"\n> ❌ **ERROR**: {raw_content}\n\n"
                        else:
                            content = raw_content

                    if content:
                        # Strip heartbeat if it leaks through
                        content = content.replace("\u200B", "")

                        # Collect response text for memory extraction + token tracking
                        if msg_type in ("response", "message"):
                            response_parts.append(raw_content)
                            _output_chars += len(raw_content)

                        chunk = {
                            "id": "chatcmpl-swarm",
                            "object": "chat.completion.chunk",
                            "created": 1234567890,
                            "model": request.model,
                            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                logger.error(f"[Stream] Generator error after {update_count} updates: {e}", exc_info=True)
                err_msg = f"\nStream error: {e}"
                yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':0,'model':request.model,'choices':[{'index':0,'delta':{'content':err_msg},'finish_reason':None}]})}\n\n"

            logger.info(f"[Stream] Completed with {update_count} updates")

            # Background memory extraction (fire-and-forget)
            if request.memory_enabled and response_parts:
                try:
                    response_text = "".join(response_parts)
                    conversation = f"User: {last_msg}\nAssistant: {response_text}"
                    logger.info(f"[MemPalace] Scheduling extraction ({len(response_text)} chars, owner={owner_id})")

                    async def _bg_extract(conv, oid):
                        count = await _mempalace_extract_http(conv, owner_id=oid)
                        logger.info(f"[MemPalace] Extraction complete: {count} memories stored")

                    _aio_sg.get_running_loop().create_task(_bg_extract(conversation[:8000], owner_id))
                except Exception as e:
                    logger.warning(f"[MemPalace] Failed to schedule extraction: {e}")

            # Emit usage stats before closing the stream
            # Token estimates: ~4 chars per token (rough heuristic for mixed LLM output)
            _usage_chunk = {
                "id": "chatcmpl-usage",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": request.model,
                "choices": [{"index": 0, "delta": {"content": "", "type": "usage"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens":     max(1, _input_chars  // 4),
                    "completion_tokens": max(0, _output_chars // 4),
                    "total_tokens":      max(1, (_input_chars + _output_chars) // 4),
                    "prompt_chars":      _input_chars,
                    "completion_chars":  _output_chars,
                },
            }
            yield f"data: {json.dumps(_usage_chunk)}\n\n"

            # Finish
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming (accumulate all rendered output)
        gen = chat_swarm(
            last_msg,
            session_id=request.session_id or "default_session",
            history=history,
            memory_enabled=request.memory_enabled,
            owner_id=owner_id,
            model=request.model,
            skill=request.skill,
            style=request.style,
            research_mode=request.research_mode,
            ultraplan_mode=request.ultraplan_mode,
            ultrathink_mode=request.ultrathink_mode,
            attachments=request.attachments,
            grounding_web=request.grounding_web,
            grounding_docs=request.grounding_docs,
            grounding_file=request.grounding_file,
            swarm_mode=request.swarm_mode,
            design_mode=request.design_mode,
            dev_mode=request.dev_mode,
        )
        full_resp = ""
        for update in gen:
            if not isinstance(update, dict):
                continue
            msg_type = update.get("type", "response")
            raw_content = update.get("content", "")
            
            if is_standard_mode:
                if msg_type in ["message", "response"]:
                    full_resp += raw_content
            else:
                if msg_type in ("status", "thought", "log"):
                    continue  # skip pipeline chatter in non-stream response
                elif msg_type == "error":
                    full_resp += f"\n> ❌ **ERROR**: {raw_content}\n\n"
                else:
                    full_resp += raw_content
        
        # Strip heartbeat
        full_resp = full_resp.replace("\u200B", "")

        # Background memory extraction (non-streaming path)
        if request.memory_enabled and full_resp.strip():
            try:
                conversation = f"User: {last_msg}\nAssistant: {full_resp}"
                logger.info(f"[MemPalace] Scheduling extraction (non-stream, {len(full_resp)} chars, owner={owner_id})")

                async def _bg_extract_ns(conv, oid):
                    count = await _mempalace_extract_http(conv, owner_id=oid)
                    logger.info(f"[MemPalace] Extraction complete: {count} memories stored")

                asyncio.get_event_loop().create_task(_bg_extract_ns(conversation[:8000], owner_id))
            except Exception as e:
                logger.warning(f"[MemPalace] Failed to schedule extraction: {e}")

        return {
            "id": "chatcmpl-swarm",
            "object": "chat.completion",
            "created": 1234567890,
            "model": request.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": full_resp}, "finish_reason": "stop"}]
        }


@app.get("/api/v1/mcp/health")
async def mcp_health():
    return mcp_server.health()


@app.get("/api/v1/mcp/client-config")
async def mcp_client_config(request: Request):
    host = str(request.base_url).rstrip("/")
    return mcp_server.client_config(host_hint=host)


@app.post("/api/v1/mcp/rpc")
async def mcp_rpc(request: MCPRpcRequest, http_request: Request):
    try:
        auth_header = http_request.headers.get("Authorization")
        result = await mcp_server.handle_rpc(request.method, request.params, auth_header=auth_header)
        return ok_response(request.id, result).model_dump()
    except ValueError as e:
        logger.warning(
            f"[MCPBridge] Unsupported method",
            extra={
                "method": request.method,
                "request_id": request.id,
                "params_keys": list((request.params or {}).keys()),
            },
        )
        return error_response(request.id, -32601, str(e)).model_dump()
    except Exception as e:
        logger.error(
            f"[MCPBridge] RPC failure: {e}",
            extra={
                "method": request.method,
                "request_id": request.id,
                "params_keys": list((request.params or {}).keys()),
            },
        )
        return internal_error(request.id, e, {"method": request.method}).model_dump()

class LogRequest(BaseModel):
    level: str
    message: str
    source: str = "External"

@app.post("/log")
async def ingest_log(request: LogRequest):
    """
    Ingests logs from external services (like ComfyUI wrapper).
    """
    log_msg = f"[{request.source}] {request.message}"
    
    if request.level.upper() == "ERROR":
        logger.error(log_msg)
    elif request.level.upper() == "WARNING":
        logger.warning(log_msg)
    else:
        logger.info(log_msg)
        
    return {"status": "logged"}

# --- Governance Endpoints ---
from liskov import governance_manager, RequestType, RequestStatus, RequestItem

class CreateRequestModel(BaseModel):
    type: RequestType
    description: str
    user: str = "coding_user"

class UpdateRequestModel(BaseModel):
    status: RequestStatus
    note: str = None

@app.post("/api/v1/request", response_model=RequestItem)
async def create_request(req: CreateRequestModel, x_swarm_source: str = Header(None, alias="X-Swarm-Source")):
    """
    Submit a new governance request (e.g. Package install).
    MAESTRO L7: Enforces Identity via API Key.
    """
    import os
    import json
    
    # Load Valid Keys
    valid_keys_str = os.getenv("VALID_API_KEYS", "{}")
    logger.info(f"DEBUG: Raw VALID_API_KEYS: {valid_keys_str}")
    logger.info(f"DEBUG: Received Header: {x_swarm_source}")

    try:
        valid_keys = json.loads(valid_keys_str)
    except json.JSONDecodeError:
        logger.error("Failed to parse VALID_API_KEYS env var.")
        valid_keys = {}

    # Validate Key
    if not x_swarm_source or x_swarm_source not in valid_keys:
        logger.warning(f"Unauthorized Request Attempt. Key: {x_swarm_source}")
        raise HTTPException(status_code=401, detail="Invalid API Key. Identity could not be verified.")

    # Resolve Identity
    authenticated_user = valid_keys[x_swarm_source]
    logger.info(f"Authenticated Identity: {authenticated_user}")

    logger.info(f"New Governance Request: {req.type} - {req.description}")
    # Force the authenticated user, ignoring the payload's claim
    return governance_manager.submit_request(req.type, req.description, authenticated_user)

@app.get("/api/v1/request", response_model=list[RequestItem])
async def list_requests():
    """
    List all requests (for Admin Dashboard).
    """
    return governance_manager.get_all_requests()

@app.get("/api/v1/request/{req_id}", response_model=RequestItem)
async def get_request(req_id: str):
    """
    Get generic request details
    """
    item = governance_manager.get_request(req_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    return item

@app.post("/api/v1/request/{req_id}/status", response_model=RequestItem)
async def update_request_status(req_id: str, update: UpdateRequestModel):
    """
    Admin/Agent Update Status (Approve/Reject).
    When a GROUNDING_WEB or GROUNDING_DOCS request is approved, the permission
    is automatically written to the grounding permissions store.
    """
    item = governance_manager.update_status(req_id, update.status, update.note)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    logger.info(f"Request {req_id} updated to {update.status}")

    # Auto-grant grounding permissions on approval
    if update.status == RequestStatus.APPROVED:
        try:
            from grounding_permissions import grounding_permissions as _gp
            _type = item.type if hasattr(item, "type") else item.dict().get("type", "")
            if _type in ("GROUNDING_WEB", "grounding_web"):
                _gp.grant(item.user, "web_grounding")
                logger.info(f"[Grounding] web_grounding granted to {item.user}")
            elif _type in ("GROUNDING_DOCS", "grounding_docs"):
                _gp.grant(item.user, "docs_grounding")
                logger.info(f"[Grounding] docs_grounding granted to {item.user}")
            elif _type in ("GROUNDING_FILE", "grounding_file"):
                _gp.grant(item.user, "file_grounding")
                logger.info(f"[Grounding] file_grounding granted to {item.user}")
        except Exception as _perm_err:
            logger.error(f"[Grounding] Failed to write permission on approval: {_perm_err}")

    return item

# --- Node Health Endpoint (Phase 6) ---
@app.get("/api/v1/health/nodes")
async def health_nodes():
    """Returns health status of all Ollama inference nodes."""
    from inference.node_health import get_node_monitor
    monitor = get_node_monitor()
    return {"nodes": monitor.get_all_statuses()}


# ---------------------------------------------------------------------------
#  Grounding Permissions Endpoints
# ---------------------------------------------------------------------------

from grounding_permissions import grounding_permissions as _grounding_perm_store

class GroundingRequestModel(BaseModel):
    permission: str  # "web_grounding", "docs_grounding", or "file_grounding"
    reason: str = ""

@app.get("/api/v1/grounding/status")
async def grounding_status(http_request: Request):
    """Return the current grounding permissions for the authenticated user."""
    owner_id = _resolve_owner_id(None, http_request)
    _grounding_perm_store.reload()
    return _grounding_perm_store.get_status(owner_id)

@app.post("/api/v1/grounding/request")
async def request_grounding_permission(
    req: GroundingRequestModel,
    http_request: Request,
    x_swarm_source: str = Header(None, alias="X-Swarm-Source"),
):
    """Submit a governance request to unlock a grounding capability.

    The request is stored as a GROUNDING_WEB, GROUNDING_DOCS, or GROUNDING_FILE governance item.
    An admin can approve it via POST /api/v1/request/{id}/status which will
    automatically write the permission to the grounding store.
    """
    if req.permission not in ("web_grounding", "docs_grounding", "file_grounding"):
        raise HTTPException(status_code=400, detail="permission must be 'web_grounding', 'docs_grounding', or 'file_grounding'")

    owner_id = _resolve_owner_id(None, http_request)
    req_type_map = {
        "web_grounding": "GROUNDING_WEB",
        "docs_grounding": "GROUNDING_DOCS",
        "file_grounding": "GROUNDING_FILE",
    }
    gov_type = req_type_map[req.permission]
    description = (
        f"User {owner_id!r} is requesting {req.permission} capability. "
        f"Reason: {req.reason or 'not provided'}"
    )
    try:
        item = governance_manager.submit_request(gov_type, description, owner_id)
        return {"status": "submitted", "request_id": item.id, "permission": req.permission}
    except Exception as exc:
        logger.error("[Grounding] Failed to submit governance request: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to submit request: {exc}")


# ---------------------------------------------------------------------------
#  Phase 5: Remote & Multi-Node API
# ---------------------------------------------------------------------------

class RemoteExecRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    host: str
    command: str
    timeout: int = 60

class BridgeTaskRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    target_node: str
    task: str
    intent: Optional[str] = None

class BridgeProxyRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    target_node: str
    method: str = "GET"
    path: str = "/"
    json_body: Optional[dict] = None

@app.post("/api/v1/remote/exec")
async def remote_exec(req: RemoteExecRequest):
    """Execute a command on a remote host via SSH."""
    from utils.remote_executor import get_remote_executor
    executor = get_remote_executor()
    result = executor.execute(req.host, req.command, timeout=req.timeout)
    return result.to_dict()

@app.get("/api/v1/remote/hosts")
async def remote_hosts():
    """List all configured remote hosts."""
    from utils.remote_executor import get_remote_executor
    return {"hosts": get_remote_executor().list_hosts()}

@app.post("/api/v1/bridge/submit")
async def bridge_submit(req: BridgeTaskRequest):
    """Submit a task to a remote Hive node."""
    from utils.bridge import get_bridge
    result = get_bridge().submit_task(req.target_node, req.task, intent=req.intent)
    return result

@app.post("/api/v1/bridge/proxy")
async def bridge_proxy(req: BridgeProxyRequest):
    """Proxy a request to a remote Hive node."""
    from utils.bridge import get_bridge
    result = get_bridge().proxy_request(req.target_node, req.method, req.path, json_body=req.json_body)
    return result

@app.get("/api/v1/bridge/nodes")
async def bridge_nodes():
    """List bridge nodes with health status."""
    from utils.bridge import get_bridge
    bridge = get_bridge()
    return {"nodes": bridge.list_nodes(), "health": bridge.check_all_health()}

@app.get("/api/v1/bridge/jobs")
async def bridge_jobs(status: Optional[str] = None):
    """List bridge jobs."""
    from utils.bridge import get_bridge
    return {"jobs": get_bridge().list_jobs(status_filter=status)}

@app.get("/api/v1/daemon/workers")
async def daemon_workers(state: Optional[str] = None):
    """List daemon workers."""
    from daemon_registry import get_daemon_registry
    reg = get_daemon_registry()
    return {"workers": reg.list_workers(state_filter=state), "count": reg.count()}

@app.get("/api/v1/trigger/list")
async def trigger_list(trigger_type: Optional[str] = None):
    """List triggers."""
    from trigger_scheduler import get_trigger_scheduler
    sched = get_trigger_scheduler()
    return {"triggers": sched.list_triggers(type_filter=trigger_type), "count": sched.count(), "running": sched.is_running}


class TriggerCronSpec(BaseModel):
    hour: Optional[int] = None
    minute: Optional[int] = None
    day_of_week: Optional[int] = None

class TriggerTaskConfig(BaseModel):
    """What to run when the trigger fires — passed straight through to chat_swarm()."""
    prompt: str
    session_id: Optional[str] = None
    model: Optional[str] = None
    swarm_mode: bool = False
    dev_mode: bool = False
    ultraplan_mode: bool = False

class TriggerCreateRequest(BaseModel):
    name: str
    trigger_type: str  # "cron" | "interval" | "once"
    task_config: TriggerTaskConfig
    cron: Optional[TriggerCronSpec] = None
    interval_seconds: Optional[float] = None
    delay_seconds: Optional[float] = None
    fire_at: Optional[float] = None

@app.post("/api/v1/trigger/create")
async def trigger_create(req: TriggerCreateRequest, request: Request):
    """Create a scheduled task — a trigger whose handler fires a chat_swarm() call
    (task_config), not a raw in-process Python handler. This is the only trigger
    kind creatable over the API, and the only kind that survives a restart."""
    from trigger_scheduler import get_trigger_scheduler
    sched = get_trigger_scheduler()
    uid = request.headers.get("X-authentik-uid", "").strip() or None
    task_config = req.task_config.model_dump()
    # owner_id defaults to the caller so scheduled runs are attributed correctly
    task_config.setdefault("owner_id", uid)

    if req.trigger_type == "cron":
        cron = req.cron or TriggerCronSpec()
        tid = sched.add_cron_task(
            req.name, task_config, hour=cron.hour, minute=cron.minute, day_of_week=cron.day_of_week,
            created_by=uid,
        )
    elif req.trigger_type == "interval":
        if not req.interval_seconds:
            raise HTTPException(status_code=400, detail="interval_seconds is required for an interval trigger")
        tid = sched.add_interval_task(req.name, task_config, seconds=req.interval_seconds, created_by=uid)
    elif req.trigger_type == "once":
        if not req.delay_seconds and not req.fire_at:
            raise HTTPException(status_code=400, detail="delay_seconds or fire_at is required for a one-shot trigger")
        tid = sched.add_once_task(
            req.name, task_config, delay_seconds=req.delay_seconds or 0, fire_at=req.fire_at, created_by=uid,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown trigger_type: {req.trigger_type}")

    return {"trigger": sched.get(tid)}

@app.post("/api/v1/trigger/{trigger_id}/pause")
async def trigger_pause(trigger_id: str):
    from trigger_scheduler import get_trigger_scheduler
    sched = get_trigger_scheduler()
    if not sched.pause(trigger_id):
        raise HTTPException(status_code=404, detail="Trigger not found or not active")
    return {"trigger": sched.get(trigger_id)}

@app.post("/api/v1/trigger/{trigger_id}/resume")
async def trigger_resume(trigger_id: str):
    from trigger_scheduler import get_trigger_scheduler
    sched = get_trigger_scheduler()
    if not sched.resume(trigger_id):
        raise HTTPException(status_code=404, detail="Trigger not found or not paused")
    return {"trigger": sched.get(trigger_id)}

@app.delete("/api/v1/trigger/{trigger_id}")
async def trigger_delete(trigger_id: str):
    from trigger_scheduler import get_trigger_scheduler
    sched = get_trigger_scheduler()
    if not sched.remove(trigger_id):
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"deleted": trigger_id}


# --- Phase 6: OpenClaude gRPC Gateway REST Endpoints ---

class GrpcInferRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    prompt: str
    model: str = ""
    intent: str = ""
    max_tokens: int = 0
    temperature: float = 0.7
    session_id: str = ""
    history: Optional[List[dict]] = None

@app.post("/api/v1/grpc/infer")
async def grpc_infer(req: GrpcInferRequest):
    """Run inference via the OpenClaude gRPC gateway (REST proxy)."""
    from grpc.client import get_grpc_client
    client = get_grpc_client()
    result = client.infer(
        prompt=req.prompt, model=req.model, intent=req.intent,
        max_tokens=req.max_tokens, temperature=req.temperature,
        session_id=req.session_id, history=req.history,
    )
    return result

@app.post("/api/v1/grpc/classify")
async def grpc_classify(req: TaskRequest):
    """Classify prompt intent via the OpenClaude gRPC gateway."""
    from grpc.client import get_grpc_client
    client = get_grpc_client()
    return client.classify(prompt=req.task)

@app.get("/api/v1/grpc/models")
async def grpc_models():
    """List models available across all Ollama nodes via gRPC gateway."""
    from grpc.client import get_grpc_client
    return {"models": get_grpc_client().list_models()}

@app.get("/api/v1/grpc/health")
async def grpc_health():
    """Health check of the OpenClaude gRPC inference gateway."""
    from grpc.client import get_grpc_client
    return get_grpc_client().health_check()


# ---------------------------------------------------------------------------
#  Training Pipeline API
# ---------------------------------------------------------------------------

class TrainingStartRequest(BaseModel):
    """Request body for /v1/training/start."""
    model_config = ConfigDict(extra="allow")
    run_type: str = "training"           # training | export | full_pipeline | curated | synthetic
    time_budget_minutes: Optional[float] = None
    base_model: Optional[str] = None
    lora_rank: Optional[int] = None
    learning_rate: Optional[float] = None
    epochs: Optional[int] = None
    dataset_path: Optional[str] = None
    # For curated dataset runs
    curated_datasets: Optional[List[str]] = None   # e.g. ["glaive-function-calling", "hermes-function-calling"]
    max_samples: Optional[int] = None              # per-dataset sample limit
    # For synthetic generation runs
    synthetic_target: Optional[int] = None          # target trajectory count (default 552)
    # Template filter — train only on traces from this agent template
    template_id: Optional[str] = None               # e.g. "code_developer", "creative_writer"

# In-memory tracking for the active training background task
_active_training: dict = {"run_id": None, "status": "idle", "started_at": None, "task": None}


async def _training_watchdog_loop():
    """Reconcile silent training-task crashes against the DB.

    Why: training runs as an asyncio task in this process; a crash on a
    code path that escapes `_run_training`'s except block (e.g. CancelledError
    or import-time failures) can leave the DB row stuck on 'running' forever.
    This loop catches that case while the container is up — the lifespan
    startup reconciler only runs on boot.
    """
    import asyncio as _asyncio

    while True:
        try:
            await _asyncio.sleep(60)
            task = _active_training.get("task")
            run_id = _active_training.get("run_id")
            if task is None or not task.done():
                continue
            # Task finished. If status didn't get reset to idle, the finally
            # block didn't run — treat as a hard crash.
            if _active_training.get("status") == "running" and run_id:
                exc = task.exception() if not task.cancelled() else _asyncio.CancelledError()
                err = f"{type(exc).__name__}: {exc}" if exc else "Task exited without resetting status"
                logger.error(f"[TrainingWatchdog] Reconciling orphaned run {run_id}: {err}")
                try:
                    from training.grpo_trainer import _update_training_run
                    _update_training_run(run_id, "failed", error=f"watchdog: {err}")
                except Exception as db_err:
                    logger.warning(f"[TrainingWatchdog] DB update failed for run {run_id}: {db_err}")
            _active_training["status"] = "idle"
            _active_training["run_id"] = None
            _active_training["task"] = None
        except _asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"[TrainingWatchdog] loop error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Buddy companion endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/v1/buddy")
async def buddy_get_state():
    """Get the current buddy state (XP, level, streak, achievements)."""
    try:
        from kay_service import get_state, get_achievements
        state = get_state()
        achievements = get_achievements()
        return {**state, "achievements": achievements}
    except Exception as exc:
        logger.warning(f"[Buddy] get_state failed: {exc}")
        return {"error": str(exc)}


@app.put("/v1/buddy")
async def buddy_save_state(request: Request):
    """Persist the full buddy state from the UI."""
    try:
        from kay_service import save_state
        body = await request.json()
        result = save_state(body)
        return result
    except Exception as exc:
        logger.warning(f"[Buddy] save_state failed: {exc}")
        return {"error": str(exc)}


@app.post("/v1/buddy/xp")
async def buddy_award_xp(request: Request):
    """Award XP for an event and return updated level info."""
    try:
        from kay_service import award_xp
        body = await request.json()
        event = body.get("event", "message_sent")
        result = award_xp(event)
        return result
    except Exception as exc:
        logger.warning(f"[Buddy] award_xp failed: {exc}")
        return {"error": str(exc)}


@app.get("/v1/buddy/habits")
async def buddy_get_habits():
    """Get user habit summary for the last 7 days."""
    try:
        from kay_service import get_habits_summary
        return get_habits_summary()
    except Exception as exc:
        logger.warning(f"[Buddy] get_habits failed: {exc}")
        return {"error": str(exc)}


@app.get("/v1/buddy/tip")
async def buddy_get_tip(context: str = "general"):
    """Get a contextual tip based on buddy state and context."""
    try:
        from kay_service import get_state, get_contextual_tip
        state = get_state()
        tip = get_contextual_tip(state, context=context)
        return {"tip": tip}
    except Exception as exc:
        logger.warning(f"[Buddy] get_tip failed: {exc}")
        return {"tip": None, "error": str(exc)}


@app.get("/v1/buddy/comment")
async def buddy_get_comment(context: str = "response_received"):
    """Get a stage-appropriate inline comment to inject into the chat thread."""
    try:
        from kay_service import get_state, get_contextual_comment
        state = get_state()
        comment = get_contextual_comment(state, context=context)
        return {"comment": comment}
    except Exception as exc:
        logger.warning(f"[Buddy] get_comment failed: {exc}")
        return {"comment": None, "error": str(exc)}


@app.get("/v1/buddy/achievements")
async def buddy_get_achievements():
    """Get all earned achievements."""
    try:
        from kay_service import get_achievements
        return {"achievements": get_achievements()}
    except Exception as exc:
        logger.warning(f"[Buddy] get_achievements failed: {exc}")
        return {"achievements": [], "error": str(exc)}


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge graph endpoints — serves graphify codebase graph files
# ═══════════════════════════════════════════════════════════════════════════

# GRAPHIFY_GRAPH_DIR points at the graphify-out folder for this project.
# Default assumes the container mounts the repo at /app and graphify runs there.
# Override via env var for alternate paths or cross-repo graphs.
_GRAPHIFY_GRAPH_DIR = Path(os.environ.get(
    "GRAPHIFY_GRAPH_DIR",
    # In the container: full repo is mounted at /workspace; agents dir at /app/agents.
    # Walk up from agents → repo root → graphify-out.
    # /workspace/graphify-out is tried first; fall back to sibling of agents dir.
    Path("/workspace/graphify-out")
    if Path("/workspace/graphify-out").exists() or Path("/workspace").exists()
    else Path(__file__).parent.parent / "graphify-out",
))

_GRAPH_NOT_READY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body { margin: 0; background: #0f1117; color: #6872a8; font-family: 'Segoe UI', sans-serif;
           display: flex; flex-direction: column; align-items: center; justify-content: center;
           height: 100vh; gap: 16px; }
    h2 { color: #c8d4f5; font-size: 1.1rem; font-weight: 600; margin: 0; }
    p  { font-size: 0.85rem; margin: 0; color: #4e5582; }
    code { background: #1a1d27; border: 1px solid #2d3148; padding: 3px 8px;
           border-radius: 4px; font-size: 0.8rem; color: #9ba3c8; }
  </style>
</head>
<body>
  <h2>🔭 Codebase graph not ready yet</h2>
  <p>Run extraction on the project to generate the graph.</p>
  <code>graphify extract . --backend ollama --model qwen3:14b --max-concurrency 1</code>
</body>
</html>"""


@app.get("/v1/graph/codebase")
async def graph_codebase(
    format: str = "json",   # noqa: A002 — shadows builtin intentionally for URL param
    fmt: str = "",          # legacy alias kept for backward compatibility
):
    """Serve the graphify codebase knowledge graph.

    ?format=html  — returns the full interactive D3 page (graph.html).
    ?format=json  — returns the raw graph.json node-link data.

    The graph is generated by `graphify extract` and stored in GRAPHIFY_GRAPH_DIR
    (default: <repo-root>/graphify-out). Set the GRAPHIFY_GRAPH_DIR env var to
    override, e.g. to point at a global or merged cross-repo graph.
    """
    # Normalise: accept both ?format= and legacy ?fmt=
    resolved_fmt = format or fmt or "json"

    graph_dir = _GRAPHIFY_GRAPH_DIR
    html_path = graph_dir / "graph.html"
    json_path = graph_dir / "graph.json"

    if resolved_fmt == "html":
        if html_path.exists():
            # Stream the (large) HTML file rather than reading it all into memory
            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(html_path),
                media_type="text/html",
                headers={"Content-Disposition": "inline"},
            )
        return HTMLResponse(content=_GRAPH_NOT_READY_HTML, status_code=202)

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No graph.json found at {graph_dir}. Run graphify extract first.",
        )
    return JSONResponse(content=json.loads(json_path.read_text(encoding="utf-8")))


@app.get("/v1/graph/report")
async def graph_report():
    """Return the plain-text GRAPH_REPORT.md from graphify-out."""
    report_path = _GRAPHIFY_GRAPH_DIR / "GRAPH_REPORT.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="GRAPH_REPORT.md not found.")
    return Response(
        content=report_path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Task board endpoints (mobile Codex loop — swarm run history)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/v1/tasks")
async def list_tasks(request: Request, status: str = "all", limit: int = 50):
    """List the authenticated user's swarm runs for the mobile task board.

    Owner is resolved with _resolve_owner_id — the SAME resolution the swarm
    dispatch uses on the write path — so the board sees the rows it recorded
    (raw X-authentik-uid would miss username-keyed rows; the critic's blocker #1).
    """
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        return {"runs": []}
    import swarm_run_store
    import swarm_run_repo_store
    import swarm_run_local_store
    runs = swarm_run_store.list_runs(
        owner_id, limit=min(max(int(limit), 1), 200), running_only=(status == "running")
    )
    coordination_ids = [r["coordination_id"] for r in runs]
    repo_by_id = swarm_run_repo_store.get_many(coordination_ids)
    local_by_id = swarm_run_local_store.get_many(coordination_ids)
    for r in runs:
        repo = repo_by_id.get(r["coordination_id"])
        local = local_by_id.get(r["coordination_id"])
        if repo:
            r["repo_url"] = repo["git_url"]
            r["branch"] = repo["branch"]
            r["dev_project_id"] = repo.get("dev_project_id")
        elif local:
            r["dev_project_id"] = local["dev_project_id"]
    return {"runs": runs}


@app.get("/v1/tasks/{coordination_id}")
async def get_task(coordination_id: str, request: Request):
    """Run detail + per-worker (pioneer) status for the board drill-down."""
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Task not found")
    import swarm_run_store
    import swarm_run_repo_store
    import swarm_run_local_store
    run = swarm_run_store.get_run(coordination_id, owner_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    repo = swarm_run_repo_store.get(coordination_id)
    if repo:
        run["repo_url"] = repo["git_url"]
        run["branch"] = repo["branch"]
        run["dev_project_id"] = repo.get("dev_project_id")
    else:
        local = swarm_run_local_store.get(coordination_id)
        if local:
            run["dev_project_id"] = local["dev_project_id"]
    return {"run": run, "workers": swarm_run_store.get_workers(coordination_id, owner_id)}


@app.patch("/v1/tasks/{coordination_id}")
async def patch_task(coordination_id: str, body: TaskMetadataPatch, request: Request):
    """Update owner-scoped mutable task metadata only."""
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Task not found")
    import swarm_run_store
    import swarm_run_repo_store

    run = swarm_run_store.get_run(coordination_id, owner_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    if run.get("status") in {"completed", "failed", "denied", "cancelled"}:
        raise HTTPException(status_code=409, detail="Task metadata is immutable after terminal completion")
    if body.branch is not None:
        if not body.branch or body.branch.startswith("-") or ".." in body.branch or "@{" in body.branch:
            raise HTTPException(status_code=422, detail="Invalid branch name")
        repo = swarm_run_repo_store.get(coordination_id)
        if not repo:
            raise HTTPException(status_code=409, detail="Task has no repository branch context")
        if not swarm_run_repo_store.update_branch(coordination_id, body.branch):
            raise HTTPException(status_code=409, detail="Task branch could not be updated")
    if any(value is not None for value in (body.title, body.scope, body.prompt)):
        if not swarm_run_store.update_metadata(
            coordination_id, owner_id, title=body.title, scope=body.scope, prompt=body.prompt
        ):
            raise HTTPException(status_code=409, detail="Task metadata could not be updated")
    updated = swarm_run_store.get_run(coordination_id, owner_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    repo = swarm_run_repo_store.get(coordination_id)
    if repo:
        updated["repo_url"] = repo["git_url"]
        updated["branch"] = repo["branch"]
        updated["dev_project_id"] = repo.get("dev_project_id")
    return {"run": updated, "workers": swarm_run_store.get_workers(coordination_id, owner_id)}


@app.get("/v1/tasks/{coordination_id}/diff")
async def get_task_diff(coordination_id: str, request: Request):
    """Aggregated unified diff for a completed run, for mobile review."""
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Task not found")
    import swarm_run_store
    run = swarm_run_store.get_run(coordination_id, owner_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    if run.get("status") == "running":
        raise HTTPException(status_code=409, detail="Run still in progress")
    diff_text = swarm_run_store.get_diff(coordination_id, owner_id)
    if not diff_text:
        raise HTTPException(status_code=404, detail="No diff for this run")
    return {
        "coordination_id": coordination_id,
        "scope": run.get("scope"),
        "diff_text": diff_text,
        "truncated": "[...diff truncated...]" in diff_text,
    }


@app.post("/v1/tasks/{coordination_id}/approve")
async def approve_task(coordination_id: str, request: Request):
    """Record acceptance of a run's result from the phone.

    v1 is POST-HOC: swarm runs auto-execute and have no coordinator approval
    gate, so this records 'I accept this diff' — it does NOT pause/release a
    build. set_approval is owner-scoped, so a foreign owner gets 404.
    """
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Task not found")
    import swarm_run_store
    if not swarm_run_store.set_approval(coordination_id, owner_id, "approved"):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "approval_state": "approved"}


@app.post("/v1/tasks/{coordination_id}/deny")
async def deny_task(coordination_id: str, request: Request):
    """Record rejection of a run's result from the phone (post-hoc, owner-scoped)."""
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Task not found")
    import swarm_run_store
    if not swarm_run_store.set_approval(coordination_id, owner_id, "denied"):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "approval_state": "denied"}


# Default off — flip on only after manually verifying Phase A/B end to end
# (see agents/dev_harness/SWARM_ON_DEVHARNESS.md for this repo's flagging
# convention).
TASKS_DIRECT_CREATE_ENABLED = os.getenv("TASKS_DIRECT_CREATE_ENABLED", "").lower() in ("1", "true", "yes")


class CreateTaskRequest(BaseModel):
    prompt: str
    dev_project_id: Optional[str] = None
    branch: Optional[str] = None
    ultraplan_mode: bool = False
    research_mode: bool = False


# In-process registry of dispatch kwargs for tasks currently sitting in the
# Redis wait list (coordination/task_queue.py). Deliberately not persisted —
# see task_queue.py's module docstring for why that's an accepted tradeoff.
_PENDING_TASK_DISPATCH: dict = {}
_pending_task_dispatch_lock = threading.Lock()


def _dispatch_task_now(coordination_id: str, dispatch_kwargs: dict) -> None:
    """Flip a run to 'running' and drain its coordinate_task generator on a
    background thread. However the run ends, the thread releases the shared-
    sandbox lock and advances the queue — this is the only place that happens,
    so every acquire is guaranteed a matching release."""
    import swarm_run_store
    from coordination import task_queue as _task_queue

    swarm_run_store.set_status(coordination_id, "running")

    def _run():
        try:
            from coordination.orchestrator import coordinate_task
            for _ in coordinate_task(**dispatch_kwargs):
                pass
        except Exception as exc:
            logger.error(f"[TaskQueue] coordinate_task failed for {coordination_id}: {exc}", exc_info=True)
        finally:
            _task_queue.release(coordination_id)
            _advance_task_queue()

    threading.Thread(target=_run, daemon=True, name=f"task-{coordination_id}").start()


def _advance_task_queue() -> None:
    """Pop the next queued task (if any) and dispatch it now that the shared
    sandbox lock is free."""
    from coordination import task_queue as _task_queue

    next_id = _task_queue.pop_next()
    if not next_id:
        return
    with _pending_task_dispatch_lock:
        kwargs = _PENDING_TASK_DISPATCH.pop(next_id, None)
    if not kwargs:
        # Process restart lost this task's dispatch args — startup
        # reconciliation already marked it 'failed'; nothing to run.
        logger.warning(f"[TaskQueue] Queued task {next_id} had no pending dispatch args — skipping.")
        _advance_task_queue()
        return
    if not _task_queue.try_acquire(next_id):
        # Lock was somehow re-taken between pop and acquire — put it back and
        # let the current holder's release trigger another advance.
        with _pending_task_dispatch_lock:
            _PENDING_TASK_DISPATCH[next_id] = kwargs
        _task_queue.enqueue(next_id)
        return
    _dispatch_task_now(next_id, kwargs)


@app.post("/v1/tasks", status_code=202)
async def create_task(body: CreateTaskRequest, request: Request):
    """Direct task creation for the "New Task" composer — bypasses chat entirely.

    If dev_project_id is given, resolves it (owner-scoped) into a repo_context
    that coordinate_task() checks the sandbox out to before Decompose starts
    (see coordination/orchestrator.py's Phase 0). dev_sandbox is one shared
    container/working tree, so only one task may run at a time — a second
    POST while another task holds it is recorded as status="queued" and
    dispatched automatically once the sandbox frees up (coordination/task_queue.py).
    """
    if not TASKS_DIRECT_CREATE_ENABLED:
        raise HTTPException(status_code=404, detail="Direct task creation is not enabled")

    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Could not resolve an authenticated owner")

    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    # session_mode drives which session_sandbox container mode this run gets
    # (see coordination/session_sandbox.py): "live_repo" for the one
    # distinguished project that bind-mounts the live repo, "ephemeral" for a
    # git_url-linked project (repo_context carries git_url/branch, Phase 0
    # clones it fresh), "local" for a blank project (repo_context carries
    # local_path instead, Phase 0 seeds the container from that project's own
    # persisted, git-initialized files — see workspace_ops.checkout_local_project),
    # or None when no project is linked at all (today's pre-redesign
    # behavior — falls back to the shared dev_sandbox if SESSION_SANDBOX_ENABLED
    # is even on, so it needs the SAME lock protection as live_repo below).
    session_mode = None
    repo_context = None
    if body.dev_project_id:
        from dev_projects import store as _dev_projects_store
        project = _dev_projects_store.get_project(body.dev_project_id, owner_id)
        if not project:
            raise HTTPException(status_code=404, detail="dev_project_id not found")
        if project.get("source") == "live_repo":
            session_mode = "live_repo"
        elif project.get("git_url"):
            from dev_projects.repo_context import build_repo_context
            repo_context = build_repo_context(project, branch=body.branch)
            session_mode = "ephemeral"
        else:
            # Blank project — no git_url to clone, but provision_project_dir()
            # git-inits every blank project at creation (docker_exec.py), so
            # there's a real local repo to seed the task container from.
            repo_context = {"dev_project_id": project["id"], "local_path": project["path"]}
            session_mode = "local"

    import swarm_run_store
    from coordination import task_queue as _task_queue

    coordination_id = f"coord-{uuid.uuid4().hex[:8]}"
    session_id = f"task-{uuid.uuid4().hex[:12]}"

    dispatch_kwargs = dict(
        user_input=prompt,
        session_id=session_id,
        owner_id=owner_id,
        dev_mode=True,
        skip_project_gate=True,
        ultraplan_mode=body.ultraplan_mode,
        research_mode=body.research_mode,
        repo_context=repo_context,
        session_mode=session_mode,
        coordination_id=coordination_id,
    )

    # The live_repo lock only protects the one shared-host-path resource:
    # live_repo mode (multiple containers, same mount) and no-project-linked
    # runs (fall back to the shared dev_sandbox). An "ephemeral" run has its
    # own fully-isolated container — nothing to serialize, dispatch immediately.
    _needs_live_repo_lock = session_mode != "ephemeral"

    # Create the row synchronously (status set explicitly below) so GET
    # /v1/tasks/{id} works the instant this call returns. coordinate_task()
    # would also call create_run itself, but ON CONFLICT DO NOTHING makes
    # that a safe no-op against the row we create here.
    if not _needs_live_repo_lock or _task_queue.try_acquire(coordination_id):
        swarm_run_store.create_run(
            coordination_id, session_id, owner_id, title=prompt, scope=None,
            started_at=int(time.time()), status="running",
        )
        _dispatch_task_now(coordination_id, dispatch_kwargs)
    else:
        swarm_run_store.create_run(
            coordination_id, session_id, owner_id, title=prompt, scope=None,
            started_at=int(time.time()), status="queued",
        )
        with _pending_task_dispatch_lock:
            _PENDING_TASK_DISPATCH[coordination_id] = dispatch_kwargs
        _task_queue.enqueue(coordination_id)

    return {"coordination_id": coordination_id}


# ---------------------------------------------------------------------------
# GATED PUSH + PR (Phase D of the Codex-task-composer plan)
#
# Two-step preview -> explicit-confirm flow. Every precondition is checked
# BEFORE any GitHub/git call: diff must already be approved (a second,
# deliberate gate layered on top of the existing one-tap approve — see the
# plan's "Gate layering" decision), the requester must own the run, a
# repo-write token must be connected, and confirm must present the exact
# single-use token issued by the most recent preview. The actual git push +
# PR creation happens in tools/github_push_ops.py, which is never reachable
# from any LLM tool loop (see that module's docstring).
# ---------------------------------------------------------------------------

GITHUB_PUSH_ENABLED = os.getenv("GITHUB_PUSH_ENABLED", "").lower() in ("1", "true", "yes")
_PUSH_CONFIRM_TTL = 15 * 60  # seconds — how long a preview's confirm_token stays valid


def _push_confirm_key(coordination_id: str) -> str:
    return f"swarm:push_confirm:{coordination_id}"


@app.get("/v1/tasks/{coordination_id}/push/preview")
async def push_preview(coordination_id: str, request: Request):
    """Pure computation — proposes branch/PR title/body and issues a short-TTL
    confirm_token. No GitHub or git side effects."""
    if not GITHUB_PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="GitHub push is not enabled")

    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    import swarm_run_store
    import swarm_run_repo_store
    import github_push_tokens
    import github_push_audit_store

    run = swarm_run_store.get_run(coordination_id, owner_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    if run.get("approval_state") != "approved":
        raise HTTPException(status_code=409, detail="Approve the diff before requesting a push")

    repo = swarm_run_repo_store.get(coordination_id)
    if not repo or not repo.get("local_branch"):
        raise HTTPException(status_code=409, detail="This task has no pushable branch")

    if not github_push_tokens.get_status(owner_id):
        raise HTTPException(status_code=409, detail="Connect a GitHub push token in Settings first")

    remote_branch = repo["local_branch"]
    pr_title = (run.get("title") or coordination_id)[:200]
    pr_body = (run.get("summary") or "")[:60000] or f"Opened by Memex from task {coordination_id}."

    import secrets
    from utils.gpu_queue import get_redis_client
    token = secrets.token_urlsafe(24)
    try:
        get_redis_client().set(_push_confirm_key(coordination_id), token, ex=_PUSH_CONFIRM_TTL)
    except Exception as e:
        logger.error(f"[push_preview] Redis unavailable, cannot issue confirm_token: {e}")
        raise HTTPException(status_code=503, detail="Push confirmation is temporarily unavailable")

    github_push_audit_store.record(
        coordination_id, owner_id, "preview_shown",
        target_repo=repo["git_url"], target_branch=remote_branch, base_branch=repo["base_branch"],
    )

    return {
        "confirm_token": token,
        "git_url": repo["git_url"],
        "base_branch": repo["base_branch"],
        "branch": remote_branch,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "expires_in": _PUSH_CONFIRM_TTL,
    }


class PushConfirmRequest(BaseModel):
    confirm_token: str
    branch: str
    pr_title: str
    pr_body: str = ""
    base_branch: str


@app.post("/v1/tasks/{coordination_id}/push/confirm")
async def push_confirm(coordination_id: str, body: PushConfirmRequest, request: Request):
    """Executes the push + PR creation after validating every precondition."""
    if not GITHUB_PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="GitHub push is not enabled")

    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    import swarm_run_store
    import swarm_run_repo_store
    import github_push_tokens
    import github_push_audit_store

    run = swarm_run_store.get_run(coordination_id, owner_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    if run.get("approval_state") != "approved":
        raise HTTPException(status_code=409, detail="Approve the diff before pushing")

    repo = swarm_run_repo_store.get(coordination_id)
    if not repo or not repo.get("local_branch"):
        raise HTTPException(status_code=409, detail="This task has no pushable branch")

    token = github_push_tokens.get_token(owner_id)
    if not token:
        raise HTTPException(status_code=409, detail="Connect a GitHub push token in Settings first")

    from utils.gpu_queue import get_redis_client
    key = _push_confirm_key(coordination_id)
    try:
        client = get_redis_client()
        stored_token = client.get(key)
    except Exception as e:
        logger.error(f"[push_confirm] Redis unavailable, cannot validate confirm_token: {e}")
        raise HTTPException(status_code=503, detail="Push confirmation is temporarily unavailable")

    if not stored_token or stored_token != body.confirm_token:
        github_push_audit_store.record(
            coordination_id, owner_id, "confirm_attempted",
            target_repo=repo["git_url"], target_branch=body.branch, base_branch=body.base_branch,
            error="stale or invalid confirm_token",
        )
        raise HTTPException(status_code=409, detail="This push preview has expired — request a new one")

    # Single-use: consume immediately so a retried/duplicated request can't push twice.
    try:
        client.delete(key)
    except Exception:
        pass

    github_push_audit_store.record(
        coordination_id, owner_id, "confirm_attempted",
        target_repo=repo["git_url"], target_branch=body.branch, base_branch=body.base_branch,
    )

    bundle_data = swarm_run_repo_store.get_bundle(coordination_id)

    from tools.github_push_ops import push_and_open_pr, GithubPushError
    try:
        result = push_and_open_pr(
            coordination_id=coordination_id,
            bundle_data=bundle_data,
            local_branch=repo["local_branch"],
            git_url=repo["git_url"],
            remote_branch=body.branch,
            base_branch=body.base_branch,
            pr_title=body.pr_title,
            pr_body=body.pr_body,
            token=token,
        )
    except GithubPushError as e:
        github_push_audit_store.record(
            coordination_id, owner_id, "push_failed",
            target_repo=repo["git_url"], target_branch=body.branch, base_branch=body.base_branch,
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=str(e))

    github_push_audit_store.record(
        coordination_id, owner_id, "push_succeeded",
        target_repo=repo["git_url"], target_branch=body.branch, base_branch=body.base_branch,
        pr_number=result.get("pr_number"), pr_url=result.get("pr_url"),
    )
    return result


@app.get("/v1/tasks/{coordination_id}/push/status")
async def push_status(coordination_id: str, request: Request):
    """Poll the latest audit row — confirm touches the network and may take a few seconds."""
    owner_id = _resolve_owner_id(None, request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    import github_push_audit_store
    latest_row = github_push_audit_store.latest(coordination_id, owner_id)
    return latest_row or {"stage": None}


# ═══════════════════════════════════════════════════════════════════════════
# Conversation sync endpoints (cross-device persistence)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/v1/conversations")
async def conv_list(request: Request):
    """Return all conversations for the authenticated user."""
    owner_id = request.headers.get("X-authentik-username", "anonymous")
    try:
        from conversation_store import list_conversations
        return {"conversations": list_conversations(owner_id)}
    except Exception as exc:
        logger.error(f"[ConvSync] list failed for {owner_id}: {exc}")
        return {"conversations": [], "error": str(exc)}


@app.put("/v1/conversations/{conv_id}")
async def conv_upsert(conv_id: str, request: Request):
    """Save (create or update) a conversation for the authenticated user."""
    owner_id = request.headers.get("X-authentik-username", "anonymous")
    try:
        body = await request.json()
        if body.get("id") != conv_id:
            return {"ok": False, "error": "id mismatch"}
        from conversation_store import save_conversation
        save_conversation(owner_id, body)
        return {"ok": True}
    except Exception as exc:
        logger.error(f"[ConvSync] upsert failed for {owner_id}/{conv_id}: {exc}")
        return {"ok": False, "error": str(exc)}


@app.delete("/v1/conversations/{conv_id}")
async def conv_delete(conv_id: str, request: Request):
    """Delete a conversation for the authenticated user."""
    owner_id = request.headers.get("X-authentik-username", "anonymous")
    try:
        from conversation_store import delete_conversation
        delete_conversation(owner_id, conv_id)
        return {"ok": True}
    except Exception as exc:
        logger.error(f"[ConvSync] delete failed for {owner_id}/{conv_id}: {exc}")
        return {"ok": False, "error": str(exc)}


# ═══════════════════════════════════════════════════════════════════════════
# User preference sync (cross-device) — onboarding callouts, etc.
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/v1/prefs/onboarding")
async def prefs_onboarding_get(request: Request):
    """Return the feature-callout keys this user has dismissed."""
    owner_id = request.headers.get("X-authentik-username", "anonymous")
    try:
        from prefs_store import get_prefs
        data = get_prefs(owner_id, "onboarding")
        return {"seenFeatures": data.get("seenFeatures", [])}
    except Exception as exc:
        logger.error(f"[Prefs] onboarding get failed for {owner_id}: {exc}")
        return {"seenFeatures": [], "error": str(exc)}


@app.put("/v1/prefs/onboarding")
async def prefs_onboarding_put(request: Request):
    """Union the incoming seen set with the stored one (monotonic, never shrinks)."""
    owner_id = request.headers.get("X-authentik-username", "anonymous")
    try:
        import time
        from prefs_store import get_prefs, save_prefs
        body = await request.json()
        incoming = set(body.get("seenFeatures", []))
        existing = set(get_prefs(owner_id, "onboarding").get("seenFeatures", []))
        merged = sorted(existing | incoming)
        save_prefs(owner_id, "onboarding", {"seenFeatures": merged}, int(time.time() * 1000))
        return {"ok": True, "seenFeatures": merged}
    except Exception as exc:
        logger.error(f"[Prefs] onboarding put failed for {owner_id}: {exc}")
        return {"ok": False, "error": str(exc)}


@app.get("/v1/training/status")
async def training_status():
    """Summary stats: last run, dataset size, model versions, active A/B tests."""
    import json as _json
    from config import TEMPLATE_DB_URL
    result = {
        "last_run": None,
        "dataset_size": {"exported": 0, "synthetic": 0, "curated": 0},
        "active_ab_tests": 0,
        "model_versions": [],
        "active_run": None,
    }

    # If there's an in-memory active run, include it
    if _active_training["status"] == "running":
        result["active_run"] = {
            "run_id": _active_training["run_id"],
            "status": "running",
            "started_at": _active_training["started_at"],
        }

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Last training run
        cur.execute("""
            SELECT id, run_type, target_model, dataset_size, status,
                   metrics::text, started_at, completed_at, error_message
            FROM swarm.training_runs ORDER BY started_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            result["last_run"] = {
                "id": row[0], "run_type": row[1], "target_model": row[2],
                "dataset_size": row[3], "status": row[4],
                "metrics": _json.loads(row[5]) if row[5] else {},
                "started_at": row[6].isoformat() if row[6] else None,
                "completed_at": row[7].isoformat() if row[7] else None,
                "error_message": row[8],
            }

            # If DB reports a running row, prefer that as active run metadata.
            if row[4] == "running":
                result["active_run"] = {
                    "run_id": row[0],
                    "status": row[4],
                    "started_at": row[6].isoformat() if row[6] else None,
                    "run_type": row[1],
                    "target_model": row[2],
                    "dataset_size": row[3],
                }

        # Dataset counts
        try:
            from pathlib import Path as _Path
            from config import TRAINING_DATASET_DIR
            dataset_dir = _Path(TRAINING_DATASET_DIR)
            if dataset_dir.exists():
                exported = sum(1 for f in dataset_dir.glob("grpo_traces_*.jsonl")
                              for _ in open(f, encoding="utf-8"))
                synthetic = sum(1 for f in dataset_dir.glob("synthetic_*.jsonl")
                               for _ in open(f, encoding="utf-8"))
                curated = sum(1 for f in dataset_dir.glob("curated_*.jsonl")
                             if "_rejected" not in f.name
                             for _ in open(f, encoding="utf-8"))
                result["dataset_size"] = {"exported": exported, "synthetic": synthetic, "curated": curated}
        except Exception:
            pass

        # Model versions
        cur.execute("""
            SELECT id, base_model, version_tag, ollama_model_name, status,
                   COALESCE(avg_score, 0), COALESCE(total_invocations, 0), created_at
            FROM swarm.model_versions ORDER BY created_at DESC LIMIT 20
        """)
        for row in cur.fetchall():
            result["model_versions"].append({
                "id": row[0], "base_model": row[1], "version_tag": row[2],
                "ollama_model_name": row[3], "status": row[4],
                "avg_score": float(row[5]), "total_invocations": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
            })

        # A/B tests
        cur.execute("SELECT COUNT(*) FROM swarm.model_versions WHERE status = 'ab_testing'")
        result["active_ab_tests"] = cur.fetchone()[0]

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Training status DB query failed: {e}")

    return result


@app.get("/v1/training/runs")
async def training_runs(limit: int = 50):
    """Paginated list of past training runs."""
    import json as _json
    from config import TEMPLATE_DB_URL
    runs = []
    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, run_type, target_model, dataset_path, dataset_size,
                   status, metrics::text, started_at, completed_at, error_message
            FROM swarm.training_runs ORDER BY started_at DESC LIMIT %s
        """, (limit,))
        for row in cur.fetchall():
            runs.append({
                "id": row[0], "run_type": row[1], "target_model": row[2],
                "dataset_path": row[3], "dataset_size": row[4],
                "status": row[5],
                "metrics": _json.loads(row[6]) if row[6] else {},
                "started_at": row[7].isoformat() if row[7] else None,
                "completed_at": row[8].isoformat() if row[8] else None,
                "error_message": row[9],
            })
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Training runs query failed: {e}")
    return {"runs": runs}


@app.get("/v1/training/curated-datasets")
async def list_curated_datasets():
    """List available curated HuggingFace datasets for training."""
    from training.dataset_curator import CURATED_DATASETS
    return {
        "datasets": [
            {
                "key": key,
                "hf_id": meta["hf_id"],
                "description": meta["description"],
                "category": meta["category"],
                "default_max": meta["default_max"],
                "recommended_for": meta.get("recommended_for", []),
            }
            for key, meta in CURATED_DATASETS.items()
        ]
    }


@app.post("/v1/training/scan")
async def scan_dataset(dataset_path: str):
    """Scan an existing dataset file for training data poisoning."""
    import asyncio
    from training.dataset_curator import scan_existing_dataset
    try:
        report = await asyncio.to_thread(scan_existing_dataset, dataset_path)
        return report
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/training/start")
async def training_start(req: TrainingStartRequest, background_tasks: BackgroundTasks):
    """Launch a training run in the background."""
    from datetime import datetime

    if _active_training["status"] == "running":
        raise HTTPException(status_code=409, detail="A training run is already in progress")

    async def _run_training():
        import asyncio
        _early_run_id = None
        try:
            _active_training["status"] = "running"
            _active_training["started_at"] = datetime.utcnow().isoformat()

            # Create a DB row immediately so the run is visible in history
            try:
                from training.grpo_trainer import _record_training_run
                from config import TRAINING_BASE_SOLVER as _default_base
                _early_run_id = _record_training_run(
                    run_type=req.run_type or "training",
                    target_model=req.base_model or _default_base,
                    dataset_path=req.dataset_path or "pending",
                    dataset_size=0,
                    status="running",
                    config={"run_type": req.run_type, "time_budget_minutes": req.time_budget_minutes},
                )
                if _early_run_id:
                    _active_training["run_id"] = _early_run_id
                    logger.info(f"[Training] Created DB row {_early_run_id} for run_type={req.run_type}")
            except Exception as db_err:
                logger.warning(f"[Training] Failed to create early DB row: {db_err}")

            if req.run_type == "export":
                # Export traces only
                from training.export_traces import TraceExporter
                exporter = TraceExporter()
                count = await asyncio.to_thread(
                    exporter.export_dataset, template_id=req.template_id
                )
                # Mark the export-only run as completed in DB
                if _early_run_id:
                    try:
                        from training.grpo_trainer import _update_training_run
                        _update_training_run(_early_run_id, "completed", metrics={"traces_exported": count})
                    except Exception:
                        pass
                _active_training["status"] = "idle"
                logger.info(f"Export complete: {count} traces")

            elif req.run_type == "curated":
                # Download curated datasets → security scan → train
                from training.dataset_curator import DatasetCurator
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig, _update_training_run as _update_run
                from config import TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS

                ds_keys = req.curated_datasets or ["glaive-function-calling", "hermes-function-calling"]

                # Progressive update: dataset download phase
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "dataset_download",
                        "curated_datasets": ds_keys,
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                curator = DatasetCurator()
                curation_result = await asyncio.to_thread(
                    curator.download_and_convert,
                    dataset_keys=ds_keys,
                    max_samples=req.max_samples,
                    scan_security=True,
                )

                output_path = curation_result["output_path"]
                if curation_result["total_written"] == 0:
                    raise ValueError("No samples survived curation + security scanning")

                logger.info(
                    f"Curated {curation_result['total_written']} samples "
                    f"({curation_result['total_rejected']} rejected by security scan)"
                )

                # Progressive update: security scan done, moving to training
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "model_loading",
                        "dataset_path": output_path,
                        "dataset_size": curation_result["total_written"],
                        "rejected_samples": curation_result["total_rejected"],
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, output_path, cfg, _early_run_id)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            elif req.run_type == "synthetic":
                # Generate synthetic trajectories → security scan → train
                from training.synthetic_gen import SyntheticTrajectoryGenerator
                from training.dataset_curator import scan_existing_dataset
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig, _update_training_run as _update_run
                from config import TRAINING_DATASET_DIR, TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS

                target = req.synthetic_target or 552
                import time as _time_mod
                _phase_timings = {}

                # Progressive update: mark synthetic generation phase
                _t_synth_start = _time_mod.time()
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "synthetic_generation",
                        "target_trajectories": target,
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                gen = SyntheticTrajectoryGenerator(output_dir=TRAINING_DATASET_DIR)
                count = await asyncio.to_thread(
                    gen.generate_dataset, target_count=target
                )
                _phase_timings["synthetic_gen_sec"] = round(_time_mod.time() - _t_synth_start, 1)
                logger.info(f"Synthetic generation complete: {count} trajectories")

                if count == 0:
                    raise ValueError("Synthetic generation produced 0 trajectories")

                # Find the generated file and scan it
                import glob
                synth_files = sorted(
                    glob.glob(f"{TRAINING_DATASET_DIR}/synthetic_*.jsonl"),
                    reverse=True,
                )
                dataset_path = synth_files[0]

                # Progressive update: mark security scan phase
                _t_scan_start = _time_mod.time()
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "security_scan",
                        "dataset_path": dataset_path,
                        "dataset_size": count,
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                # Security scan the generated data
                scan_report = await asyncio.to_thread(scan_existing_dataset, dataset_path)
                _phase_timings["security_scan_sec"] = round(_time_mod.time() - _t_scan_start, 1)
                blocked = scan_report["scan_summary"].get("blocked", 0)
                if blocked > 0:
                    logger.warning(f"Security scan found {blocked} blocked samples in synthetic data")

                # Progressive update: mark training phase
                _t_train_start = _time_mod.time()
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "model_loading",
                        "dataset_path": dataset_path,
                        "dataset_size": count,
                        "blocked_samples": blocked,
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                        "phase_timings": _phase_timings,
                    })

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, dataset_path, cfg, _early_run_id)
                _phase_timings["training_sec"] = round(_time_mod.time() - _t_train_start, 1)
                # Store final phase timings
                if _early_run_id:
                    _update_run(_early_run_id, "completed", metrics={
                        "phase": "completed",
                        "phase_timings": _phase_timings,
                    })
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            elif req.run_type == "full_pipeline":
                # Export → Train
                from training.export_traces import TraceExporter
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig, _update_training_run as _update_run
                from config import TRAINING_DATASET_DIR, TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS
                import glob

                # Progressive update: export phase
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "exporting_traces",
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                exporter = TraceExporter()
                await asyncio.to_thread(
                    exporter.export_dataset, template_id=req.template_id
                )

                # Find latest dataset
                datasets_found = sorted(
                    glob.glob(f"{TRAINING_DATASET_DIR}/grpo_traces_*.jsonl"),
                    reverse=True,
                )
                if not datasets_found:
                    raise ValueError("No dataset found after export")

                # Progressive update: model loading phase
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "model_loading",
                        "dataset_path": datasets_found[0],
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, datasets_found[0], cfg, _early_run_id)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            else:
                # Training only — use specified or latest dataset
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig, _update_training_run as _update_run
                from config import TRAINING_DATASET_DIR, TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS
                import glob

                dataset = req.dataset_path
                if not dataset:
                    datasets_found = sorted(
                        glob.glob(f"{TRAINING_DATASET_DIR}/grpo_traces_*.jsonl"),
                        reverse=True,
                    )
                    if not datasets_found:
                        raise ValueError("No training dataset found")
                    dataset = datasets_found[0]

                # Progressive update: model loading phase
                if _early_run_id:
                    _update_run(_early_run_id, "running", metrics={
                        "phase": "model_loading",
                        "dataset_path": dataset,
                        "target_model": req.base_model or TRAINING_BASE_SOLVER,
                    })

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, dataset, cfg, _early_run_id)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

        except BaseException as e:
            logger.error(f"Background training failed: {e!r}", exc_info=True)
            if _early_run_id:
                try:
                    from training.grpo_trainer import _update_training_run
                    _update_training_run(_early_run_id, "failed", error=f"{type(e).__name__}: {e}")
                except Exception as db_err:
                    logger.warning(f"[Training] Failed to mark DB row {_early_run_id} as failed: {db_err}")
            raise
        finally:
            # Guarantee the in-memory lock is released, regardless of how we exited.
            _active_training["status"] = "idle"
            _active_training["run_id"] = None
            _active_training["task"] = None

    import asyncio as _asyncio
    task = _asyncio.create_task(_run_training())
    _active_training["task"] = task
    return {"status": "started", "run_type": req.run_type, "time_budget_minutes": req.time_budget_minutes}


@app.post("/v1/training/cancel")
async def training_cancel():
    """Force-cancel a stuck training run by resetting the in-memory lock."""
    prev_status = _active_training["status"]
    prev_run_id = _active_training["run_id"]
    # Mark DB row as cancelled if one exists
    if prev_run_id:
        try:
            from training.grpo_trainer import _update_training_run
            _update_training_run(prev_run_id, "failed", error="Cancelled by user")
        except Exception:
            pass
    _active_training["status"] = "idle"
    _active_training["run_id"] = None
    _active_training["started_at"] = None
    _active_training["task"] = None
    logger.warning(f"[Training] Force-cancelled: was status={prev_status}, run_id={prev_run_id}")
    return {"status": "cancelled", "previous_status": prev_status, "previous_run_id": prev_run_id}


@app.get("/v1/training/runs/{run_id}/live")
async def training_run_live(run_id: int):
    """Return real-time training metrics by reading Prometheus gauges + DB row.

    This endpoint is polled by the UI every 5 seconds for running runs.
    It combines in-memory Prometheus gauge values (updated every step) with
    the latest DB heartbeat so the UI can show live step count, loss, ETA, etc.
    """
    import json as _json
    from config import TEMPLATE_DB_URL

    # 1. Read Prometheus gauges (in-process, fast)
    prom = {}
    try:
        from metrics import (
            TRAINING_IS_ACTIVE, TRAINING_STEP_CURRENT, TRAINING_EPOCH_CURRENT,
            TRAINING_TOTAL_STEPS, TRAINING_LOSS, TRAINING_GRAD_NORM,
            TRAINING_LEARNING_RATE, TRAINING_REWARD_MEAN, TRAINING_REWARD_STD,
            TRAINING_STEP_TIME, TRAINING_ENTROPY, TRAINING_PHASE,
            TRAINING_TIME_BUDGET_SEC, TRAINING_BUDGET_START, TRAINING_RUN_ID,
            PHASE_NAMES,
        )
        prom = {
            "is_active": TRAINING_IS_ACTIVE._value.get(),
            "current_step": int(TRAINING_STEP_CURRENT._value.get()),
            "total_steps": int(TRAINING_TOTAL_STEPS._value.get()),
            "current_epoch": round(TRAINING_EPOCH_CURRENT._value.get(), 4),
            "loss": round(TRAINING_LOSS._value.get(), 6) if TRAINING_LOSS._value.get() else None,
            "grad_norm": round(TRAINING_GRAD_NORM._value.get(), 4) if TRAINING_GRAD_NORM._value.get() else None,
            "learning_rate": TRAINING_LEARNING_RATE._value.get() or None,
            "reward_mean": round(TRAINING_REWARD_MEAN._value.get(), 4) if TRAINING_REWARD_MEAN._value.get() else None,
            "reward_std": round(TRAINING_REWARD_STD._value.get(), 4) if TRAINING_REWARD_STD._value.get() else None,
            "step_time_sec": round(TRAINING_STEP_TIME._value.get(), 2) if TRAINING_STEP_TIME._value.get() else None,
            "entropy": round(TRAINING_ENTROPY._value.get(), 4) if TRAINING_ENTROPY._value.get() else None,
            "phase_ordinal": int(TRAINING_PHASE._value.get()),
            "phase": PHASE_NAMES.get(int(TRAINING_PHASE._value.get()), "unknown"),
            "time_budget_sec": TRAINING_TIME_BUDGET_SEC._value.get() or None,
            "budget_start_epoch": TRAINING_BUDGET_START._value.get() or None,
            "prom_run_id": int(TRAINING_RUN_ID._value.get()) if TRAINING_RUN_ID._value.get() else None,
        }
    except Exception as e:
        logger.debug(f"[Live] Prometheus gauge read failed: {e}")

    # 2. Read latest DB metrics for this run
    db_metrics = {}
    db_status = None
    db_started_at = None
    db_config = {}
    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT status, metrics::text, config::text, started_at
            FROM swarm.training_runs WHERE id = %s
        """, (run_id,))
        row = cur.fetchone()
        if row:
            db_status = row[0]
            db_metrics = _json.loads(row[1]) if row[1] else {}
            db_config = _json.loads(row[2]) if row[2] else {}
            db_started_at = row[3].isoformat() if row[3] else None
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"[Live] DB read failed for run {run_id}: {e}")

    if db_status is None:
        raise HTTPException(status_code=404, detail=f"Training run {run_id} not found")

    # 3. Merge — prefer Prometheus (real-time) over DB (heartbeat lag)
    current_step = prom.get("current_step") or db_metrics.get("current_step", 0)
    total_steps = prom.get("total_steps") or db_metrics.get("total_steps", 0)
    step_time = prom.get("step_time_sec") or db_metrics.get("step_time_sec")
    loss = prom.get("loss") or db_metrics.get("loss")
    reward_mean = prom.get("reward_mean") or db_metrics.get("reward_mean")
    reward_std = prom.get("reward_std") or db_metrics.get("reward_std")
    entropy = prom.get("entropy") or db_metrics.get("entropy")
    phase = prom.get("phase") if prom.get("phase") != "unknown" else db_metrics.get("phase", "unknown")
    current_epoch = prom.get("current_epoch") or db_metrics.get("current_epoch", 0)
    total_epochs = db_config.get("num_epochs") or db_metrics.get("num_epochs")

    # 4. ETA calculation
    import time as _time
    elapsed_sec = None
    if db_started_at:
        from datetime import datetime
        started_dt = datetime.fromisoformat(db_started_at)
        elapsed_sec = (_time.time() - started_dt.timestamp())

    eta_sec = None
    budget_remaining_sec = None
    if step_time and total_steps and current_step < total_steps:
        eta_sec = round((total_steps - current_step) * step_time, 1)
    budget_sec = prom.get("time_budget_sec") or db_config.get("time_budget_minutes")
    if budget_sec:
        # If from config it's minutes, convert
        if budget_sec == db_config.get("time_budget_minutes"):
            budget_sec = budget_sec * 60
        budget_start = prom.get("budget_start_epoch")
        if budget_start:
            budget_remaining_sec = round(budget_sec - (_time.time() - budget_start), 1)
            if budget_remaining_sec < 0:
                budget_remaining_sec = 0
            # ETA is min of step-based and budget-based
            if eta_sec is not None and budget_remaining_sec is not None:
                eta_sec = min(eta_sec, budget_remaining_sec)
            elif budget_remaining_sec is not None:
                eta_sec = budget_remaining_sec

    return {
        "run_id": run_id,
        "status": db_status,
        "phase": phase,
        "current_step": current_step,
        "total_steps": total_steps,
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "loss": loss,
        "grad_norm": prom.get("grad_norm"),
        "learning_rate": prom.get("learning_rate"),
        "reward_mean": reward_mean,
        "reward_std": reward_std,
        "entropy": entropy,
        "step_time_sec": step_time,
        "elapsed_sec": round(elapsed_sec, 1) if elapsed_sec else None,
        "eta_sec": eta_sec,
        "time_budget_sec": prom.get("time_budget_sec") or (db_config.get("time_budget_minutes", 0) * 60 if db_config.get("time_budget_minutes") else None),
        "budget_remaining_sec": budget_remaining_sec,
        "target_model": db_metrics.get("target_model"),
        "dataset_size": db_metrics.get("dataset_size"),
        "dataset_path": db_metrics.get("dataset_path"),
    }


@app.get("/v1/training/runs/{run_id}/report")
async def training_run_report(run_id: int):
    """Generate a structured post-training report for a completed run."""
    import json as _json
    from config import TEMPLATE_DB_URL

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Fetch the run
        cur.execute("""
            SELECT id, run_type, target_model, dataset_path, dataset_size,
                   status, config::text, metrics::text, started_at, completed_at,
                   error_message
            FROM swarm.training_runs WHERE id = %s
        """, (run_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Training run {run_id} not found")

        run = {
            "id": row[0], "run_type": row[1], "target_model": row[2],
            "dataset_path": row[3], "dataset_size": row[4], "status": row[5],
            "config": _json.loads(row[6]) if row[6] else {},
            "metrics": _json.loads(row[7]) if row[7] else {},
            "started_at": row[8].isoformat() if row[8] else None,
            "completed_at": row[9].isoformat() if row[9] else None,
            "error_message": row[10],
        }

        # Calculate durations
        duration_sec = None
        if row[8] and row[9]:
            duration_sec = (row[9] - row[8]).total_seconds()

        metrics = run["metrics"]
        train_runtime = metrics.get("train_runtime", 0)
        overhead_sec = (duration_sec - train_runtime) if duration_sec and train_runtime else None

        # Check if a model version was created from this run
        model_version = None
        adapter_path = metrics.get("adapter_path", "")
        if adapter_path:
            cur.execute("""
                SELECT id, version_tag, ollama_model_name, status,
                       COALESCE(avg_score, 0), COALESCE(total_invocations, 0)
                FROM swarm.model_versions
                WHERE adapter_path = %s OR adapter_path LIKE %s
                ORDER BY created_at DESC LIMIT 1
            """, (adapter_path, f"%{adapter_path.split('/')[-1]}%"))
            mv_row = cur.fetchone()
            if mv_row:
                model_version = {
                    "id": mv_row[0], "version_tag": mv_row[1],
                    "ollama_model_name": mv_row[2], "status": mv_row[3],
                    "avg_score": float(mv_row[4]), "total_invocations": mv_row[5],
                }

        # Check for A/B test associated with this model
        ab_test = None
        if model_version:
            cur.execute("""
                SELECT id, candidate_model, base_model, traffic_split,
                       status, winner,
                       (SELECT COUNT(*) FROM swarm.ab_test_results WHERE test_id = t.id) as result_count,
                       (SELECT AVG(score) FROM swarm.ab_test_results WHERE test_id = t.id AND model_used = t.candidate_model) as candidate_avg,
                       (SELECT AVG(score) FROM swarm.ab_test_results WHERE test_id = t.id AND model_used = t.base_model) as base_avg
                FROM swarm.ab_tests t
                WHERE candidate_model = %s
                ORDER BY created_at DESC LIMIT 1
            """, (model_version.get("ollama_model_name") or model_version.get("version_tag"),))
            ab_row = cur.fetchone()
            if ab_row:
                ab_test = {
                    "id": ab_row[0], "candidate_model": ab_row[1],
                    "base_model": ab_row[2], "traffic_split": float(ab_row[3]) if ab_row[3] else None,
                    "status": ab_row[4], "winner": ab_row[5],
                    "result_count": ab_row[6],
                    "candidate_avg_score": float(ab_row[7]) if ab_row[7] else None,
                    "base_avg_score": float(ab_row[8]) if ab_row[8] else None,
                }

        cur.close()
        conn.close()

        # Build the report
        report = {
            "run_id": run["id"],
            "status": run["status"],
            "run_type": run["run_type"],
            "phase": metrics.get("phase"),  # Progressive pipeline phase

            "timing": {
                "started_at": run["started_at"],
                "completed_at": run["completed_at"],
                "total_wall_clock_sec": round(duration_sec, 1) if duration_sec else None,
                "active_training_sec": round(train_runtime, 1) if train_runtime else None,
                "overhead_sec": round(overhead_sec, 1) if overhead_sec else None,
                "overhead_note": "Model loading, quantization, dataset preparation",
                "phase_timings": metrics.get("phase_timings"),
            },

            "dataset": {
                "path": metrics.get("dataset_path") or run["dataset_path"],
                "total_samples": metrics.get("dataset_size") or run["dataset_size"],
                "training_examples": metrics.get("train_samples"),
            },

            "model": {
                "base_model": metrics.get("target_model") or metrics.get("base_model") or run["target_model"],
                "trainable_params": metrics.get("trainable_params"),
                "total_params": metrics.get("total_params"),
                "trainable_pct": metrics.get("trainable_pct"),
            },

            "hyperparameters": {
                "lora_rank": metrics.get("lora_rank"),
                "lora_alpha": metrics.get("lora_alpha"),
                "learning_rate": metrics.get("learning_rate"),
                "batch_size": metrics.get("batch_size"),
                "gradient_accumulation": metrics.get("gradient_accumulation"),
                "max_seq_len": metrics.get("max_seq_len"),
                "num_epochs": metrics.get("num_epochs"),
                "time_budget_minutes": metrics.get("time_budget_minutes"),
                "budget_limited": metrics.get("budget_limited"),
            },

            "results": {
                "final_loss": metrics.get("train_loss"),
                "train_samples_per_second": metrics.get("train_samples_per_second"),
                "train_steps_per_second": metrics.get("train_steps_per_second"),
                "adapter_path": metrics.get("adapter_path"),
            },

            "deployment": {
                "model_version": model_version,
                "ab_test": ab_test,
            },

            "error": run["error_message"],
        }

        # For running runs, populate live metrics from Prometheus gauges
        if run["status"] == "running":
            live = None
            try:
                from metrics import (
                    TRAINING_STEP_CURRENT, TRAINING_EPOCH_CURRENT,
                    TRAINING_TOTAL_STEPS, TRAINING_LOSS, TRAINING_REWARD_MEAN,
                    TRAINING_REWARD_STD, TRAINING_STEP_TIME, TRAINING_ENTROPY,
                    TRAINING_PHASE, TRAINING_TIME_BUDGET_SEC, TRAINING_BUDGET_START,
                    PHASE_NAMES,
                )
                import time as _time
                current_step = int(TRAINING_STEP_CURRENT._value.get())
                total_steps_val = int(TRAINING_TOTAL_STEPS._value.get())
                step_time_val = TRAINING_STEP_TIME._value.get()
                budget_sec = TRAINING_TIME_BUDGET_SEC._value.get()
                budget_start = TRAINING_BUDGET_START._value.get()

                # Compute elapsed and ETA
                elapsed_sec = None
                if row[8]:
                    elapsed_sec = round((_time.time() - row[8].timestamp()), 1)
                eta_sec = None
                if step_time_val and total_steps_val and current_step < total_steps_val:
                    eta_sec = round((total_steps_val - current_step) * step_time_val, 1)
                budget_remaining = None
                if budget_sec and budget_start:
                    budget_remaining = round(budget_sec - (_time.time() - budget_start), 1)
                    if budget_remaining < 0:
                        budget_remaining = 0
                    if eta_sec is not None:
                        eta_sec = min(eta_sec, budget_remaining)
                    else:
                        eta_sec = budget_remaining

                live = {
                    "phase": PHASE_NAMES.get(int(TRAINING_PHASE._value.get()), metrics.get("phase")),
                    "current_step": current_step,
                    "total_steps": total_steps_val or metrics.get("total_steps"),
                    "current_epoch": round(TRAINING_EPOCH_CURRENT._value.get(), 4),
                    "total_epochs": metrics.get("num_epochs"),
                    "loss": round(TRAINING_LOSS._value.get(), 6) if TRAINING_LOSS._value.get() else None,
                    "reward_mean": round(TRAINING_REWARD_MEAN._value.get(), 4) if TRAINING_REWARD_MEAN._value.get() else None,
                    "reward_std": round(TRAINING_REWARD_STD._value.get(), 4) if TRAINING_REWARD_STD._value.get() else None,
                    "entropy": round(TRAINING_ENTROPY._value.get(), 4) if TRAINING_ENTROPY._value.get() else None,
                    "step_time_sec": round(step_time_val, 2) if step_time_val else None,
                    "elapsed_sec": elapsed_sec,
                    "eta_sec": eta_sec,
                    "budget_remaining_sec": budget_remaining,
                }
            except Exception as live_err:
                logger.debug(f"[Report] Live metrics unavailable: {live_err}")
                # Fall back to DB heartbeat metrics
                live = {
                    "phase": metrics.get("phase"),
                    "current_step": metrics.get("current_step"),
                    "total_steps": metrics.get("total_steps"),
                    "current_epoch": metrics.get("current_epoch"),
                    "total_epochs": metrics.get("num_epochs"),
                    "loss": metrics.get("loss"),
                    "reward_mean": metrics.get("reward_mean"),
                    "reward_std": metrics.get("reward_std"),
                    "step_time_sec": metrics.get("step_time_sec"),
                }
            report["live"] = live

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Training report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Convert & Deploy API
# ---------------------------------------------------------------------------

class ConvertRequest(BaseModel):
    """Request body for /v1/training/convert."""
    model_config = ConfigDict(extra="allow")
    training_run_id: int
    base_model: Optional[str] = None
    system_prompt: Optional[str] = None


class DeployRequest(BaseModel):
    """Request body for /v1/training/deploy."""
    model_config = ConfigDict(extra="allow")
    training_run_id: int
    template_id: str
    traffic_split: float = 0.2
    min_invocations: int = 100


@app.post("/v1/training/convert")
async def start_conversion(req: ConvertRequest, background_tasks: BackgroundTasks):
    """Launch LoRA merge + Ollama import as a background task."""
    # Reuse the _active_training guard (GPU/disk contention)
    if _active_training["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"A task is already running (run_id={_active_training['run_id']}). Wait for it to finish."
        )

    from training.convert_gguf import run_convert
    from config import TRAINING_BASE_SOLVER

    async def _run_conversion():
        try:
            _active_training["status"] = "running"
            _active_training["run_id"] = f"convert-{req.training_run_id}"
            _active_training["started_at"] = __import__("datetime").datetime.utcnow().isoformat()
            report = run_convert(
                training_run_id=req.training_run_id,
                base_model=req.base_model or TRAINING_BASE_SOLVER,
                system_prompt=req.system_prompt,
            )
            _active_training["status"] = "idle"
            _active_training["last_report"] = report
            logger.info(f"Conversion finished: {report['status']}")
        except Exception as e:
            _active_training["status"] = "idle"
            logger.error(f"Conversion background task failed: {e}", exc_info=True)

    background_tasks.add_task(_run_conversion)
    return {"status": "started", "training_run_id": req.training_run_id}


@app.post("/v1/training/deploy")
async def start_deploy(req: DeployRequest):
    """Start an A/B test for a converted model. Synchronous (fast DB operation)."""
    from training.convert_gguf import run_deploy

    report = run_deploy(
        training_run_id=req.training_run_id,
        template_id=req.template_id,
        traffic_split=req.traffic_split,
        min_invocations=req.min_invocations,
    )

    if report["status"] == "failed":
        raise HTTPException(status_code=400, detail=report["error"])

    return report


@app.get("/v1/training/runs/{run_id}/convert-report")
async def convert_report(run_id: int):
    """Fetch conversion report for a training run."""
    import json as _json
    from config import TEMPLATE_DB_URL

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Find conversion run that references this source training run
        cur.execute("""
            SELECT id, status, metrics::text, config::text, started_at, completed_at, error_message
            FROM swarm.training_runs
            WHERE run_type = 'conversion' AND config::text LIKE %s
            ORDER BY id DESC LIMIT 1
        """, (f'%"source_run_id": {run_id}%',))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No conversion found for this run")

        conv_metrics = _json.loads(row[2]) if row[2] else {}
        conv_config = _json.loads(row[3]) if row[3] else {}

        # Get model version info
        model_version = None
        version_id = conv_metrics.get("version_id")
        if version_id:
            cur.execute("""
                SELECT id, version_tag, ollama_model_name, status,
                       COALESCE(avg_score, 0), COALESCE(total_invocations, 0)
                FROM swarm.model_versions WHERE id = %s
            """, (version_id,))
            mv_row = cur.fetchone()
            if mv_row:
                model_version = {
                    "id": mv_row[0], "version_tag": mv_row[1],
                    "ollama_model_name": mv_row[2], "status": mv_row[3],
                    "avg_score": float(mv_row[4]), "total_invocations": mv_row[5],
                }

        cur.close()
        conn.close()

        duration_sec = None
        if row[4] and row[5]:
            duration_sec = (row[5] - row[4]).total_seconds()

        return {
            "source_run_id": run_id,
            "conversion_run_id": row[0],
            "status": row[1],
            "method": conv_metrics.get("method"),
            "timing": {
                "total_sec": conv_metrics.get("total_sec") or (round(duration_sec, 1) if duration_sec else None),
                "merge_sec": conv_metrics.get("merge_sec"),
                "convert_sec": conv_metrics.get("convert_sec"),
                "ollama_import_sec": conv_metrics.get("ollama_import_sec"),
            },
            "ollama": {
                "model_name": conv_metrics.get("ollama_name") or conv_config.get("ollama_name"),
                "verified": conv_metrics.get("verified"),
            },
            "model_version": model_version,
            "warnings": conv_metrics.get("warnings", []),
            "error": row[6],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Convert report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/training/runs/{run_id}/deploy-report")
async def deploy_report(run_id: int):
    """Fetch live A/B test report for a training run's deployed model."""
    import json as _json
    from config import TEMPLATE_DB_URL

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()

        # Find model version for this training run
        cur.execute("""
            SELECT id, ollama_model_name, version_tag, status
            FROM swarm.model_versions
            WHERE training_run_id = %s
            ORDER BY id DESC LIMIT 1
        """, (run_id,))
        mv = cur.fetchone()
        if not mv:
            raise HTTPException(status_code=404, detail="No model version found for this run")

        version_id, candidate_model, version_tag, mv_status = mv

        # Find A/B test for this candidate
        cur.execute("""
            SELECT id, template_id, candidate_model, base_model, traffic_split,
                   min_invocations, status, winner, started_at, concluded_at
            FROM swarm.ab_tests
            WHERE candidate_model = %s
            ORDER BY id DESC LIMIT 1
        """, (candidate_model,))
        ab_row = cur.fetchone()

        if not ab_row:
            cur.close()
            conn.close()
            return {
                "source_run_id": run_id,
                "status": "not_deployed",
                "model_version": {
                    "id": version_id, "ollama_model_name": candidate_model,
                    "version_tag": version_tag, "status": mv_status,
                },
                "test": None,
            }

        test_id = ab_row[0]

        # Get result counts and averages
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE model_used = %s) as n_candidate,
                COUNT(*) FILTER (WHERE model_used = %s) as n_base,
                AVG(score) FILTER (WHERE model_used = %s) as avg_candidate,
                AVG(score) FILTER (WHERE model_used = %s) as avg_base,
                COUNT(*) as total
            FROM swarm.ab_test_results WHERE test_id = %s
        """, (ab_row[2], ab_row[3], ab_row[2], ab_row[3], test_id))
        stats = cur.fetchone()

        # Try to evaluate the test
        evaluation = None
        try:
            from training.ab_test import ABTestManager
            mgr = ABTestManager()
            evaluation = mgr.evaluate_test(test_id)
        except Exception:
            pass

        cur.close()
        conn.close()

        n_candidate = stats[0] or 0
        n_base = stats[1] or 0
        avg_candidate = float(stats[2]) if stats[2] else None
        avg_base = float(stats[3]) if stats[3] else None

        improvement = None
        if avg_candidate is not None and avg_base is not None and avg_base > 0:
            improvement = round((avg_candidate - avg_base) / avg_base * 100, 2)

        return {
            "source_run_id": run_id,
            "status": ab_row[6],  # active / concluded
            "model_version": {
                "id": version_id, "ollama_model_name": candidate_model,
                "version_tag": version_tag, "status": mv_status,
            },
            "test": {
                "id": test_id,
                "template_id": ab_row[1],
                "candidate_model": ab_row[2],
                "base_model": ab_row[3],
                "traffic_split": float(ab_row[4]) if ab_row[4] else None,
                "min_invocations": ab_row[5],
                "status": ab_row[6],
                "winner": ab_row[7],
                "started_at": ab_row[8].isoformat() if ab_row[8] else None,
                "concluded_at": ab_row[9].isoformat() if ab_row[9] else None,
            },
            "results": {
                "n_candidate": n_candidate,
                "n_base": n_base,
                "total_samples": n_candidate + n_base,
                "candidate_avg_score": round(avg_candidate, 4) if avg_candidate else None,
                "base_avg_score": round(avg_base, 4) if avg_base else None,
                "improvement_pct": improvement,
                "p_value": evaluation.get("p_value") if evaluation else None,
            },
            "evaluation": evaluation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Deploy report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ART STUDIO API
# ═══════════════════════════════════════════════════════════════════════════════

class ImageGenRequest(BaseModel):
    prompt: str
    model_name: str = "auto"
    cfg: float = 7.0
    steps: int = 20
    width: int = 1024
    height: int = 1024
    sampler: str = "euler"
    scheduler: str = "normal"
    seed: int = -1
    gpu_context: str = "image"

class ImageSearchRequest(BaseModel):
    query: str

class ThreeDGenRequest(BaseModel):
    prompt: str
    workflow: str = "workflow_triposg.json"
    auto_concept: bool = True
    steps: int = 0        # 0 = use workflow default
    cfg: float = 0.0      # 0 = use workflow default
    quality: str = "high" # fast | balanced | high

class ActionFigureRequest(BaseModel):
    prompt: str
    workflow: str = "workflow_triposg.json"
    target_height: float = 150.0
    clearance: float = 0.3

# ── Art Studio async job queue ──────────────────────────────────────────────
# All generation runs in background; clients poll GET /v1/art/jobs/{id}
import asyncio as _art_asyncio

from media_job_store import (
    create_art_job as _store_create_art_job,
    finish_art_job as _store_finish_art_job,
    get_art_job as _store_get_art_job,
    update_art_job as _store_update_art_job,
    create_image_training_run as _store_create_image_training_run,
    get_image_training_run as _store_get_image_training_run,
)
from workspace_paths import resolve_workspace_path

def _art_job_create(mode: str, prompt: str) -> str:
    return _store_create_art_job(mode, prompt)


def _art_job_update(job_id: str, **fields):
    return _store_update_art_job(job_id, **fields)

def _art_job_finish(job_id: str, status: str, result: str):
    _store_finish_art_job(job_id, status, result)

@app.get("/v1/art/jobs/{job_id}")
async def art_job_status(job_id: str):
    """Poll for generation job status."""
    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/v1/art/models")
async def list_art_models():
    """List curated image profiles plus raw ComfyUI checkpoints."""
    try:
        from specialized.image_gen import get_image_model_catalog
        return get_image_model_catalog()
    except Exception as e:
        logger.warning(f"Failed to list art models: {e}")
        return {"models": [], "profiles": [], "checkpoints": []}

@app.post("/v1/art/generate/image")
async def art_generate_image(req: ImageGenRequest):
    """Queue an image generation job. Returns job_id for polling."""
    job_id = _art_job_create("image", req.prompt)

    async def _run():
        try:
            from specialized.image_gen import generate_image
            result = await _art_asyncio.to_thread(
                generate_image,
                prompt=req.prompt,
                model_name=req.model_name,
                cfg=req.cfg,
                steps=req.steps,
                width=req.width,
                height=req.height,
                sampler=req.sampler,
                scheduler=req.scheduler,
                seed=req.seed,
                gpu_context=req.gpu_context,
            )
            status = "error" if result.startswith("Error") or result.startswith("Failed") else "ok"
            _art_job_finish(job_id, status, result)
        except Exception as e:
            logger.error(f"Art Studio image gen failed: {e}")
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}


def _is_public_image_url(url: str) -> bool:
    """Reject non-HTTP URLs and private/reserved destinations before downloading."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except (OSError, ValueError):
        return False


def _search_and_cache_web_image(query: str) -> str:
    """Find one moderated Internet image, cache it as an artifact, and preserve its source."""
    try:
        from ddgs import DDGS
    except ImportError as exc:
        return f"Error: Internet image search is unavailable: {exc}"

    safe_query = (query or "").strip()
    if not safe_query:
        return "Error: no Internet image search query was supplied."
    try:
        results = DDGS().images(safe_query, max_results=8, safesearch="moderate")
        for result in results or []:
            image_url = str(result.get("image") or "")
            if not _is_public_image_url(image_url):
                logger.info("Internet image candidate skipped: non-public or unsupported URL")
                continue
            try:
                response = _httpx.get(
                    image_url,
                    timeout=15.0,
                    follow_redirects=False,
                    headers={"User-Agent": "Friday image delivery/1.0"},
                )
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if response.status_code != 200 or not content_type.startswith("image/"):
                    logger.info(
                        "Internet image candidate skipped: status=%s content_type=%s",
                        response.status_code, content_type or "missing",
                    )
                    continue
                if len(response.content) > 10 * 1024 * 1024:
                    continue
                # Keep visual verification off Lovelace.  Moondream is reliable at
                # describing images but not at returning a bare numeric answer, so
                # derive an auditable score from its description rather than trusting
                # a model-generated number.
                confidence = None
                try:
                    verdict = _httpx.post(
                        "http://192.168.2.103:11434/api/generate",
                        timeout=50.0,
                        json={
                            "model": "moondream",
                            "stream": False,
                            # Image lookup is occasional; do not reserve Turing VRAM
                            # after the one verification request completes.
                            "keep_alive": "0",
                            "prompt": "Describe this image in one short sentence.",
                            "images": [base64.b64encode(response.content).decode("ascii")],
                        },
                    )
                    description = verdict.json().get("response", "") if verdict.status_code == 200 else ""
                    # Moondream is reliable at descriptions but not constrained yes/no
                    # replies. Normalize simple singular/plural forms before matching so
                    # an accurate caption such as "penguins" satisfies "penguin".
                    def _vision_match_token(word: str) -> str:
                        if word.endswith("ies") and len(word) > 4:
                            return word[:-3] + "y"
                        if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
                            return word[:-1]
                        return word
                    request_words = {
                        _vision_match_token(word) for word in re.findall(r"[a-z]{3,}", safe_query.lower())
                        if word not in {"image", "picture", "photo", "from", "with", "that", "this", "the", "and", "for"}
                    }
                    description_words = {
                        _vision_match_token(word)
                        for word in re.findall(r"[a-z]{3,}", str(description).lower())
                    }
                    if request_words and description_words:
                        matched_words = sum(word in description_words for word in request_words)
                        confidence = round(100 * matched_words / len(request_words))
                except Exception as exc:
                    logger.info("Internet image visual verification unavailable: %s", type(exc).__name__)
                extension = {
                    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                }.get(content_type, ".img")
                filename = f"web_{uuid.uuid4().hex}{extension}"
                delivery_dir = "/workspace/delivered_artifacts"
                os.makedirs(delivery_dir, exist_ok=True)
                with open(os.path.join(delivery_dir, filename), "wb") as image_file:
                    image_file.write(response.content)
                source_url = str(result.get("url") or image_url)
                confidence_note = f" | Visual confidence: {confidence}%" if confidence is not None else ""
                return f"Generated Image: {filename} | Source: {source_url}{confidence_note}"
            except Exception as exc:  # try the next search candidate
                logger.info(f"Internet image candidate skipped: {type(exc).__name__}")
        return "Error: no safe downloadable Internet image was found."
    except Exception as exc:
        logger.warning(f"Internet image search failed: {exc}")
        return f"Error: Internet image search failed: {type(exc).__name__}"


@app.post("/v1/art/search/image")
async def art_search_image(req: ImageSearchRequest):
    """Queue a moderated Internet-image search and cache the selected image for delivery."""
    job_id = _art_job_create("image_search", req.query)

    async def _run():
        try:
            result = await _art_asyncio.to_thread(_search_and_cache_web_image, req.query)
            _art_job_finish(job_id, "error" if result.startswith("Error:") else "ok", result)
        except Exception as exc:
            logger.error(f"Art Studio Internet image search failed: {exc}")
            _art_job_finish(job_id, "error", str(exc))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}


# ── Scene Composer (complex-scene decomposition + OmniGen2 composite) ───────
# UX pattern: card grid analogous to swarm panel. Each card = one image asset.
# Parent job tracks the cards list; children are regular art jobs.

class SceneStartRequest(BaseModel):
    prompt: str
    engine: str = "omnigen"  # "omnigen" | "flux-inpaint" (future)


def _scene_resolve_workspace_image_path(filename: str) -> str | None:
    """Locate a delivered image by filename. Mirrors the lookup used elsewhere
    in main.py for serving art assets."""
    for base in (
        "/tmp/comfyui_images",
        os.getenv("COMFYUI_OUTPUT_DIR"),
        "/app/comfy_io/output",
    ):
        if not base:
            continue
        candidate = os.path.join(base, filename)
        if os.path.exists(candidate):
            return candidate
    return None


def _scene_kick_child_gen(parent_job_id: str, card_id: str) -> str:
    """Spawn a child image-gen job for one card. Returns the child job_id.
    The card's prompt + role drive parameters: characters use flux-dev-quality
    portrait framing; establishing shots use the same model but wider framing."""
    parent = _store_get_art_job(parent_job_id)
    if not parent:
        raise HTTPException(404, "Scene job not found")

    cards = parent.get("cards") or []
    card = next((c for c in cards if c["card_id"] == card_id), None)
    if not card:
        raise HTTPException(404, "Card not found in scene job")

    # Mark generating BEFORE async dispatch so the UI reflects state immediately.
    card["status"] = "generating"
    card["image_path"] = None
    _store_update_art_job(parent_job_id, cards=cards)

    child_job_id = _art_job_create("image", card["prompt"])
    card["child_job_id"] = child_job_id
    _store_update_art_job(parent_job_id, cards=cards)

    async def _run_child():
        try:
            from specialized.image_gen import generate_image
            result = await _art_asyncio.to_thread(
                generate_image,
                prompt=card["prompt"],
                model_name="flux-dev-quality",
                cfg=3.5,
                steps=25,
                width=1024,
                height=1024,
                seed=card.get("seed", -1),
            )
            status = "error" if result.startswith("Error") or result.startswith("Failed") else "ok"
            _art_job_finish(child_job_id, status, result)

            # Propagate back to the parent card
            parent_refresh = _store_get_art_job(parent_job_id)
            if not parent_refresh:
                return
            cards_now = parent_refresh.get("cards") or []
            for c in cards_now:
                if c["card_id"] == card_id:
                    if status == "ok":
                        # result format: "Generated Image: <filename> (Saved to Gallery) | ✅ Verified."
                        try:
                            fname = result.split("Generated Image: ")[1].split(" ")[0]
                            c["image_path"] = fname
                        except Exception:
                            pass
                        c["status"] = "ready"
                    else:
                        c["status"] = "error"
                        c["error"] = result
                    break
            _store_update_art_job(parent_job_id, cards=cards_now)
        except Exception as e:
            logger.error(f"Scene child gen failed: {e}")
            _art_job_finish(child_job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run_child())
    return child_job_id


@app.post("/v1/art/scene/start")
async def art_scene_start(req: SceneStartRequest):
    """Decompose a complex scene prompt and spawn child gens for each card."""
    from specialized.scene_compose import decompose_scene, build_scene_job, is_complex_scene

    parent_id = _art_job_create("scene", req.prompt)
    _store_update_art_job(parent_id, engine=req.engine, state="decomposing", cards=[])

    async def _decompose_and_kick():
        try:
            # NB: is_complex_scene() is for auto-routing from /v1/art/generate/image.
            # If the caller explicitly hit /scene/start they want decomposition —
            # let the LLM decide how many characters to extract.
            decomp = await _art_asyncio.to_thread(decompose_scene, req.prompt)
            if decomp is None:
                _art_job_finish(parent_id, "error", "Scene decomposition failed (Ollama error).")
                return
            scene_job = build_scene_job(parent_id, req.prompt, decomp)
            cards = [
                {
                    "card_id": c.card_id,
                    "role": c.role,
                    "name": c.name,
                    "prompt": c.prompt,
                    "status": "pending",
                    "image_path": None,
                    "child_job_id": None,
                    "seed": c.seed,
                }
                for c in scene_job.cards
            ]
            _store_update_art_job(parent_id, state="generating", cards=cards)
            # Kick child gens for every card
            for c in cards:
                _scene_kick_child_gen(parent_id, c["card_id"])
        except Exception as e:
            logger.error(f"Scene decomposition failed: {e}")
            _art_job_finish(parent_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_decompose_and_kick())
    return {"job_id": parent_id, "status": "running"}


@app.get("/v1/art/scene/{job_id}")
async def art_scene_get(job_id: str):
    """Poll the full scene state — parent + all card states."""
    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(404, "Scene job not found")
    return job


@app.post("/v1/art/scene/{job_id}/regenerate/{card_id}")
async def art_scene_regenerate(job_id: str, card_id: str):
    """Re-run generation for one card (e.g. user didn't like the result)."""
    child = _scene_kick_child_gen(job_id, card_id)
    return {"card_id": card_id, "child_job_id": child, "status": "regenerating"}


@app.post("/v1/art/scene/{job_id}/approve/{card_id}")
async def art_scene_approve(job_id: str, card_id: str):
    """Mark a card as approved by the user. When all cards are approved, the
    UI can call /compose to trigger the final composite."""
    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(404, "Scene job not found")
    cards = job.get("cards") or []
    for c in cards:
        if c["card_id"] == card_id:
            if c["status"] != "ready":
                raise HTTPException(409, f"Card not ready (status={c['status']})")
            c["status"] = "approved"
            break
    else:
        raise HTTPException(404, "Card not found")
    _store_update_art_job(job_id, cards=cards)
    all_approved = all(c["status"] == "approved" for c in cards)
    new_state = "awaiting_compose" if all_approved else "generating"
    _store_update_art_job(job_id, state=new_state)
    return {"card_id": card_id, "status": "approved", "all_approved": all_approved}


@app.post("/v1/art/scene/{job_id}/compose")
async def art_scene_compose(job_id: str):
    """Trigger the final OmniGen2 composite from all approved cards."""
    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(404, "Scene job not found")
    cards = job.get("cards") or []
    if not all(c["status"] == "approved" for c in cards):
        unapproved = [c["name"] for c in cards if c["status"] != "approved"]
        raise HTTPException(409, f"Not all cards approved: {unapproved}")

    _store_update_art_job(job_id, state="composing")

    async def _run_compose():
        try:
            from specialized.scene_compose import compose_via_omnigen
            from utils.gpu_queue import request_lock

            est_card = next((c for c in cards if c["role"] == "establishing_shot"), None)
            char_cards = [c for c in cards if c["role"] == "character"]

            est_path = _scene_resolve_workspace_image_path(est_card["image_path"]) if est_card else None
            char_paths: list[tuple[str, str]] = []
            for c in char_cards:
                p = _scene_resolve_workspace_image_path(c["image_path"])
                if p:
                    char_paths.append((c["name"], p))

            if not char_paths:
                _art_job_finish(job_id, "error", "No character images resolved on disk.")
                return

            # Use the "compose" GPU zone — evicts Klein, warms OmniGen.
            with request_lock("compose", timeout=900):
                composite = await _art_asyncio.to_thread(
                    compose_via_omnigen,
                    scene_prompt=job.get("prompt", ""),
                    character_image_paths=char_paths,
                    establishing_shot_path=est_path,
                )
            if not composite:
                _art_job_finish(job_id, "error", "OmniGen2 compose returned no output.")
                return
            _store_update_art_job(job_id, composite_path=composite, state="done")
            _art_job_finish(job_id, "ok", f"Composite: {composite}")
        except Exception as e:
            logger.error(f"Scene compose failed: {e}")
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run_compose())
    return {"job_id": job_id, "status": "composing"}


@app.post("/v1/art/generate/3d")
async def art_generate_3d(req: ThreeDGenRequest):
    """Queue a 3D model generation job. Returns job_id for polling."""
    job_id = _art_job_create("3d", req.prompt)

    async def _run():
        try:
            image_path = None
            if req.auto_concept:
                from specialized.image_gen import generate_image
                import re
                concept_prompt = (
                    f"one single {req.prompt}, solo, alone, full body, centered subject, "
                    f"standing straight, A-pose, legs slightly apart, arms slightly away from body, "
                    f"front facing camera, perfectly symmetrical, "
                    f"clean hard edges, every limb fully separated and distinct, "
                    f"isolated on pure white background, "
                    f"bright even studio lighting, high detail, sharp focus, "
                    f"no ground, no floor, no shadow, no base, no pedestal, "
                    f"no cropping, entire figure visible head to toe, feet floating above white"
                )
                _CONCEPT_NEG = (
                    "multiple objects, multiple characters, text, watermark, frame, border, "
                    "vignette, gradient background, shadow on ground, ground shadow, cast shadow, "
                    "ground contact, floor, puddle, rock base, stone base, earth, dirt, "
                    "complex background, environment, landscape, cropped, cut off, portrait only, "
                    "partial body, bad anatomy, deformed, extra limbs, blurry, low quality, "
                    "low resolution, dark background, colored background, feet touching ground"
                )
                _art_job_update(job_id, result="Generating concept art...")
                img_result = await _art_asyncio.to_thread(
                    generate_image, concept_prompt,
                    width=1024, height=1024,
                    cfg=4.5, steps=20,
                    negative_prompt=_CONCEPT_NEG,
                    skip_refinement=True,
                )
                match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
                if not match:
                    _art_job_finish(job_id, "error", f"Concept art failed: {img_result}")
                    return
                image_path = f"/app/comfy_io/output/{match.group(1)}"
            else:
                _art_job_finish(job_id, "error", "No image provided. Enable auto_concept or use /v1/art/generate/3d-from-image.")
                return

            import os
            if not os.path.exists(image_path):
                _art_job_finish(job_id, "error", f"Concept art image not found at {image_path}")
                return

            # Prepare image for 3D: remove background, composite on black
            from specialized.forge_agent import generate_3d_model, prepare_image_for_3d
            prepared_path = prepare_image_for_3d(image_path)
            if prepared_path:
                image_path = prepared_path

            _art_job_update(job_id, result="Generating 3D model (this may take several minutes)...")
            # Build quality overrides from request
            quality_overrides = {}
            if req.steps > 0:
                quality_overrides["steps"] = req.steps
            if req.cfg > 0:
                quality_overrides["cfg"] = req.cfg
            if not quality_overrides and req.quality:
                _QUALITY_PRESETS = {
                    "fast":     {"steps": 75,  "cfg": 5.0},
                    "balanced": {"steps": 100, "cfg": 5.5},
                    "high":     {"steps": 150, "cfg": 6.0},
                    "ultra":    {"steps": 200, "cfg": 6.5},
                }
                quality_overrides = _QUALITY_PRESETS.get(req.quality, {})

            result = await _art_asyncio.to_thread(
                generate_3d_model, image_path, req.workflow, quality_overrides
            )
            status = "error" if result.startswith("Error") else "ok"
            _art_job_finish(job_id, status, result)
        except Exception as e:
            logger.error(f"Art Studio 3D gen failed: {e}")
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}

@app.post("/v1/art/generate/action-figure")
async def art_generate_action_figure(req: ActionFigureRequest):
    """Queue an action figure generation job. Returns job_id for polling."""
    job_id = _art_job_create("action-figure", req.prompt)

    async def _run():
        try:
            from specialized.image_gen import generate_image
            import re
            concept_prompt = (
                f"{req.prompt}, neutral A-pose turnaround, front view, "
                f"standing perfectly upright, arms hanging relaxed at 45 degrees from body, "
                f"feet together, body facing directly forward, "
                f"symmetrical, single character, small figure centered with large white space around it, "
                f"isolated on pure solid white background, studio product photo lighting, "
                f"entire body visible head to toe including feet, high detail, sharp focus, "
                f"no weapons, no props, no accessories, no text, no cropping, no vignette"
            )
            _TPOSE_NEG = (
                "multiple objects, multiple characters, text, watermark, frame, border, "
                "vignette, dark edges, gradient background, shadow on ground, cast shadow, "
                "ground plane, rock base, pedestal, complex background, environment, landscape, "
                "cropped, portrait only, partial body, cut off feet, "
                "perspective distortion, foreshortening, dynamic pose, action pose, fighting stance, "
                "weapon, sword, gun, shield, "
                "bad anatomy, deformed, extra limbs, blurry, low quality, low resolution"
            )
            _art_job_update(job_id, result="Generating concept art...")
            img_result = await _art_asyncio.to_thread(
                generate_image, concept_prompt,
                width=1024, height=1024,
                cfg=4.5, steps=20,
                negative_prompt=_TPOSE_NEG,
                skip_refinement=True,
            )
            match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
            if not match:
                _art_job_finish(job_id, "error", f"Concept art failed: {img_result}")
                return
            image_path = f"/app/comfy_io/output/{match.group(1)}"

            import os
            if not os.path.exists(image_path):
                _art_job_finish(job_id, "error", f"Concept art image not found at {image_path}")
                return

            # Prepare image for 3D: remove background, composite on black
            from specialized.forge_agent import prepare_image_for_3d
            prepared_path = prepare_image_for_3d(image_path)
            if prepared_path:
                image_path = prepared_path

            _art_job_update(job_id, result="Generating 3D mesh and segmenting into posable parts...")
            from specialized.action_figure_agent import generate_action_figure
            result = await _art_asyncio.to_thread(
                generate_action_figure, image_path, req.workflow,
                target_height=req.target_height, clearance=req.clearance,
            )
            status = "error" if "Failed" in result else "ok"
            _art_job_finish(job_id, status, result)
        except Exception as e:
            logger.error(f"Art Studio action figure gen failed: {e}")
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}

@app.get("/v1/art/gallery/images")
async def art_gallery_images():
    """List generated images with metadata."""
    import json as _json
    gallery_path = "/workspace/delivered_artifacts"
    if not os.path.exists(gallery_path):
        return {"images": []}
    try:
        images = []
        for f in sorted(os.listdir(gallery_path), key=lambda x: os.path.getmtime(os.path.join(gallery_path, x)), reverse=True):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                fpath = os.path.join(gallery_path, f)
                meta = {}
                meta_path = fpath + ".json"
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as mf:
                        meta = _json.load(mf)
                images.append({
                    "filename": f,
                    "url": f"/delivered_artifacts/{f}",
                    "download_url": f"/v1/art/gallery/images/{f}?dl=1",
                    "size_bytes": os.path.getsize(fpath),
                    "meta": meta,
                })
        return {"images": images}
    except Exception as e:
        return {"images": [], "error": str(e)}

@app.get("/v1/art/gallery/images/{filename}")
async def art_serve_gallery_image(filename: str, dl: int = 0):
    """Serve a delivered image, optionally as a download attachment."""
    import re
    if not re.match(r'^[\w.\- ]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    fpath = os.path.normpath(os.path.join("/workspace/delivered_artifacts", filename))
    if not fpath.startswith("/workspace/delivered_artifacts"):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Image not found")
    ext = filename.rsplit(".", 1)[-1].lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    media_type = media_types.get(ext, "application/octet-stream")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if dl else {}
    return FileResponse(fpath, media_type=media_type, headers=headers)


@app.get("/v1/art/gallery/3d")
async def art_gallery_3d():
    """List 3D model files with direct download URLs."""
    output_dirs = [
        ("3d_models", "/app/comfy_io/output/3D"),
        ("action_figures", "/app/comfy_io/output/action_figures"),
    ]
    files = []
    for category, dir_path in output_dirs:
        if not os.path.exists(dir_path):
            continue
        subdir = "3D" if category == "3d_models" else "action_figures"
        for f in sorted(os.listdir(dir_path), key=lambda x: os.path.getmtime(os.path.join(dir_path, x)), reverse=True):
            if f.lower().endswith(('.glb', '.obj', '.stl', '.3mf')):
                fpath = os.path.join(dir_path, f)
                rel = f"{subdir}/{f}"
                files.append({
                    "filename": f,
                    "category": category,
                    "ext": f.rsplit(".", 1)[-1].upper(),
                    "size_bytes": os.path.getsize(fpath),
                    "url": f"/v1/art/files/{rel}",
                    "download_url": f"/v1/art/files/{rel}?dl=1",
                })
    return {"files": files}

# ── Serve 3D model files (GLB/OBJ/STL) for the viewer ─────────────────────

@app.get("/v1/art/files/{filepath:path}")
async def art_serve_file(filepath: str, dl: int = 0):
    """Serve a generated 3D file for the browser viewer. Pass ?dl=1 to force download."""
    full_path = os.path.join("/app/comfy_io/output", filepath)
    full_path = os.path.normpath(full_path)

    if not full_path.startswith("/app/comfy_io/output"):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    ext = full_path.rsplit(".", 1)[-1].lower()
    media_types = {"glb": "model/gltf-binary", "gltf": "model/gltf+json",
                   "obj": "text/plain", "stl": "model/stl", "3mf": "model/3mf"}
    media_type = media_types.get(ext, "application/octet-stream")
    filename = os.path.basename(full_path)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if dl else {}
    return FileResponse(full_path, media_type=media_type, headers=headers)


@app.get("/delivered_artifacts/{filepath:path}")
async def serve_delivered_artifact(filepath: str, dl: int = 0):
    """
    Serve files from delivered_artifacts with optional download forcing.
    Pass ?dl=1 to force browser download instead of inline display.
    This complements the StaticFiles mount by supporting Content-Disposition headers.
    """
    import mimetypes
    
    full_path = os.path.normpath(os.path.join("/workspace/delivered_artifacts", filepath))
    
    # Security check: prevent directory traversal
    if not full_path.startswith("/workspace/delivered_artifacts"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type:
        ext = full_path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif",
            "mp4": "video/mp4", "webm": "video/webm",
            "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
            "glb": "model/gltf-binary", "gltf": "model/gltf+json",
            "obj": "text/plain", "stl": "model/stl", "3mf": "model/3mf"
        }
        mime_type = mime_map.get(ext, "application/octet-stream")
    
    filename = os.path.basename(full_path)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if dl else {}
    
    return FileResponse(full_path, media_type=mime_type, headers=headers)


@app.get("/v1/art/jobs/{job_id}/download")
async def art_job_download(job_id: str, dl: int = 1):
    """
    Single-hop download from a job ID.
    Resolves the output file from the job result and streams it directly.
    Pass ?dl=0 to serve inline (e.g. for browser preview) instead of attachment.
    """
    import re
    from fastapi.responses import RedirectResponse

    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") not in ("ok", "completed"):
        raise HTTPException(status_code=409, detail=f"Job not complete — status: {job.get('status')}")

    result = job.get("result", "")

    # Image jobs: result contains "Generated Image: filename.png"
    img_match = re.search(r"Generated Image: ([\w.\-]+)", result)
    if img_match:
        filename = img_match.group(1)
        fpath = os.path.normpath(f"/workspace/delivered_artifacts/{filename}")
        if not fpath.startswith("/workspace/delivered_artifacts"):
            raise HTTPException(status_code=403, detail="Access denied")
        if not os.path.isfile(fpath):
            raise HTTPException(status_code=404, detail=f"Output file not found: {filename}")
        ext = filename.rsplit(".", 1)[-1].lower()
        media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        media_type = media_types.get(ext, "application/octet-stream")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if dl else {}
        return FileResponse(fpath, media_type=media_type, headers=headers)

    # 3D jobs: result contains a path ending in .glb/.obj/.stl
    path_match = re.search(r"(/[^\s]+\.(?:glb|obj|stl|3mf))", result, re.IGNORECASE)
    if path_match:
        full_path = os.path.normpath(path_match.group(1))
        allowed = ["/app/comfy_io/output", "/workspace"]
        if not any(full_path.startswith(r) for r in allowed):
            raise HTTPException(status_code=403, detail="Access denied")
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail=f"Output file not found: {full_path}")
        ext = full_path.rsplit(".", 1)[-1].lower()
        media_types = {"glb": "model/gltf-binary", "obj": "text/plain", "stl": "model/stl", "3mf": "model/3mf"}
        media_type = media_types.get(ext, "application/octet-stream")
        filename = os.path.basename(full_path)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'} if dl else {}
        return FileResponse(full_path, media_type=media_type, headers=headers)

    raise HTTPException(status_code=422, detail="Could not resolve output file from job result")

# ── Smooth / optimize a generated mesh for 3D printing ─────────────────────

class SmoothRequest(BaseModel):
    mesh_path: str
    target_height: float = 150.0
    smooth_iterations: int = 10

@app.post("/v1/art/smooth")
async def art_smooth_mesh(req: SmoothRequest):
    """Smooth and optimize a mesh for 3D printing. Returns path to optimized GLB."""
    import trimesh

    if not os.path.isfile(req.mesh_path):
        raise HTTPException(status_code=404, detail=f"Mesh not found: {req.mesh_path}")

    try:
        from specialized.mesh_utils import optimize_for_printing

        scene = trimesh.load(req.mesh_path, force="scene")
        if isinstance(scene, trimesh.Scene):
            meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(meshes) if meshes else None
        else:
            mesh = scene

        if mesh is None or not isinstance(mesh, trimesh.Trimesh):
            raise HTTPException(status_code=400, detail="Could not extract mesh")

        mesh = optimize_for_printing(
            mesh, target_height_mm=req.target_height,
            smooth_iterations=req.smooth_iterations,
        )

        # Save optimized version alongside original
        base, ext = os.path.splitext(req.mesh_path)
        out_path = f"{base}_print{ext}"
        mesh.export(out_path)

        return {"status": "ok", "path": out_path, "vertices": len(mesh.vertices), "faces": len(mesh.faces)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mesh smoothing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── User-guided segmentation (Meshy-style joint placement) ─────────────────

class JointPosition(BaseModel):
    x: float
    y: float
    z: float

class SegmentRequest(BaseModel):
    mesh_path: str
    joints: dict[str, JointPosition]  # e.g. {"neck": {x, y, z}, "left_shoulder": {x, y, z}}
    target_height: float = 150.0
    clearance: float = 0.3

@app.post("/v1/art/segment")
async def art_segment_with_joints(req: SegmentRequest):
    """
    Segment a mesh at user-placed joint positions.
    Returns job_id for polling — segmentation runs in background.
    """
    if not os.path.isfile(req.mesh_path):
        raise HTTPException(status_code=404, detail=f"Mesh not found: {req.mesh_path}")

    job_id = _art_job_create("segment", f"Segmenting with {len(req.joints)} joints")

    async def _run():
        try:
            import trimesh
            import numpy as np
            from specialized.mesh_utils import repair_mesh, validate_printability
            from specialized.joint_library import BallSocketJoint, orient_joint_geometry, safe_boolean
            from specialized.action_figure_agent import (
                BODY_PARTS, ACTION_FIGURE_OUTPUT_DIR, _load_mesh,
                _center_mesh, _scale_mesh_to_height, _ensure_output_dir,
            )

            _art_job_update(job_id, result="Loading and repairing mesh...")
            mesh = _load_mesh(req.mesh_path)
            mesh = repair_mesh(mesh)
            mesh = _center_mesh(mesh)
            mesh = _scale_mesh_to_height(mesh, req.target_height)

            # Build skeleton dict from user-placed joints
            # For joints the user didn't place, we skip those body parts
            user_joints = {}
            for name, pos in req.joints.items():
                user_joints[name] = {
                    "position": np.array([pos.x, pos.y, pos.z]),
                    "normal": _infer_joint_normal(name),
                    "radius": _infer_joint_radius(name, req.target_height),
                }

            skeleton = {"joints": user_joints, "confidence": 1.0, "detected_features": {}}

            _art_job_update(job_id, result=f"Cutting mesh at {len(user_joints)} joints...")

            # Determine which body parts we can extract (all required joints must be placed)
            _ensure_output_dir()
            prefix = f"segment_{uuid.uuid4().hex[:8]}"
            output_files = {}
            part_meshes = {}
            skipped = []

            for part_name, joint_reqs in BODY_PARTS.items():
                required_joints = [jn for jn, _ in joint_reqs]
                if not all(jn in user_joints for jn in required_joints):
                    skipped.append(part_name)
                    continue

                # Extract part by cutting at each adjacent joint
                part = mesh.copy()
                for joint_name, role in joint_reqs:
                    joint = user_joints[joint_name]
                    normal = joint["normal"]
                    cut_normal = -normal if role == "parent" else normal

                    try:
                        sliced = part.slice_plane(joint["position"], cut_normal, cap=True)
                        if sliced is not None and len(sliced.faces) > 5:
                            part = sliced
                    except Exception:
                        pass

                if len(part.faces) < 20:
                    skipped.append(part_name)
                    continue

                # Add ball-socket joints
                for joint_name, role in joint_reqs:
                    joint = user_joints[joint_name]
                    bsj = BallSocketJoint(ball_radius=joint["radius"], clearance=req.clearance)

                    if role == "parent":
                        ball = bsj.create_ball_assembly()
                        orient_joint_geometry(ball, joint["position"], joint["normal"])
                        part = safe_boolean("union", [part, ball])
                    else:
                        housing = bsj.create_socket_housing()
                        orient_joint_geometry(housing, joint["position"], -joint["normal"])
                        part = safe_boolean("union", [part, housing])
                        void = bsj.create_socket_void()
                        orient_joint_geometry(void, joint["position"], -joint["normal"])
                        part = safe_boolean("difference", [part, void])

                out_path = os.path.join(ACTION_FIGURE_OUTPUT_DIR, f"{prefix}_{part_name}.stl")
                part.export(out_path, file_type="stl")
                output_files[part_name] = out_path
                part_meshes[part_name] = part

            warnings = validate_printability(part_meshes)
            part_count = len(output_files)

            # Manifest
            manifest = {
                "prefix": prefix,
                "target_height_mm": req.target_height,
                "clearance_mm": req.clearance,
                "user_joints": {n: {"x": j.x, "y": j.y, "z": j.z} for n, j in req.joints.items()},
                "parts": {n: p for n, p in output_files.items()},
                "skipped": skipped,
                "warnings": warnings,
            }
            manifest_path = os.path.join(ACTION_FIGURE_OUTPUT_DIR, f"{prefix}_manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)

            result_msg = (
                f"Segmentation complete: {part_count} parts exported.\n"
                f"Skipped: {', '.join(skipped) if skipped else 'none'}\n"
                f"Manifest: {manifest_path}"
            )
            _art_job_finish(job_id, "ok", result_msg)

        except Exception as e:
            logger.error(f"Segmentation failed: {e}", exc_info=True)
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}


def _infer_joint_normal(joint_name: str):
    """Infer cut plane normal from joint name (standard humanoid)."""
    import numpy as np
    normals = {
        "neck": [0, 0, 1], "waist": [0, 0, 1],
        "left_shoulder": [-1, 0, 0], "right_shoulder": [1, 0, 0],
        "left_elbow": [-1, 0, 0], "right_elbow": [1, 0, 0],
        "left_wrist": [-1, 0, 0], "right_wrist": [1, 0, 0],
        "left_hip": [0, 0, -1], "right_hip": [0, 0, -1],
        "left_knee": [0, 0, -1], "right_knee": [0, 0, -1],
        "left_ankle": [0, 0, -1], "right_ankle": [0, 0, -1],
    }
    return np.array(normals.get(joint_name, [0, 0, 1]), dtype=float)


def _infer_joint_radius(joint_name: str, target_height: float) -> float:
    """Estimate ball-socket radius from joint name and figure scale."""
    scale = target_height / 150.0
    radii = {
        "neck": 3.5, "waist": 5.0,
        "left_shoulder": 4.0, "right_shoulder": 4.0,
        "left_elbow": 3.0, "right_elbow": 3.0,
        "left_wrist": 2.5, "right_wrist": 2.5,
        "left_hip": 4.5, "right_hip": 4.5,
        "left_knee": 3.5, "right_knee": 3.5,
        "left_ankle": 2.5, "right_ankle": 2.5,
    }
    return radii.get(joint_name, 3.5) * scale


@app.get("/v1/templates")
async def list_templates():
    """List all expertise templates (for deploy form's template dropdown)."""
    from config import TEMPLATE_DB_URL

    try:
        import psycopg2
        conn = psycopg2.connect(TEMPLATE_DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, intent, default_model
            FROM swarm.expertise_templates
            ORDER BY id
        """)
        templates = []
        for row in cur.fetchall():
            templates.append({
                "id": row[0],
                "intent": row[1],
                "default_model": row[2],
            })
        cur.close()
        conn.close()
        return {"templates": templates}
    except Exception as e:
        logger.warning(f"Failed to list templates: {e}")
        return {"templates": []}


# ---------------------------------------------------------------------------
# Context Compaction Endpoint
# ---------------------------------------------------------------------------
class CompactRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "qwen2.5-coder:14b-instruct-q4_k_m"

@app.post("/v1/chat/compact")
async def compact_chat(request: CompactRequest):
    """
    Summarize a long conversation into [summary_message] + last 3 exchanges.
    Called by the UI when the user clicks the context meter or auto-compact fires.
    """
    from church import get_best_host_for_model
    import httpx
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    if len(messages) <= 6:
        return {"messages": messages, "summary": "", "compacted": False}

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:500]}" for m in messages[:-3]
    )
    summarize_prompt = (
        "Summarize the following conversation in 3 concise sentences, "
        "capturing the key tasks, decisions, and context needed to continue:\n\n"
        f"{history_text}"
    )
    try:
        ollama_host = get_best_host_for_model(request.model)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{ollama_host}/api/generate", json={
                "model": request.model,
                "prompt": summarize_prompt,
                "stream": False,
            })
        summary = resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"[Compact] Summarization failed: {e}")
        summary = f"[Conversation context — {len(messages)} messages]"

    compacted = [
        {"role": "system", "content": f"[Conversation Summary]: {summary}"},
        *messages[-3:],
    ]
    return {"messages": compacted, "summary": summary, "compacted": True}


# ---------------------------------------------------------------------------
# Session Memory Endpoints
# ---------------------------------------------------------------------------
class SummarizeSessionRequest(BaseModel):
    messages: List[ChatMessage]
    topic: str = "general"
    model: str = "qwen2.5-coder:14b-instruct-q4_k_m"

@app.post("/v1/chat/summarize-session")
async def summarize_session(request: SummarizeSessionRequest):
    """
    Produce a 3-sentence summary of a completed conversation for cross-session memory.
    Only called when the user has opted in to session memory.
    """
    from church import get_best_host_for_model
    import httpx
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    if len(messages) < 4:
        return {"summary": "", "saved": False}

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:400]}" for m in messages[:20]
    )
    summarize_prompt = (
        "Summarize this conversation in exactly 3 sentences. "
        "Focus on: what the user was trying to accomplish, key decisions made, and any important context for future sessions.\n\n"
        f"{history_text}"
    )
    try:
        ollama_host = get_best_host_for_model(request.model)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{ollama_host}/api/generate", json={
                "model": request.model,
                "prompt": summarize_prompt,
                "stream": False,
            })
        summary = resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"[SummarizeSession] Failed: {e}")
        return {"summary": "", "saved": False}

    return {"summary": summary, "saved": False}


class SessionSummaryRequest(BaseModel):
    date_key: str
    topic: str
    summary: str
    owner_id: Optional[str] = None

@app.post("/v1/memory/session-summary")
async def save_session_summary(request: SessionSummaryRequest, http_request: Request):
    """Persist a session summary to skills_memory.json."""
    from memory_system import memory
    owner_id = _resolve_owner_id(request.owner_id, http_request)
    result = memory.add_session_summary(request.date_key, request.topic, request.summary, owner_id=owner_id)
    return {"status": "ok", "message": result}


@app.get("/v1/memory/session-summaries")
async def get_session_summaries(n: int = 5, owner_id: Optional[str] = None, http_request: Request = None):
    """Retrieve the N most recent session summaries."""
    from memory_system import memory
    resolved_owner_id = _resolve_owner_id(owner_id, http_request) if http_request is not None else owner_id
    summaries = memory.get_recent_summaries(n=n, owner_id=resolved_owner_id)
    return {"summaries": summaries}


# ══════════════════════════════════════════════════════════════════════════════
# Cluster-Aware Ops Infrastructure (merged from Core main branch)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/ops/health")
async def ops_health():
    """Infrastructure health across cluster nodes + control plane service checks."""
    import subprocess
    import socket
    import requests as _requests
    from config import HOPPER_IP, LANGFUSE_HOST, TURING_IP, LOVELACE_IP

    def normalize_containers(raw_containers):
        # Docker's own /containers/json?all=true response is the source of truth for
        # State (running/exited/created/restarting/paused/dead) — read it directly
        # instead of assuming "running" (which silently hid every dropped/created
        # container from the Fleet grid: Docker's default, non-`all` query only ever
        # RETURNS running containers, so nothing else could previously arrive here).
        parsed = []
        for c in raw_containers or []:
            name = c.get("Names", ["/unknown"])
            if isinstance(name, list):
                name = (name[0] if name else "unknown").lstrip("/")
            image_raw = c.get("Image", "unknown")
            image = image_raw.split("/")[-1].split(":")[0]
            uptime = c.get("Status", "Unknown")
            status = c.get("State") or "unknown"
            parsed.append({"name": name, "image": image, "uptime": uptime, "status": status})
        return parsed

    def fetch_local_containers():
        try:
            result = subprocess.run(
                ["curl", "-s", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/json?all=true"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return normalize_containers(json.loads(result.stdout))
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect("/var/run/docker.sock")
            request = (
                "GET /containers/json?all=true HTTP/1.0\r\n"
                "Host: localhost\r\n"
                "Accept: application/json\r\n"
                "\r\n"
            )
            sock.sendall(request.encode("ascii"))
            chunks = []
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
            sock.close()
            raw = b"".join(chunks).decode("utf-8", errors="replace")
            parts = raw.split("\r\n\r\n", 1)
            if len(parts) != 2:
                raise RuntimeError("Malformed docker socket response")
            body = parts[1]
            if not body.strip():
                return []
            return normalize_containers(json.loads(body))
        except Exception as e:
            raise RuntimeError(f"Local docker query failed: {str(e)[:80]}")

    def fetch_remote_containers(ip_addr: str):
        endpoint = f"http://{ip_addr}:2375/containers/json?all=true"
        resp = _requests.get(endpoint, timeout=4)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        return normalize_containers(resp.json())

    def fetch_justin_containers():
        try:
            return fetch_local_containers()
        except Exception:
            last_error = None
            for host in [LOVELACE_IP, "host.docker.internal"]:
                try:
                    return fetch_remote_containers(host)
                except Exception as e:
                    last_error = e
            raise RuntimeError(str(last_error) if last_error else "Lovelace container probe failed")

    nodes = []
    ctrl_plane = []
    degraded_reasons = []

    cluster_defs = [
        {"name": "Lovelace", "role": "execution", "ip": LOVELACE_IP, "fetch": lambda: fetch_justin_containers()},
        {"name": "Turing", "role": "gateway", "ip": TURING_IP, "fetch": lambda: fetch_remote_containers(TURING_IP)},
        {"name": "Hopper", "role": "control", "ip": HOPPER_IP, "fetch": lambda: fetch_remote_containers(HOPPER_IP)},
    ]

    for node in cluster_defs:
        try:
            containers = node["fetch"]()
            # `containers` now includes every state (see normalize_containers), so
            # running_count must filter — it previously equaled len(containers) only
            # because the fetch itself used to silently exclude non-running containers.
            running = sum(1 for c in containers if c.get("status") == "running")
            nodes.append({
                "name": node["name"], "role": node["role"], "ip": node["ip"],
                "healthy": True, "running_count": running,
                "containers": containers, "error": None,
            })
        except Exception as e:
            nodes.append({
                "name": node["name"], "role": node["role"], "ip": node["ip"],
                "healthy": False, "running_count": 0,
                "containers": [], "error": str(e)[:120],
            })
            degraded_reasons.append(f"{node['name']}: {str(e)[:50]}")

    execution_plane = next((n["containers"] for n in nodes if n["role"] == "execution"), [])
    running_count = sum(n["running_count"] for n in nodes)

    cp_services = [
        {"name": "Langfuse", "url": f"{LANGFUSE_HOST}/api/public/health", "port": 3000},
        {"name": "PostgreSQL", "url": None, "port": 5432},
        {"name": "SPIRE Server", "url": None, "port": 8081},
        {"name": "MinIO API", "url": f"http://{HOPPER_IP}:9190/minio/health/live", "port": 9190},
        {"name": "MinIO Console", "url": None, "port": 9191},
    ]
    for svc in cp_services:
        try:
            if svc["url"]:
                r = _requests.get(svc["url"], timeout=2)
                alive = r.status_code < 500
            else:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                code = s.connect_ex((HOPPER_IP, svc["port"]))
                s.close()
                alive = code == 0
            ctrl_plane.append({"name": svc["name"], "port": svc["port"], "healthy": alive})
        except Exception:
            ctrl_plane.append({"name": svc["name"], "port": svc["port"], "healthy": False})

    down_control = [svc["name"] for svc in ctrl_plane if not svc["healthy"]]
    if down_control:
        degraded_reasons.append(f"Control plane: {', '.join(down_control[:3])}")

    status_msg = "ONLINE" if not degraded_reasons else f"DEGRADED ({'; '.join(degraded_reasons[:3])})"
    return {
        "status": status_msg, "running_count": running_count, "nodes": nodes,
        "execution_plane": execution_plane, "control_plane": ctrl_plane,
    }


# --- Ops Traces Endpoints (Langfuse proxy) ---
@app.get("/api/v1/ops/traces")
async def ops_traces(limit: int = 50):
    """Recent Langfuse traces (proxied from Langfuse API)."""
    import requests as _requests
    from config import LANGFUSE_HOST
    lf_host = LANGFUSE_HOST
    lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not lf_public:
        return {"data": [], "error": "LANGFUSE_PUBLIC_KEY not configured"}
    try:
        url = f"{lf_host}/api/public/traces?limit={limit}&orderBy=timestamp.desc"
        resp = _requests.get(url, auth=(lf_public, lf_secret), timeout=5)
        if resp.status_code == 200:
            traces = []
            for t in resp.json().get("data", []):
                traces.append({
                    "id": t.get("id"), "timestamp": t.get("timestamp"),
                    "name": t.get("name", "Unknown"),
                    "input_preview": str(t.get("input", ""))[:120],
                    "latency": t.get("latency"), "level": t.get("level", "DEFAULT"),
                })
            return {"data": traces}
        return {"data": [], "error": f"Langfuse HTTP {resp.status_code}"}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/api/v1/ops/traces/{trace_id}")
async def ops_trace_detail(trace_id: str):
    """Langfuse trace detail + observations (spans)."""
    import requests as _requests
    from config import LANGFUSE_HOST
    lf_host = LANGFUSE_HOST
    lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not lf_public:
        raise HTTPException(status_code=503, detail="LANGFUSE_PUBLIC_KEY not configured")
    try:
        trace_resp = _requests.get(
            f"{lf_host}/api/public/traces/{trace_id}",
            auth=(lf_public, lf_secret), timeout=5,
        )
        trace_data = trace_resp.json() if trace_resp.status_code == 200 else {}
        obs_resp = _requests.get(
            f"{lf_host}/api/public/observations?traceId={trace_id}&limit=50",
            auth=(lf_public, lf_secret), timeout=5,
        )
        observations = obs_resp.json().get("data", []) if obs_resp.status_code == 200 else []
        return {
            "trace": trace_data, "observations": observations,
            "langfuse_url": f"{lf_host}/project/default/traces/{trace_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Training Runs / Catalog Endpoints ---
@app.get("/api/v1/training/runs")
async def training_runs_list():
    """List training run directories from the configured training output directory."""
    from pathlib import Path as _Path
    from config import TRAINING_OUTPUT_DIR
    runs = []
    base_dir = _Path(TRAINING_OUTPUT_DIR)
    if base_dir.exists():
        for run_dir in sorted(base_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if not run_dir.is_dir():
                continue
            config_file = run_dir / "training_config.json"
            cfg = {}
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            adapter_ready = (
                (run_dir / "adapter_model.safetensors").exists()
                or (run_dir / "adapter_model.bin").exists()
            )
            gguf_files = [f.name for f in run_dir.glob("*.gguf")]
            status = "converted" if gguf_files else ("complete" if adapter_ready else "in_progress")
            runs.append({
                "id": run_dir.name, "base_model": cfg.get("base_model", "unknown"),
                "started_at": cfg.get("started_at"), "num_epochs": cfg.get("num_epochs"),
                "status": status, "adapter_ready": adapter_ready, "gguf_files": gguf_files,
            })
    return {"runs": runs}


@app.get("/api/v1/training/catalog")
async def model_catalog():
    """Model catalog: Ollama models on all nodes + local trained GGUF files."""
    import requests as _requests
    from pathlib import Path as _Path
    from config import OLLAMA_HOST, SECONDARY_OLLAMA_HOST, TRAINING_OUTPUT_DIR
    catalog: dict = {"ollama_models": [], "local_gguf": [], "errors": []}
    for label, host in [("execution-plane", OLLAMA_HOST), ("control-plane", SECONDARY_OLLAMA_HOST)]:
        try:
            r = _requests.get(f"{host}/api/tags", timeout=3)
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    catalog["ollama_models"].append({
                        "name": m.get("name"),
                        "size_mb": round((m.get("size") or 0) / 1_048_576, 1),
                        "modified_at": m.get("modified_at"), "node": label,
                        "digest": (m.get("digest") or "")[:12],
                    })
        except Exception as e:
            catalog["errors"].append(f"{label}: {str(e)[:80]}")
    base_dir = _Path(TRAINING_OUTPUT_DIR)
    if base_dir.exists():
        for gguf in sorted(base_dir.rglob("*.gguf")):
            stat = gguf.stat()
            catalog["local_gguf"].append({
                "name": gguf.stem, "path": str(gguf.relative_to(base_dir)),
                "size_mb": round(stat.st_size / 1_048_576, 1), "run_id": gguf.parent.name,
            })
    return catalog


# --- Evidence Locker Endpoints ---
@app.get("/api/v1/ops/evidence/folders")
async def evidence_folders():
    """List available evidence folders under /workspace/docs."""
    from pathlib import Path as _Path
    docs_root = _Path("/workspace/docs")
    default_folders = ["specs", "evidence", "compliance", "architecture"]
    if not docs_root.exists():
        return {"folders": [], "error": "docs directory not found"}
    folders = [p.name for p in docs_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    folders = sorted(set(default_folders + folders))
    return {"folders": folders}


@app.get("/api/v1/ops/evidence/files")
async def evidence_files(folder: str):
    """List evidence files for a given docs subfolder."""
    from pathlib import Path as _Path
    docs_root = _Path("/workspace/docs")
    target = (docs_root / folder).resolve()
    if not str(target).startswith(str(docs_root.resolve())):
        raise HTTPException(status_code=403, detail="Invalid folder path")
    if not target.exists() or not target.is_dir():
        return {"files": [], "error": "folder not found"}
    allowed = {".md", ".txt", ".json", ".yaml", ".yml"}
    files = []
    for f in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if f.is_file() and f.suffix.lower() in allowed:
            files.append({"name": f.name, "size": f.stat().st_size})
    return {"files": files}


@app.get("/api/v1/ops/evidence/content")
async def evidence_content(folder: str, filename: str):
    """Read an evidence file from docs safely."""
    from pathlib import Path as _Path
    docs_root = _Path("/workspace/docs").resolve()
    file_path = (docs_root / folder / filename).resolve()
    if not str(file_path).startswith(str(docs_root)):
        raise HTTPException(status_code=403, detail="Invalid file path")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {"name": file_path.name, "folder": folder, "content": content,
                "content_type": file_path.suffix.lower().lstrip(".")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Media Gallery + ComfyUI + Generation Endpoints ---
@app.get("/api/v1/media/gallery")
async def media_gallery(kind: str = "all"):
    """List artifacts from /workspace/delivered_artifacts with optional type filtering."""
    from pathlib import Path as _Path
    gallery_dir = _Path("/workspace/delivered_artifacts")
    if not gallery_dir.exists():
        return {"items": []}
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    audio_exts = {".wav", ".mp3", ".ogg", ".m4a"}
    model_exts = {".glb", ".obj", ".3mf"}

    def _include(ext: str) -> bool:
        if kind == "image": return ext in image_exts
        if kind == "audio": return ext in audio_exts
        if kind == "model": return ext in model_exts
        return ext in image_exts or ext in audio_exts or ext in model_exts

    items = []
    for f in sorted(gallery_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if not _include(ext):
            continue
        meta = None
        meta_file = f.with_name(f.name + ".json")
        if meta_file.exists() and meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                meta = None
        media_kind = "model" if ext in model_exts else ("image" if ext in image_exts else "audio")
        items.append({
            "name": f.name, "kind": media_kind,
            "size_mb": round(f.stat().st_size / 1_048_576, 2),
            "updated_at": f.stat().st_mtime,
            "url": f"/delivered_artifacts/{f.name}",
            "download_url": f"/delivered_artifacts/{f.name}?dl=1",
            "metadata": meta,
        })
    return {"items": items}


class MediaImageGenerateRequest(BaseModel):
    prompt: str
    model_name: str = "auto"
    cfg: float = 7.0
    steps: int = 20
    width: int = 1024
    height: int = 1024
    sampler: str = "euler"
    scheduler: str = "normal"
    seed: int = -1


class MediaForgeGenerateRequest(BaseModel):
    image_path: str
    workflow_name: str = "workflow_hunyuan_paint-2.json"


class MediaImageLoRATrainRequest(BaseModel):
    name: str
    base_profile: str = "sdxl-general"
    dataset_dir: str = "/workspace/delivered_artifacts"
    trigger_word: str | None = None
    max_images: int = 250
    learning_rate: float = 1e-4
    steps: int = 1000
    trainer_mode: str = "plan-only"


class MediaImageRatingRequest(BaseModel):
    score: int = Field(..., ge=1, le=5, description="Quality score 1-5")
    approved: bool = Field(False, description="Approve image for LoRA training dataset")
    notes: str | None = None
    trigger_word: str | None = None
    base_profile: str = "sdxl-general"


@app.get("/api/v1/media/comfyui/status")
async def media_comfyui_status():
    """Check ComfyUI availability for media workflows."""
    import requests as _requests
    comfy_url = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
    try:
        resp = _requests.get(f"{comfy_url}/system_stats", timeout=3)
        return {"healthy": resp.status_code == 200, "host": comfy_url}
    except Exception as e:
        return {"healthy": False, "host": comfy_url, "error": str(e)[:120]}


@app.get("/api/v1/media/comfyui/checkpoints")
async def media_comfyui_checkpoints():
    """List curated image profiles plus raw ComfyUI checkpoints."""
    try:
        from specialized.image_gen import get_image_model_catalog
        return get_image_model_catalog()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch checkpoints: {e}")


@app.post("/api/v1/media/generate/image")
async def media_generate_image(req: MediaImageGenerateRequest):
    """Generate image using Creative Studio toolchain (ComfyUI-backed)."""
    try:
        from specialized.image_gen import generate_image
        result = generate_image(
            prompt=req.prompt, model_name=req.model_name, cfg=req.cfg,
            steps=req.steps, width=req.width, height=req.height,
            sampler=req.sampler, scheduler=req.scheduler, seed=req.seed,
        )
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")


@app.post("/api/v1/media/generate/3d")
async def media_generate_3d(req: MediaForgeGenerateRequest):
    """Generate 3D model from image via Creature Forge."""
    try:
        from specialized.forge_agent import generate_3d_model
        result = generate_3d_model(req.image_path, req.workflow_name)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D generation failed: {e}")


@app.post("/api/v1/media/training/image-lora")
async def media_train_image_lora(req: MediaImageLoRATrainRequest):
    """Queue a dedicated image LoRA training preparation run."""
    resolved_dataset_dir = resolve_workspace_path(req.dataset_dir)
    if not os.path.isdir(resolved_dataset_dir):
        raise HTTPException(status_code=404, detail=f"Dataset directory not found: {req.dataset_dir}")

    payload = req.model_dump()
    payload["dataset_dir"] = resolved_dataset_dir
    run = _store_create_image_training_run(payload)
    return {"run_id": run["run_id"], "status": run["status"], "payload": run["payload"]}


@app.get("/api/v1/media/training/image-lora/{run_id}")
async def media_train_image_lora_status(run_id: str):
    """Get status for a queued image LoRA training run."""
    run = _store_get_image_training_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Image LoRA training run not found")
    return run


@app.post("/v1/art/jobs/{job_id}/rate")
async def rate_art_job(job_id: str, req: MediaImageRatingRequest):
    """
    Rate a completed art job (score 1-5).  When approved=True the output image
    is copied to the approved-shots dataset and a mini LoRA training run is queued.
    """
    import re
    import shutil as _shutil
    from pathlib import Path as _Path

    job = _store_get_art_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Persist the rating back to the job record
    _art_job_update(
        job_id,
        score=req.score,
        approved=req.approved,
        rating_notes=req.notes,
        rated_at=time.time(),
    )

    response: dict = {"job_id": job_id, "score": req.score, "approved": req.approved}

    if req.approved:
        result_str = job.get("result", "")
        match = re.search(r"Generated Image: ([\w.\-]+)", result_str)
        if not match:
            response["warning"] = "Job result did not contain an image filename — skipping training enqueue."
            return response

        filename = match.group(1)

        # Locate the image in delivered_artifacts
        _workspace = "/workspace" if os.path.isdir("/workspace/delivered_artifacts") else str(
            _Path(__file__).resolve().parent.parent
        )
        src_img = _Path(_workspace) / "delivered_artifacts" / filename
        if not src_img.exists():
            response["warning"] = f"Image file not found at {src_img} — skipping training enqueue."
            return response

        # Copy to approved-shots dataset
        approved_dir = _Path(_workspace) / "training_data" / "image_lora" / "approved_shots"
        approved_dir.mkdir(parents=True, exist_ok=True)
        dst_img = approved_dir / filename
        _shutil.copy(src_img, dst_img)

        # Copy sidecar if present
        src_sidecar = _Path(str(src_img) + ".json")
        if src_sidecar.exists():
            _shutil.copy(src_sidecar, _Path(str(dst_img) + ".json"))
        else:
            # Create minimal sidecar from job metadata
            import json as _json
            sidecar = {
                "prompt": job.get("prompt", ""),
                "job_id": job_id,
                "score": req.score,
                "trigger_word": req.trigger_word,
                "approved": True,
            }
            _Path(str(dst_img) + ".json").write_text(_json.dumps(sidecar, indent=2))

        # Enqueue a mini LoRA training run on the approved dataset
        trigger = req.trigger_word or (job.get("prompt", "concept") or "concept").split()[0]
        training_payload = {
            "name": f"feedback_{job_id[:8]}",
            "dataset_dir": str(approved_dir),
            "base_profile": req.base_profile,
            "trigger_word": trigger,
            "steps": 150,
            "learning_rate": 1e-4,
            "max_images": 50,
            "trainer_mode": "execute",
        }
        run = _store_create_image_training_run(training_payload)
        response["training_run_id"] = run["run_id"]
        response["training_status"] = run["status"]
        response["dataset_dir"] = str(approved_dir)
        logger.info(
            "Approved art job %s queued as training run %s (trigger=%s)",
            job_id, run["run_id"], trigger,
        )

    return response


# --- Voice Synthesis Endpoint ---
class TrainingVoiceSpeakRequest(BaseModel):
    text: str
    pitch: int = 3
    method: str = "rmvpe"
    speed: float = 1.0


@app.post("/api/v1/training/voice/speak")
async def training_voice_speak(req: TrainingVoiceSpeakRequest):
    """Synthesize a WAV clip via the BMO voice service and return audio bytes."""
    import requests as _requests

    bmo_url = os.getenv("BMO_VOICE_URL", "http://voice_engine_gpu:8020").rstrip("/")
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    params = {
        "text": text,
        "pitch": req.pitch,
        "speed": req.speed,
        "method": req.method,
    }

    try:
        resp = _requests.post(f"{bmo_url}/speak", params=params, timeout=90)
        if resp.status_code != 200:
            logger.error(
                "[VoiceSpeak] BMO voice service error status=%s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            raise HTTPException(status_code=502, detail=f"BMO voice service returned {resp.status_code}")

        return Response(content=resp.content, media_type="audio/wav")
    except Exception as e:
        logger.error("[VoiceSpeak] Voice synthesis proxy failed: %s", e)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=502, detail=str(e)[:200])


# --- Knowledge Ingestion Endpoints ---
@app.post("/api/v1/knowledge/ingest")
async def knowledge_ingest():
    """Ingest text content into the knowledge base (RAG)."""
    from fastapi import Request
    import requests as _requests
    # This is a placeholder that will be wired to the actual RAG pipeline
    return {"status": "accepted", "message": "Knowledge ingestion endpoint ready"}


@app.post("/api/v1/knowledge/ingest_file")
async def knowledge_ingest_file():
    """Ingest file content into the knowledge base (RAG)."""
    return {"status": "accepted", "message": "File ingestion endpoint ready"}


# ---------------------------------------------------------------------------
# Service Health Check + Restart Endpoints
# ---------------------------------------------------------------------------

SERVICE_REGISTRY = [
    # Turing Gateway services
    {"id": "grafana",      "name": "Grafana",        "node": "Turing",         "ip": "192.168.2.103", "port": 3001, "container": "grafana-Turing",      "health_url": "http://192.168.2.103:3001/grafana/api/health"},
    {"id": "prometheus",   "name": "Prometheus",      "node": "Turing",         "ip": "192.168.2.103", "port": 9091, "container": "prometheus-Turing",   "health_url": "http://192.168.2.103:9091/prometheus/-/healthy"},
    {"id": "loki",         "name": "Loki",            "node": "Turing",         "ip": "192.168.2.103", "port": 3100, "container": "loki-Turing",         "health_url": "http://192.168.2.103:3100/ready"},
    {"id": "alertmanager", "name": "Alertmanager",    "node": "Turing",         "ip": "192.168.2.103", "port": 9093, "container": "alertmanager-Turing", "health_url": "http://192.168.2.103:9093/alertmanager/-/healthy"},
    {"id": "cadvisor",     "name": "cAdvisor",        "node": "Turing",         "ip": "192.168.2.103", "port": 8888, "container": "cadvisor-Turing",     "health_url": None},
    {"id": "ollama-Turing",  "name": "Ollama (Turing)",   "node": "Turing",         "ip": "192.168.2.103", "port": 11434,"container": "ollama-Turing",       "health_url": "http://192.168.2.103:11434/"},
    {"id": "redis-Turing",   "name": "Redis (Turing)",    "node": "Turing",         "ip": "192.168.2.103", "port": 6379, "container": "redis-Turing",        "health_url": None},
    # Control Node services
    {"id": "langfuse",     "name": "Langfuse",        "node": "Hopper", "ip": "192.168.2.102", "port": 3000, "container": "langfuse-web",      "health_url": "http://192.168.2.102:3000/api/public/health"},
    {"id": "postgres",     "name": "PostgreSQL",      "node": "Hopper", "ip": "192.168.2.102", "port": 5432, "container": "postgres",          "health_url": None},
    {"id": "clickhouse",   "name": "ClickHouse",      "node": "Hopper", "ip": "192.168.2.102", "port": 8123, "container": "clickhouse",        "health_url": "http://192.168.2.102:8123/ping"},
    {"id": "minio",        "name": "MinIO",           "node": "Hopper", "ip": "192.168.2.102", "port": 9190, "container": "minio",             "health_url": "http://192.168.2.102:9190/minio/health/live"},
    {"id": "redis-ctrl",   "name": "Redis (Control)", "node": "Hopper", "ip": "192.168.2.102", "port": 6379, "container": "redis",             "health_url": None},
    {"id": "spire",        "name": "SPIRE Server",    "node": "Hopper", "ip": "192.168.2.102", "port": 8081, "container": "spire-server",      "health_url": None},
    {"id": "mempalace",    "name": "MemPalace",       "node": "Hopper", "ip": "192.168.2.102", "port": 8200, "container": "mempalace",         "health_url": "http://192.168.2.102:8200/health"},
    # Execution Node services
    {"id": "ollama-exec",  "name": "Ollama (Exec)",   "node": "Lovelace",    "ip": "192.168.2.101", "port": 11434,"container": "ollama",            "health_url": "http://192.168.2.101:11434/"},
]

NODE_DOCKER_SOCKETS = {
    "Turing":         "http://192.168.2.103:2375",
    "Hopper": "http://192.168.2.102:2375",
    "Lovelace":    "http://192.168.2.101:2375",
}


@app.get("/api/v1/ops/services")
async def ops_service_checks():
    """Deep connectivity check for every registered service."""
    import socket
    import time
    import requests as _requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def check_one(svc: dict) -> dict:
        result = {
            "id": svc["id"], "name": svc["name"], "node": svc["node"],
            "ip": svc["ip"], "port": svc["port"], "container": svc["container"],
            "healthy": False, "latency_ms": None, "detail": "",
        }
        t0 = time.time()
        try:
            if svc["health_url"]:
                r = _requests.get(svc["health_url"], timeout=4)
                result["healthy"] = r.status_code < 500
                result["detail"] = f"HTTP {r.status_code}"
            else:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                code = s.connect_ex((svc["ip"], svc["port"]))
                s.close()
                result["healthy"] = code == 0
                result["detail"] = "TCP open" if code == 0 else f"TCP refused (code {code})"
        except _requests.exceptions.ConnectTimeout:
            result["detail"] = "Connect timeout"
        except _requests.exceptions.ConnectionError as e:
            result["detail"] = f"Connection error: {str(e)[:80]}"
        except Exception as e:
            result["detail"] = str(e)[:100]
        result["latency_ms"] = round((time.time() - t0) * 1000)
        return result

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(check_one, svc): svc for svc in SERVICE_REGISTRY}
        for fut in as_completed(futures):
            results.append(fut.result())

    node_order = {"Turing": 0, "Hopper": 1, "Lovelace": 2}
    results.sort(key=lambda r: (node_order.get(r["node"], 99), r["name"]))

    healthy_count = sum(1 for r in results if r["healthy"])
    return {
        "services": results,
        "summary": {
            "total": len(results),
            "healthy": healthy_count,
            "unhealthy": len(results) - healthy_count,
        },
    }


@app.post("/api/v1/ops/services/{service_id}/restart")
async def ops_service_restart(service_id: str):
    """Restart a specific service container via Docker API."""
    import requests as _requests

    svc = next((s for s in SERVICE_REGISTRY if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_id}")

    docker_url = NODE_DOCKER_SOCKETS.get(svc["node"])
    if not docker_url:
        raise HTTPException(status_code=500, detail=f"No docker socket configured for node {svc['node']}")

    container = svc["container"]
    try:
        resp = _requests.post(f"{docker_url}/containers/{container}/restart?t=10", timeout=30)
        if resp.status_code == 204:
            return {"status": "restarted", "service": svc["name"], "node": svc["node"], "container": container}
        elif resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Container '{container}' not found on {svc['node']}")
        else:
            raise HTTPException(status_code=502, detail=f"Docker API returned {resp.status_code}: {resp.text[:200]}")
    except _requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Cannot reach Docker socket proxy on {svc['node']} ({docker_url})")
    except _requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail=f"Restart timed out for {container} on {svc['node']}")


# ---------------------------------------------------------------------------
# Fleet panel — administer ANY container by (node, name), not just the
# 16 registry services. Backs the Fleet tab in /mission-control.
# ---------------------------------------------------------------------------

def _docker_url_for_node(node: str) -> str:
    """Resolve a node name (case-insensitive) to its docker socket-proxy URL."""
    for k, v in NODE_DOCKER_SOCKETS.items():
        if k.lower() == node.lower():
            return v
    raise HTTPException(status_code=404, detail=f"Unknown node: {node}")


def _demux_docker_logs(raw: bytes) -> str:
    """Decode a Docker /logs stream.

    Non-TTY containers return a multiplexed stream: each frame is an 8-byte
    header [stream(1), 0,0,0, size(4 big-endian)] followed by `size` payload
    bytes. TTY containers return the payload raw. Best-effort: fall back to a
    plain decode if the framing doesn't parse cleanly.
    """
    if not raw:
        return ""
    out = []
    i, n = 0, len(raw)
    try:
        while i + 8 <= n:
            stream_type = raw[i]
            size = int.from_bytes(raw[i + 4:i + 8], "big")
            # Header sanity: stream_type is 0/1/2 and frame fits in the buffer.
            if stream_type not in (0, 1, 2) or i + 8 + size > n:
                raise ValueError("not multiplexed")
            out.append(raw[i + 8:i + 8 + size].decode("utf-8", errors="replace"))
            i += 8 + size
        if out:
            return "".join(out)
    except Exception:
        pass
    return raw.decode("utf-8", errors="replace")


@app.get("/api/v1/ops/fleet/{node}/{container}/logs")
async def ops_fleet_logs(node: str, container: str, tail: int = 200):
    """Fetch recent stdout+stderr for a container (via Docker socket-proxy)."""
    import requests as _requests

    docker_url = _docker_url_for_node(node)
    tail = max(1, min(tail, 1000))
    endpoint = (
        f"{docker_url}/containers/{container}/logs"
        f"?stdout=true&stderr=true&tail={tail}&timestamps=false"
    )
    try:
        resp = _requests.get(endpoint, timeout=10)
    except _requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Cannot reach Docker socket proxy on {node} ({docker_url})")
    except _requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail=f"Log fetch timed out for {container} on {node}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Container '{container}' not found on {node}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Docker API returned {resp.status_code}: {resp.text[:200]}")
    return {"node": node, "container": container, "tail": tail, "logs": _demux_docker_logs(resp.content)}


@app.get("/api/v1/ops/gpu-lock")
def ops_gpu_lock_status():
    """Current GPU-lease status (proxied from the authoritative GPU_LOCK_HOST)."""
    import requests as _requests
    from config import GPU_LOCK_HOST

    try:
        resp = _requests.get(f"{GPU_LOCK_HOST}/internal/gpu-lock/status", timeout=4)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        # Surface as "unknown" rather than 500 so the panel degrades gracefully.
        return {"locked": None, "holder_context": None, "remaining_s": None,
                "error": f"GPU lock host unreachable: {str(e)[:100]}"}


@app.post("/api/v1/ops/gpu-lock/clear")
def ops_gpu_lock_clear():
    """Force-clear a stuck GPU lease (operator action)."""
    import os
    import requests as _requests
    from config import GPU_LOCK_HOST

    headers = {}
    secret = os.getenv("GPU_LOCK_SECRET", "")
    if secret:
        headers["X-GPU-Lock-Secret"] = secret
    try:
        resp = _requests.post(f"{GPU_LOCK_HOST}/internal/gpu-lock/clear", headers=headers, timeout=6)
    except _requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Cannot reach GPU lock host ({GPU_LOCK_HOST})")
    except _requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="GPU lock clear timed out")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"GPU lock host: {resp.text[:200]}")
    return resp.json()


# ---------------------------------------------------------------------------
# Agent View — live snapshot of active swarm coordination sessions + workers.
# Backs the rebuilt /monitoring/swarm-observer surface (polled).
# ---------------------------------------------------------------------------

@app.get("/api/v1/swarm/sessions")
def swarm_sessions():
    """Currently-running coordination sessions with per-worker phase/state/model."""
    try:
        from coordination.session import snapshot_active_sessions
        sessions = snapshot_active_sessions()
    except Exception as e:
        return {"sessions": [], "count": 0, "error": f"snapshot failed: {str(e)[:120]}"}

    # Enrich each worker with its resolved model (best-effort; role → model).
    try:
        from role_model_resolver import get_model_for_role
        for s in sessions:
            owner = s.get("owner_id")
            for w in s.get("workers", []):
                try:
                    w["model"] = get_model_for_role(owner, w.get("role", ""))
                except Exception:
                    w["model"] = None
    except Exception:
        pass

    return {"sessions": sessions, "count": len(sessions)}


if __name__ == "__main__":
    # If run directly via python, use uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ---------------------------------------------------------------------------
# PROVIDER KEYS — Per-user API key management for external LLM providers
# ---------------------------------------------------------------------------

class _ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str
    label: str = ""


@app.get("/api/v1/provider-keys/providers")
async def provider_keys_catalog():
    """Return the catalog of supported providers and their models."""
    try:
        from provider_keys import PROVIDERS
        # Don't expose internal fields like key_prefix
        return {
            provider_id: {
                "label": info["label"],
                "models": info.get("models", []),
            }
            for provider_id, info in PROVIDERS.items()
        }
    except Exception as e:
        logger.error(f"provider_keys_catalog error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/provider-keys/list")
async def provider_keys_list(http_request: Request):
    """List the providers the current user has connected (no keys exposed)."""
    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        from provider_keys import list_connected
        return {"providers": list_connected(uid)}
    except Exception as e:
        logger.error(f"provider_keys_list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/provider-keys/connect")
async def provider_keys_connect(body: _ProviderKeyRequest, http_request: Request):
    """Store or update a provider API key for the current user."""
    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        from provider_keys import upsert_key, PROVIDERS
        if body.provider not in PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {body.provider}. Supported: {list(PROVIDERS.keys())}"
            )
        upsert_key(uid, body.provider, body.api_key, body.label)
        if body.provider == "nvidia":
            try:
                from providers.nvidia_entitlement import invalidate as _nv_invalidate
                _nv_invalidate(uid)
            except Exception:
                pass
        return {"status": "connected", "provider": body.provider}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"provider_keys_connect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/provider-keys/{provider}")
async def provider_keys_disconnect(provider: str, http_request: Request):
    """Remove a stored provider key for the current user."""
    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        from provider_keys import delete_key
        deleted = delete_key(uid, provider)
        if provider == "nvidia":
            try:
                from providers.nvidia_entitlement import invalidate as _nv_invalidate
                _nv_invalidate(uid)
            except Exception:
                pass
        return {"disconnected": deleted, "provider": provider}
    except Exception as e:
        logger.error(f"provider_keys_disconnect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GITHUB OAUTH — Device Flow endpoints (Phase 1C)
# ---------------------------------------------------------------------------

class _DeviceAuthResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int

class _DevicePollRequest(BaseModel):
    device_code: str


@app.post("/api/v1/github/device-authorize")
async def github_device_authorize(http_request: Request):
    """
    Step 1: Initiate GitHub Device Flow.
    Returns user_code, verification_uri, device_code for the frontend to display.
    """
    import urllib.request as _ur
    import urllib.parse as _up

    client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="GITHUB_OAUTH_CLIENT_ID not configured")

    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = _up.urlencode({"client_id": client_id, "scope": "read:user"}).encode()
    req = _ur.Request(
        "https://github.com/login/device/code",
        data=payload,
        headers={"Accept": "application/json"},
        method="POST",
    )
    try:
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.error(f"github_device_authorize: upstream error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")

    if "error" in data:
        raise HTTPException(status_code=400, detail=data.get("error_description", data["error"]))

    return {
        "device_code": data["device_code"],
        "user_code": data["user_code"],
        "verification_uri": data["verification_uri"],
        "expires_in": data.get("expires_in", 900),
        "interval": data.get("interval", 5),
    }


@app.post("/api/v1/github/device-poll")
async def github_device_poll(body: _DevicePollRequest, http_request: Request):
    """
    Step 2: Poll GitHub for Device Flow completion.
    On success, fetches github username and stores encrypted token.
    Returns {status: 'pending'|'authorized'|'error', username?: str}
    """
    import urllib.request as _ur
    import urllib.parse as _up

    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")

    client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="GITHUB_OAUTH_CLIENT_ID not configured")

    payload = _up.urlencode({
        "client_id": client_id,
        "device_code": body.device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }).encode()
    req = _ur.Request(
        "https://github.com/login/oauth/access_token",
        data=payload,
        headers={"Accept": "application/json"},
        method="POST",
    )
    try:
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.error(f"github_device_poll: upstream error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")

    error = data.get("error")
    if error == "authorization_pending":
        return {"status": "pending"}
    if error == "slow_down":
        return {"status": "pending", "slow_down": True}
    if error:
        return {"status": "error", "message": data.get("error_description", error)}

    access_token = data.get("access_token")
    if not access_token:
        return {"status": "error", "message": "No access_token in response"}

    # Fetch GitHub username
    user_req = _ur.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    try:
        with _ur.urlopen(user_req, timeout=10) as resp:
            user_data = json.loads(resp.read())
        github_username = user_data.get("login", "unknown")
    except Exception as e:
        logger.warning(f"github_device_poll: could not fetch username: {e}")
        github_username = "unknown"

    # Store encrypted token
    try:
        from github_oauth import upsert_token
        upsert_token(
            user_id=uid,
            github_username=github_username,
            access_token=access_token,
            scopes=data.get("scope", "read:user"),
        )
    except Exception as e:
        logger.error(f"github_device_poll: token storage failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store token: {e}")

    return {"status": "authorized", "username": github_username}


@app.get("/api/v1/github/status")
async def github_status(http_request: Request):
    """Return whether the current user has a connected GitHub account."""
    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        from github_oauth import get_token
        record = get_token(uid)
    except Exception as e:
        logger.error(f"github_status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not record:
        return {"connected": False}
    return {
        "connected": True,
        "username": record.github_username,
        "scopes": record.scopes,
        "connected_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.delete("/api/v1/github/disconnect")
async def github_disconnect(http_request: Request):
    """Remove the stored GitHub token for the current user."""
    uid = http_request.headers.get("X-authentik-uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        from github_oauth import delete_token
        deleted = delete_token(uid)
    except Exception as e:
        logger.error(f"github_disconnect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return {"disconnected": deleted}


# ---------------------------------------------------------------------------
# GITHUB PUSH TOKENS — fine-grained PAT for repo-write access (Phase C of the
# Codex-task-composer plan). Structurally separate from the OAuth device flow
# above: github_oauth_tokens is a read:user credential consumed as an
# LLM-provider identity; this is a human-pasted PAT scoped for git push / PR
# creation, stored in its own swarm.github_push_tokens table
# (agents/github_push_tokens.py). This module is settings-page-only and
# human-driven — it is never imported by agents/dev_harness/tool_defs.py and
# never registered in TOOL_DISPATCH, so the LLM agent itself can never reach
# it (see agents/tools/sandbox_ops.py's _GIT_ALLOW safety boundary).
# ---------------------------------------------------------------------------

class _GithubPushTokenRequest(BaseModel):
    token: str


@app.post("/api/v1/github/push/token")
async def github_push_connect(body: _GithubPushTokenRequest, http_request: Request):
    """
    Connect a fine-grained GitHub PAT for repo-write access.

    Validates the token live against GET https://api.github.com/user BEFORE
    ever storing it — an invalid/expired token is rejected with 400 and never
    reaches swarm.github_push_tokens.
    """
    owner_id = _resolve_owner_id(None, http_request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = (body.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    import urllib.request as _ur
    import urllib.error as _ue

    user_req = _ur.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with _ur.urlopen(user_req, timeout=10) as resp:
            user_data = json.loads(resp.read())
    except _ue.HTTPError as e:
        if e.code == 401:
            raise HTTPException(status_code=400, detail="Invalid or expired GitHub token")
        logger.warning(f"github_push_connect: GitHub API error {e.code} for owner_id={owner_id}")
        raise HTTPException(status_code=400, detail=f"GitHub API error: {e.code}")
    except Exception as e:
        logger.warning(f"github_push_connect: validation failed for owner_id={owner_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not reach GitHub: {e}")

    github_username = user_data.get("login")
    if not github_username:
        raise HTTPException(status_code=400, detail="GitHub API did not return a username")

    import github_push_tokens
    github_push_tokens.upsert_token(owner_id, github_username, token)

    status = github_push_tokens.get_status(owner_id)
    if not status:
        raise HTTPException(status_code=500, detail="Token validated but failed to store")
    return {"connected": True, "github_username": status["github_username"]}


@app.get("/api/v1/github/push/status")
async def github_push_status(http_request: Request):
    """Return whether the current user has a connected repo-write PAT (never the token)."""
    owner_id = _resolve_owner_id(None, http_request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    import github_push_tokens
    status = github_push_tokens.get_status(owner_id)
    return status or {"connected": False}


@app.delete("/api/v1/github/push/token")
async def github_push_disconnect(http_request: Request):
    """Remove the stored repo-write PAT for the current user."""
    owner_id = _resolve_owner_id(None, http_request)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    import github_push_tokens
    deleted = github_push_tokens.delete_token(owner_id)
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# DEV TERMINAL — WebSocket proxy to a per-session dev sandbox container
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    """
    WebSocket terminal: opens a shell inside a dev sandbox container and
    pipes stdin/stdout/stderr bidirectionally.
    Requires X-authentik-uid header (passed as query param ?uid=... because
    browsers cannot set custom WS headers). Optional ?session=... scopes the
    underlying container the same way _dev_harness_stream's chat turns do
    (falls back to uid if omitted — one container per session key, reused
    across reconnects); optional ?projectId=... selects which dev_projects
    row that session's container is provisioned for (falls back to the
    per-owner live-repo project, same default as chat).
    """
    import asyncio
    import docker as docker_sdk

    uid = websocket.query_params.get("uid", "").strip()
    if not uid:
        await websocket.close(code=4001, reason="Authentication required")
        return

    session_param = websocket.query_params.get("session", "").strip()
    project_id = websocket.query_params.get("projectId", "").strip()

    await websocket.accept()

    # Resolve which container this terminal targets — same session_sandbox
    # mechanism and project-resolution logic as Phase F's _dev_harness_stream,
    # instead of the historical hardcoded "dev_sandbox" literal. Falls back to
    # that literal when SESSION_SANDBOX_ENABLED is off, matching every other
    # entry point's off-switch behavior.
    container_name = "dev_sandbox"
    try:
        from coordination.orchestrator import SESSION_SANDBOX_ENABLED as _term_sse
        if _term_sse:
            from dev_projects import store as _dev_projects_store
            from dev_projects.repo_context import build_repo_context
            from coordination.session_sandbox import ensure_session_container
            from coordination.sandbox_identity import set_current_container
            from coordination.workspace_ops import checkout_repo_branch

            project = None
            if project_id:
                project = _dev_projects_store.get_project(project_id, uid)
            if not project:
                project = _dev_projects_store.get_or_create_live_repo_project(uid)

            mode = "live_repo" if project.get("source") == "live_repo" else "ephemeral"
            session_key = session_param or uid
            container_name, _term_created = ensure_session_container(session_key, mode=mode)

            if _term_created and mode == "ephemeral" and project.get("git_url"):
                set_current_container(container_name)
                try:
                    _rc = build_repo_context(project)
                    checkout_repo_branch(_rc["git_url"], _rc["branch"], _rc["base_branch"])
                finally:
                    set_current_container(None)
    except Exception as e:
        logger.error(f"terminal_ws session container setup failed for uid={uid}: {e}", exc_info=True)
        await websocket.send_text(f"\r\n\x1b[31mTerminal session setup failed: {e}\x1b[0m\r\n")
        await websocket.close(code=4003, reason="Session setup failed")
        return

    try:
        client = docker_sdk.from_env()
        try:
            container = client.containers.get(container_name)
        except docker_sdk.errors.NotFound:
            await websocket.send_text(f"\r\n\x1b[31m{container_name} container not found. Is it running?\x1b[0m\r\n")
            await websocket.close(code=4002, reason="Sandbox unavailable")
            return

        # Create exec instance: bash login shell
        exec_id = client.api.exec_create(
            container.id,
            cmd=["/bin/bash", "-l"],
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True,
            environment={"TERM": "xterm-256color"},
        )
        sock = client.api.exec_start(exec_id["Id"], detach=False, tty=True, socket=True)
        # Unwrap the underlying socket
        raw_sock = sock._sock if hasattr(sock, "_sock") else sock
        raw_sock.setblocking(False)

        loop = asyncio.get_event_loop()

        async def forward_output():
            """Read from container PTY → send to WebSocket."""
            while True:
                try:
                    data = await loop.run_in_executor(None, raw_sock.recv, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
                except (OSError, BlockingIOError):
                    await asyncio.sleep(0.01)
                except Exception:
                    break

        async def forward_input():
            """Read from WebSocket → write to container PTY."""
            while True:
                try:
                    msg = await websocket.receive()
                    if "bytes" in msg:
                        raw_sock.sendall(msg["bytes"])
                    elif "text" in msg:
                        # Resize event: {"type":"resize","cols":N,"rows":N}
                        try:
                            cmd = json.loads(msg["text"])
                            if cmd.get("type") == "resize":
                                client.api.exec_resize(
                                    exec_id["Id"],
                                    height=cmd.get("rows", 24),
                                    width=cmd.get("cols", 80),
                                )
                        except Exception:
                            raw_sock.sendall(msg["text"].encode())
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

        await asyncio.gather(forward_output(), forward_input())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"terminal_ws error for uid={uid}: {e}", exc_info=True)
        try:
            await websocket.send_text(f"\r\n\x1b[31mTerminal error: {e}\x1b[0m\r\n")
            await websocket.close(code=1011)
        except Exception:
            pass




