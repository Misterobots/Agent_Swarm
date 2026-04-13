
import logging
import sys
import os
import json
import uuid
# Ensure agents dir is in path
if "/app/agents" not in sys.path:
    sys.path.append("/app/agents")
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
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
from router import handle_task_event
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

        print("DEBUG: Startup Complete. Yielding...")
        logger.info("Swarm Engine Online. Waiting for events...")
        yield
        # Shutdown
        logger.info("Shutting down Swarm Engine...")
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
from fastapi.responses import JSONResponse

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
    Returns security_level from JWT-ACE token when present, else "anonymous".
    Public so the UI can call it without a token.
    """
    auth = get_spiffe_auth()
    my_id = auth.get_spiffe_id()

    # Try the middleware-attached agent card first (available when middleware validates)
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
    
    agent = get_voice_agent()
    # Process message
    response_msg = agent.process(Message(role="user", content=request.text))
    
    return {
        "text": response_msg.content,
        "audio_path": response_msg.metadata.get("audio_path") if response_msg.metadata else None
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
    attachments: Optional[List[dict]] = None  # file attachments [{name, mimeType, data, size}]


def _resolve_owner_id(payload_user_id: Optional[str], request: Request) -> Optional[str]:
    """Resolve a stable owner identifier from request payload or authenticated context."""
    if payload_user_id:
        return payload_user_id

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
        return f"session:{agent_card.session_id}"

    return None

@app.get("/v1/models")
async def list_models():
    """
    Mock OpenAI /v1/models endpoint so Open-WebUI can verify the connection.
    """
    logger.info("--- [DEBUG] /v1/models requested ---")
    import time
    try:
        # Check if we are shutting down immediately
        return {
            "object": "list",
            "data": [
                {
                    "id": "swarm-standard",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "MarsRL"
                },
                {
                    "id": "Home-AI-Swarm",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "MarsRL"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error in list_models: {e}")
        raise

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, http_request: Request):
    """
    Standard Chat API to allow external tools (Open-WebUI, VS Code) to talk to the Swarm.
    """
    from fastapi.responses import StreamingResponse
    from router import chat_swarm
    import json
    import asyncio

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
                    attachments=request.attachments,
                )
            except Exception as e:
                logger.error(f"[Stream] chat_swarm init failed: {e}")
                yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':0,'model':request.model,'choices':[{'index':0,'delta':{'content':f'Error: {e}'},'finish_reason':None}]})}\n\n"
                yield "data: [DONE]\n\n"
                return

            update_count = 0
            response_parts = []  # Collect response text for memory extraction
            try:
                for update in gen:
                    update_count += 1
                    logger.debug(f"[Stream] update #{update_count}: {update}")
                    # Update is expected to be a dict: {"type": ..., "content": ...}
                    if not isinstance(update, dict):
                        continue

                    msg_type = update.get("type", "response")
                    raw_content = update.get("content", "")

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

                        if msg_type not in ["message", "response", "error"]:
                            continue

                        content = raw_content
                    else:
                        # Format non-response items as markdown blockquotes for the Swarm UI
                        if msg_type == "status":
                            content = f"\n> ⏳ _{raw_content}_\n\n"
                        elif msg_type == "log":
                            content = f"\n> 🛠️ _{raw_content}_\n\n"
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
                        try:
                            from mempalace_client import mempalace
                            result = await asyncio.to_thread(
                                mempalace.extract, conv, owner_id=oid
                            )
                            logger.info(f"[MemPalace] Extraction complete: {len(result)} memories stored")
                        except Exception as exc:
                            logger.warning(f"[MemPalace] Background extraction failed: {exc}")

                    asyncio.get_event_loop().create_task(_bg_extract(conversation[:8000], owner_id))
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
            attachments=request.attachments,
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
                if msg_type == "status":
                    full_resp += f"\n> ⏳ _{raw_content}_\n\n"
                elif msg_type == "log":
                    full_resp += f"\n> 🛠️ _{raw_content}_\n\n"
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
                    try:
                        from mempalace_client import mempalace
                        result = await asyncio.to_thread(mempalace.extract, conv, owner_id=oid)
                        logger.info(f"[MemPalace] Extraction complete: {len(result)} memories stored")
                    except Exception as exc:
                        logger.warning(f"[MemPalace] Background extraction failed: {exc}")

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
from governance import governance_manager, RequestType, RequestStatus, RequestItem

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
    """
    item = governance_manager.update_status(req_id, update.status, update.note)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    logger.info(f"Request {req_id} updated to {update.status}")
    return item

