
import logging
import sys
import os
import json
import uuid
import time
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
            logger.info(f"Trigger Scheduler started: {trigger_sched.count()} triggers")
        except ImportError as e:
            logger.warning(f"Trigger scheduler not available: {e}")
        except Exception as e:
            logger.warning(f"Trigger scheduler init failed (non-fatal): {e}")

        # 7. Clean up orphaned training runs (status='running' but server restarted)
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

        print("DEBUG: Startup Complete. Yielding...")
        logger.info("Swarm Engine Online. Waiting for events...")
        yield
        # Shutdown
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

# Staged rollout: parse mode logs policy mismatches without blocking,
# soft/hard modes enforce endpoint-class policy in AuthorizationMiddleware.
app.add_middleware(AuthorizationMiddleware)

# --- Global Exception Handler (To capture crashes before uvicorn swallows them) ---
from fastapi import Request
from fastapi.responses import JSONResponse, Response

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

# Mount Delivered Artifacts for remote downloading (Satellite)
if os.path.exists("/workspace/delivered_artifacts"):
    app.mount("/delivered_artifacts", StaticFiles(directory="/workspace/delivered_artifacts"), name="artifacts")

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
    return {"status": "online", "system": "Home AI Lab Swarm"}

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
        groups_raw = request.headers.get("X-authentik-groups", "")
        groups = [g.strip() for g in groups_raw.split("|") if g.strip()]
        is_admin = "admins" in groups
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

# --- Voice Assistant Endpoint ---
class VoiceRequest(BaseModel):
    text: str

# Persist agent to avoid re-initializing Ollama/Phidata every request (reduces latency)
_voice_agent = None

def get_voice_agent():
    global _voice_agent
    if _voice_agent is None:
        from specialized.voice_assistant import VoiceAssistantAgent
        _voice_agent = VoiceAssistantAgent()
    return _voice_agent

@app.post("/v1/voice/chat")
async def voice_chat(request: VoiceRequest):
    """
    Dedicated endpoint for Voice Satellite.
    Returns text response AND audio path.
    """
    from specialized.voice_assistant import Message
    
    import asyncio as _aio
    agent = get_voice_agent()
    # Process message (run in thread to avoid blocking the async event loop)
    response_msg = await _aio.to_thread(agent.process, Message(role="user", content=request.text))
    metadata = response_msg.metadata or {}

    return {
        "text": response_msg.content,
        "audio_path": metadata.get("audio_path"),
        "sandbox": {
            "emotion": metadata.get("emotion"),
            "pitch": metadata.get("pitch"),
            "speed": metadata.get("speed"),
            "sample_match": metadata.get("sample_match"),
            "response_sample": metadata.get("response_sample"),
            "sample_file": metadata.get("sample_file"),
            "sample_url": metadata.get("sample_url"),
            "audio_kind": metadata.get("audio_kind"),
        },
    }

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
    grounding_web: bool = False       # inject live web search results (requires governance permission)
    grounding_docs: bool = False      # inject knowledge-base document chunks (requires governance permission)
    grounding_file: bool = False      # inject local workspace file content (requires governance permission)
    swarm_mode: bool = False          # route through Lamport multi-agent coordinator
    solving_max_iter: Optional[int] = None  # MarsRL max iterations (0 = unlimited, overrides config)
    solving_max_time: Optional[int] = None  # MarsRL max time in seconds (0 = unlimited, overrides config)


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
# Dev tool definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

DEV_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /workspace (e.g. 'src/app.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file in the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /workspace",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete new content for the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory in the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to /workspace (default: '.')",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a shell command in the dev sandbox. "
                "The sandbox has Python 3, Node.js 20, git, and common build tools. "
                "Use this to run tests, install packages, build projects, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory relative to /workspace (optional)",
                    },
                },
                "required": ["command"],
            },
        },
    },
]


def _resolve_owner_id(payload_user_id: Optional[str], request: Request) -> Optional[str]:
    """Resolve a stable owner identifier from request payload or authenticated context."""
    # DEBUG: Log all headers to understand what's being received
    auth_headers = {
        "X-authentik-uid": request.headers.get("X-authentik-uid", ""),
        "X-authentik-username": request.headers.get("X-authentik-username", ""),
        "X-authentik-email": request.headers.get("X-authentik-email", ""),
    }
    logger.debug(f"[owner_id] payload={payload_user_id}, headers={auth_headers}")
    
    if payload_user_id:
        logger.info(f"[owner_id] Resolved from payload: {payload_user_id}")
        return payload_user_id

    # Check Authentik forward-auth headers (injected by Traefik forwardAuth middleware)
    authentik_uid = request.headers.get("X-authentik-uid", "").strip()
    if authentik_uid:
        logger.info(f"[owner_id] Resolved from X-authentik-uid: {authentik_uid}")
        return authentik_uid
    authentik_user = request.headers.get("X-authentik-username", "").strip()
    if authentik_user:
        logger.info(f"[owner_id] Resolved from X-authentik-username: {authentik_user}")
        return authentik_user

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

    if auto_scope != "none" and tool_name:
        _apply_auto_approve(uid, tool_name, auto_scope)

    _approval_decisions[call_id] = True
    event = _approval_events.pop(call_id, None)
    if event:
        event.set()
    logger.info(f"[dev_approve] call_id={call_id} uid={uid} auto={auto_scope} approved")
    return {"ok": True}