# --- Node Health Endpoint (Phase 6) ---
@app.get("/api/v1/health/nodes")
async def health_nodes():
    """Returns health status of all Ollama inference nodes."""
    from inference.node_health import get_node_monitor
    monitor = get_node_monitor()
    return {"nodes": monitor.get_all_statuses()}


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
        _active_training["status"] = "running"
        _active_training["started_at"] = datetime.utcnow().isoformat()
        try:
            if req.run_type == "export":
                # Export traces only
                from training.export_traces import TraceExporter
                exporter = TraceExporter()
                count = await asyncio.to_thread(
                    exporter.export_dataset, template_id=req.template_id
                )
                _active_training["status"] = "idle"
                logger.info(f"Export complete: {count} traces")

            elif req.run_type == "curated":
                # Download curated datasets → security scan → train
                from training.dataset_curator import DatasetCurator
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig
                from config import TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS

                ds_keys = req.curated_datasets or ["glaive-function-calling", "hermes-function-calling"]
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

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, output_path, cfg)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            elif req.run_type == "synthetic":
                # Generate synthetic trajectories → security scan → train
                from training.synthetic_gen import SyntheticTrajectoryGenerator
                from training.dataset_curator import scan_existing_dataset
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig
                from config import TRAINING_DATASET_DIR, TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS

                target = req.synthetic_target or 552
                gen = SyntheticTrajectoryGenerator(output_dir=TRAINING_DATASET_DIR)
                count = await asyncio.to_thread(
                    gen.generate_dataset, target_count=target
                )
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

                # Security scan the generated data
                scan_report = await asyncio.to_thread(scan_existing_dataset, dataset_path)
                blocked = scan_report["scan_summary"].get("blocked", 0)
                if blocked > 0:
                    logger.warning(f"Security scan found {blocked} blocked samples in synthetic data")

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, dataset_path, cfg)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            elif req.run_type == "full_pipeline":
                # Export → Train
                from training.export_traces import TraceExporter
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig
                from config import TRAINING_DATASET_DIR, TRAINING_BASE_SOLVER, \
                    TRAINING_LORA_RANK, TRAINING_LEARNING_RATE, TRAINING_NUM_EPOCHS
                import glob

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

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, datasets_found[0], cfg)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

            else:
                # Training only — use specified or latest dataset
                from training.grpo_trainer import train_grpo, GRPOTrainingConfig
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

                cfg = GRPOTrainingConfig(
                    time_budget_minutes=req.time_budget_minutes,
                    base_model=req.base_model or TRAINING_BASE_SOLVER,
                    lora_rank=req.lora_rank or TRAINING_LORA_RANK,
                    learning_rate=req.learning_rate or TRAINING_LEARNING_RATE,
                    num_epochs=req.epochs or TRAINING_NUM_EPOCHS,
                )
                result = await asyncio.to_thread(train_grpo, dataset, cfg)
                _active_training["run_id"] = result.get("run_id")
                _active_training["status"] = "idle"

        except Exception as e:
            logger.error(f"Background training failed: {e}", exc_info=True)
            _active_training["status"] = "idle"

    background_tasks.add_task(_run_training)
    return {"status": "started", "run_type": req.run_type, "time_budget_minutes": req.time_budget_minutes}


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

            "timing": {
                "started_at": run["started_at"],
                "completed_at": run["completed_at"],
                "total_wall_clock_sec": round(duration_sec, 1) if duration_sec else None,
                "active_training_sec": round(train_runtime, 1) if train_runtime else None,
                "overhead_sec": round(overhead_sec, 1) if overhead_sec else None,
                "overhead_note": "Model loading, quantization, dataset preparation",
            },

            "dataset": {
                "path": run["dataset_path"],
                "total_samples": run["dataset_size"],
                "training_examples": metrics.get("train_samples"),
            },

            "model": {
                "base_model": metrics.get("base_model") or run["target_model"],
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

    _active_training["status"] = "running"
    _active_training["run_id"] = f"convert-{req.training_run_id}"
    _active_training["started_at"] = __import__("datetime").datetime.utcnow().isoformat()

    async def _run_conversion():
        try:
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
from datetime import datetime as _dt

_art_jobs: dict[str, dict] = {}  # job_id → {status, result, mode, prompt, created_at, finished_at}

def _art_job_create(mode: str, prompt: str) -> str:
    job_id = str(uuid.uuid4())
    _art_jobs[job_id] = {
        "status": "running",
        "result": None,
        "mode": mode,
        "prompt": prompt,
        "created_at": _dt.utcnow().isoformat(),
        "finished_at": None,
    }
    return job_id

def _art_job_finish(job_id: str, status: str, result: str):
    if job_id in _art_jobs:
        _art_jobs[job_id]["status"] = status
        _art_jobs[job_id]["result"] = result
        _art_jobs[job_id]["finished_at"] = _dt.utcnow().isoformat()

@app.get("/v1/art/jobs/{job_id}")
async def art_job_status(job_id: str):
    """Poll for generation job status."""
    job = _art_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/v1/art/models")
async def list_art_models():
    """List available ComfyUI model checkpoints."""
    try:
        from specialized.image_gen import list_available_models
        models = list_available_models()
        return {"models": models or ["v1-5-pruned-emaonly.ckpt"]}
    except Exception as e:
        logger.warning(f"Failed to list art models: {e}")
        return {"models": ["v1-5-pruned-emaonly.ckpt"]}

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
                    f"standing straight, neutral pose, front facing camera, "
                    f"clean edges, isolated on plain white background, "
                    f"studio lighting, high detail, sharp focus, "
                    f"no cropping, entire figure visible head to toe"
                )
                _CONCEPT_NEG = (
                    "multiple objects, multiple characters, text, watermark, frame, border, "
                    "vignette, gradient background, shadow on ground, complex background, "
                    "environment, landscape, cropped, cut off, portrait only, partial body, "
                    "bad anatomy, deformed, extra limbs, blurry, low quality, low resolution"
                )
                _art_jobs[job_id]["result"] = "Generating concept art..."
                img_result = await _art_asyncio.to_thread(
                    generate_image, concept_prompt,
                    width=1024, height=1024,
                    cfg=2.0, steps=6,
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

            _art_jobs[job_id]["result"] = "Generating 3D model (this may take several minutes)..."
            # Build quality overrides from request
            quality_overrides = {}
            if req.steps > 0:
                quality_overrides["steps"] = req.steps
            if req.cfg > 0:
                quality_overrides["cfg"] = req.cfg
            if not quality_overrides and req.quality:
                _QUALITY_PRESETS = {
                    "fast":     {"steps": 50, "cfg": 5.0},
                    "balanced": {"steps": 75, "cfg": 5.0},
                    "high":     {"steps": 100, "cfg": 5.0},
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
                f"{req.prompt}, T-pose reference sheet, front view, "
                f"arms extended straight to sides at shoulder height, legs slightly apart, "
                f"symmetrical, single character, centered subject, "
                f"isolated on solid white background, studio product photo lighting, "
                f"entire body visible head to toe, high detail, sharp focus, "
                f"no props, no text, no cropping"
            )
            _TPOSE_NEG = (
                "multiple objects, multiple characters, text, watermark, frame, border, "
                "vignette, gradient background, shadow on ground, complex background, "
                "environment, landscape, cropped, portrait only, partial body, cut off feet, "
                "perspective distortion, foreshortening, dynamic pose, action pose, "
                "bad anatomy, deformed, extra limbs, blurry, low quality, low resolution"
            )
            _art_jobs[job_id]["result"] = "Generating T-pose concept art..."
            img_result = await _art_asyncio.to_thread(
                generate_image, concept_prompt,
                width=1024, height=1024,
                cfg=2.0, steps=6,
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

            _art_jobs[job_id]["result"] = "Generating 3D mesh and segmenting into posable parts..."
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
                    "size_bytes": os.path.getsize(fpath),
                    "meta": meta,
                })
        return {"images": images}
    except Exception as e:
        return {"images": [], "error": str(e)}