@app.post("/api/v1/dev/deny/{call_id}")
async def deny_tool_call(call_id: str, http_request: Request):
    """Deny a pending tool call from the AI agent."""
    uid = http_request.headers.get("X-authentik-uid", "").strip() or "default"
    _approval_decisions[call_id] = False
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


@app.get("/v1/models")
async def list_models(request: Request):
    """
    OpenAI-compatible /v1/models.
    Returns local swarm models + GitHub Models if the user has a connected account.
    """
    try:
        base_models = [
            {"id": "swarm-standard",  "object": "model", "created": int(time.time()), "owned_by": "MarsRL"},
            {"id": "Home-AI-Swarm",   "object": "model", "created": int(time.time()), "owned_by": "MarsRL"},
        ]

        # Append GitHub Models if this user has a connected token
        uid = request.headers.get("X-authentik-uid", "").strip()
        if uid:
            try:
                from github_oauth import get_token
                from providers.github_models_provider import GITHUB_MODELS
                if get_token(uid):
                    for m in GITHUB_MODELS:
                        base_models.append({
                            "id": m["id"],
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "github",
                            "context_window": m.get("context"),
                        })
            except Exception as e:
                logger.warning(f"list_models: could not fetch GitHub models: {e}")

        return {"object": "list", "data": base_models}
    except Exception as e:
        logger.error(f"Error in list_models: {e}")
        raise

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, http_request: Request):
    """
    Standard Chat API to allow external tools (Open-WebUI, VS Code) to talk to the Swarm.
    """
    from fastapi.responses import StreamingResponse
    from church import chat_swarm
    import json
    import asyncio

    # Route GitHub Models requests directly to the GitHubModelsProvider
    if request.model.startswith("github/"):
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

                # --- Phase 2: agentic dev mode ---
                if request.dev_mode:
                    from prompts.hivecode import HIVECODE_SYSTEM_PROMPT
                    from tools.sandbox_ops import execute_tool as _sandbox_execute

                    # Prepend HiveCode system prompt
                    dev_msgs = [{"role": "system", "content": HIVECODE_SYSTEM_PROMPT}] + msgs

                    async def _tool_executor(call_id: str, tool_name: str, args: dict) -> str:
                        """Wraps sandbox execution with optional approval gate."""
                        if not _is_auto_approved(uid, tool_name):
                            # Emit approval-needed event first
                            approval_event = {
                                "id": "chatcmpl-github",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": request.model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "type": "tool_approval_needed",
                                        "tool_call_id": call_id,
                                        "tool_name": tool_name,
                                        "tool_input": args,
                                        "content": f"Approval required: {tool_name}",
                                    },
                                    "finish_reason": None,
                                }],
                            }
                            # We can't yield from a non-generator coroutine, so we
                            # store the event data for the outer loop to pick up.
                            _pending_tool_approvals[call_id] = approval_event
                            # Create an asyncio.Event for this call
                            event = _asyncio.Event()
                            _approval_events[call_id] = event
                            try:
                                await _asyncio.wait_for(event.wait(), timeout=120.0)
                            except _asyncio.TimeoutError:
                                _approval_decisions.pop(call_id, None)
                                return f"Tool {tool_name!r} approval timed out after 120 s — skipped."
                            approved = _approval_decisions.pop(call_id, False)
                            if not approved:
                                return f"Tool {tool_name!r} was denied by the user."
                        # Execute in thread executor to avoid blocking the event loop
                        import asyncio as _aio
                        loop = _aio.get_event_loop()
                        result = await loop.run_in_executor(None, _sandbox_execute, tool_name, args)
                        return result

                    # Dict for the outer generator to flush approval-needed events before waiting
                    _pending_tool_approvals: dict[str, dict] = {}

                    async for chunk in provider.generate_stream_with_tools(
                        dev_msgs, DEV_TOOL_DEFINITIONS, _tool_executor
                    ):
                        # First flush any pending approval event for the same call_id
                        if chunk.type == "tool_start" and chunk.tool_call_id in _pending_tool_approvals:
                            # Not needed yet — approval events are emitted from within _tool_executor
                            pass
                        # Flush stored approval-needed event if present
                        for pending_id, pending_sse in list(_pending_tool_approvals.items()):
                            yield f"data: {json.dumps(pending_sse)}\n\n"
                            del _pending_tool_approvals[pending_id]

                        # Build SSE for this chunk
                        delta: dict = {"type": chunk.type, "content": chunk.content}
                        if chunk.tool_name:
                            delta["tool_name"] = chunk.tool_name
                        if chunk.tool_input is not None:
                            delta["tool_input"] = chunk.tool_input
                        if chunk.tool_call_id:
                            delta["tool_call_id"] = chunk.tool_call_id
                        if chunk.type == "tool_result":
                            delta["tool_output"] = chunk.content

                        sse = {
                            "id": "chatcmpl-github",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": request.model,
                            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(sse)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

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
                    swarm_mode=request.swarm_mode,
                    dev_mode=request.dev_mode,
                    solving_max_iter=request.solving_max_iter,
                    solving_max_time=request.solving_max_time,
                )
            except Exception as e:
                logger.error(f"[Stream] chat_swarm init failed: {e}")
                yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':0,'model':request.model,'choices':[{'index':0,'delta':{'content':f'Error: {e}'},'finish_reason':None}]})}\n\n"
                yield "data: [DONE]\n\n"
                return

            update_count = 0
            response_parts = []  # Collect response text for memory extraction
            _in_think_block = False  # Track <think> tag state across chunks

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

                        if msg_type not in ["message", "response", "error", "clarification_request", "media_attachment", "clarification_card", "model_queue_status"]:
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
                        if msg_type in ("status", "thought", "log", "plan",
                                        "turn_boundary", "turn_metadata",
                                        "continuation", "stream_mode",
                                        "clarification_request", "clarification_card",
                                        "media_attachment", "model_queue_status"):
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

                        # Collect response text for memory extraction
                        if msg_type in ("response", "message"):
                            response_parts.append(raw_content)

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

        except Exception as e:
            logger.error(f"Background training failed: {e}", exc_info=True)
            # Mark the early DB row as failed so it doesn't stay 'running' forever
            if _early_run_id:
                try:
                    from training.grpo_trainer import _update_training_run
                    _update_training_run(_early_run_id, "failed", error=str(e))
                except Exception as db_err:
                    logger.warning(f"[Training] Failed to mark DB row {_early_run_id} as failed: {db_err}")
            _active_training["status"] = "idle"
            _active_training["run_id"] = None

    background_tasks.add_task(_run_training)
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
            )
            status = "error" if result.startswith("Error") or result.startswith("Failed") else "ok"
            _art_job_finish(job_id, status, result)
        except Exception as e:
            logger.error(f"Art Studio image gen failed: {e}")
            _art_job_finish(job_id, "error", str(e))

    _art_asyncio.get_event_loop().create_task(_run())
    return {"job_id": job_id, "status": "running"}

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
        parsed = []
        for c in raw_containers or []:
            name = c.get("Names", ["/unknown"])
            if isinstance(name, list):
                name = (name[0] if name else "unknown").lstrip("/")
            image_raw = c.get("Image", "unknown")
            image = image_raw.split("/")[-1].split(":")[0]
            uptime = c.get("Status", "Unknown")
            parsed.append({"name": name, "image": image, "uptime": uptime, "status": "running"})
        return parsed

    def fetch_local_containers():
        try:
            result = subprocess.run(
                ["curl", "-s", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/json"],
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
                "GET /containers/json HTTP/1.0\r\n"
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
        endpoint = f"http://{ip_addr}:2375/containers/json"
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
            nodes.append({
                "name": node["name"], "role": node["role"], "ip": node["ip"],
                "healthy": True, "running_count": len(containers),
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

    bmo_url = os.getenv("BMO_VOICE_URL", "http://bmo-voice:8000").rstrip("/")
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
# DEV TERMINAL — WebSocket proxy to dev-sandbox container (Phase 1B)
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    """
    WebSocket terminal: opens a shell inside the dev-sandbox container and
    pipes stdin/stdout/stderr bidirectionally.
    Requires X-authentik-uid header (passed as query param ?uid=... because
    browsers cannot set custom WS headers).
    """
    import asyncio
    import docker as docker_sdk

    uid = websocket.query_params.get("uid", "").strip()
    if not uid:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()

    try:
        client = docker_sdk.from_env()
        try:
            container = client.containers.get("dev_sandbox")
        except docker_sdk.errors.NotFound:
            await websocket.send_text("\r\n\x1b[31mdev-sandbox container not found. Is it running?\x1b[0m\r\n")
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