@app.get("/v1/art/gallery/3d")
async def art_gallery_3d():
    """List 3D model files."""
    output_dirs = [
        ("3d_models", "/app/comfy_io/output/3D"),
        ("action_figures", "/app/comfy_io/output/action_figures"),
    ]
    files = []
    for category, dir_path in output_dirs:
        if not os.path.exists(dir_path):
            continue
        for f in sorted(os.listdir(dir_path), key=lambda x: os.path.getmtime(os.path.join(dir_path, x)), reverse=True):
            if f.lower().endswith(('.glb', '.obj', '.stl', '.3mf')):
                fpath = os.path.join(dir_path, f)
                files.append({
                    "filename": f,
                    "category": category,
                    "ext": f.rsplit(".", 1)[-1].upper(),
                    "size_bytes": os.path.getsize(fpath),
                    "path": fpath,
                })
    return {"files": files}

# ── Serve 3D model files (GLB/OBJ/STL) for the viewer ─────────────────────

@app.get("/v1/art/files/{filepath:path}")
async def art_serve_file(filepath: str):
    """Serve a generated 3D file for the browser viewer."""
    # Only allow serving from known output directories
    allowed_roots = ["/app/comfy_io/output", "/app/comfy_io/output/action_figures"]
    full_path = os.path.join("/app/comfy_io/output", filepath)
    full_path = os.path.normpath(full_path)

    if not any(full_path.startswith(root) for root in ["/app/comfy_io/output"]):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    ext = full_path.rsplit(".", 1)[-1].lower()
    media_types = {"glb": "model/gltf-binary", "gltf": "model/gltf+json",
                   "obj": "text/plain", "stl": "model/stl", "3mf": "model/3mf"}
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(full_path, media_type=media_type)

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

            _art_jobs[job_id]["result"] = "Loading and repairing mesh..."
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

            _art_jobs[job_id]["result"] = f"Cutting mesh at {len(user_joints)} joints..."

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
    from router import get_best_host_for_model
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
    from router import get_best_host_for_model
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
    from config import CONTROL_NODE_IP, LANGFUSE_HOST, R730_IP, JUSTIN_PC_IP

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
                "GET /containers/json HTTP/1.1\r\n"
                "Host: localhost\r\n"
                "Accept: application/json\r\n"
                "Connection: close\r\n\r\n"
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
            for host in [JUSTIN_PC_IP, "host.docker.internal"]:
                try:
                    return fetch_remote_containers(host)
                except Exception as e:
                    last_error = e
            raise RuntimeError(str(last_error) if last_error else "Justin-PC container probe failed")

    nodes = []
    ctrl_plane = []
    degraded_reasons = []

    cluster_defs = [
        {"name": "Justin-PC", "role": "execution", "ip": JUSTIN_PC_IP, "fetch": lambda: fetch_justin_containers()},
        {"name": "R730", "role": "gateway", "ip": R730_IP, "fetch": lambda: fetch_remote_containers(R730_IP)},
        {"name": "Control Node", "role": "control", "ip": CONTROL_NODE_IP, "fetch": lambda: fetch_remote_containers(CONTROL_NODE_IP)},
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
        {"name": "MinIO API", "url": f"http://{CONTROL_NODE_IP}:9190/minio/health/live", "port": 9190},
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
                code = s.connect_ex((CONTROL_NODE_IP, svc["port"]))
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
            "url": f"/delivered_artifacts/{f.name}", "metadata": meta,
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
    """List available ComfyUI checkpoints."""
    try:
        from specialized.image_gen import list_available_models
        models = list_available_models()
        return {"models": models}
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


# --- Voice Synthesis Endpoint ---
@app.post("/api/v1/training/voice/speak")
async def training_voice_speak():
    """Synthesize voice clip using BMO voice engine (RVC)."""
    from fastapi import Request as _Request
    from starlette.requests import Request
    import requests as _requests
    # Get request body
    req = Request(scope={"type": "http"})
    bmo_url = os.getenv("BMO_VOICE_URL", "http://bmo-voice:5111")
    try:
        body = {"text": "Hello from the swarm", "voice": "default"}
        resp = _requests.post(f"{bmo_url}/synthesize", json=body, timeout=15)
        if resp.status_code == 200:
            return {"audio_url": "/api/v1/training/voice/latest.wav", "status": "ok"}
        return {"status": "error", "detail": f"BMO returned {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


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


if __name__ == "__main__":
    # If run directly via python, use uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
