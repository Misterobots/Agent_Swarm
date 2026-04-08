
import logging
import sys
import os
# Ensure agents dir and workspace root are in path
if "/app/agents" not in sys.path:
    sys.path.append("/app/agents")
if "/workspace" not in sys.path:
    sys.path.insert(0, "/workspace")
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uvicorn
from contextlib import asynccontextmanager
from metrics import AGENT_STATE
from prometheus_client import make_asgi_app
from logger_setup import setup_logger

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

@app.get("/voice_samples/{filename}")
async def serve_voice_sample(filename: str):
    """Serve pre-recorded BMO voice samples to the satellite."""
    sample_dir = "/app/agents/bmo_voice/voice_samples"
    file_path = os.path.join(sample_dir, filename)
    
    # Direct match
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    
    # Case-insensitive fallback
    if os.path.isdir(sample_dir):
        for f in os.listdir(sample_dir):
            if f.lower() == filename.lower():
                return FileResponse(os.path.join(sample_dir, f), media_type="audio/wav")
    
    print(f"⚠️ Voice sample not found: {file_path} (dir exists: {os.path.isdir(sample_dir)})")
    raise HTTPException(status_code=404, detail=f"Sample not found: {filename}")

# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "online", "system": "Home AI Lab Swarm"}

@app.get("/api/v1/identity")
async def get_my_identity(auth_claims: dict = Depends(SpiffeJWTBearer(auto_error=False))):
    """
    Debug endpoint to view current SPIFFE identity and caller identity.
    """
    auth = get_spiffe_auth()
    my_id = auth.get_spiffe_id()
    
    return {
        "my_spiffe_id": my_id,
        "caller_identity": auth_claims if auth_claims else "anonymous",
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
async def chat_completions(request: ChatRequest):
    """
    Standard Chat API to allow external tools (Open-WebUI, VS Code) to talk to the Swarm.
    """
    from fastapi.responses import StreamingResponse
    from router import chat_swarm
    import json

    # Extract history (all but the last message)
    history = request.messages[:-1]
    # Extract latest prompt
    last_msg = request.messages[-1].content
    
    # Check for "Standard Mode" (OpenAI Compatibility)
    # Suppresses internal logs/status updates
    is_standard_mode = request.model.startswith("swarm-") or request.model == "default"
    
    if request.stream:
        async def stream_generator():
            # Get generator from the swarm router
            gen = chat_swarm(last_msg, history=history)
            
            for update in gen:
                # Update is expected to be a dict: {"type": ..., "content": ...}
                if not isinstance(update, dict):
                    continue
                    
                msg_type = update.get("type", "response")
                raw_content = update.get("content", "")
                
                # In standard mode, we only yield the actual assistant segments
                if is_standard_mode:
                    if msg_type not in ["message", "response"]:
                        continue
                    content = raw_content
                    hive_event = None
                else:
                    # Build structured hive_event for the Hive UI to render
                    # rich thinking/tool/agent displays (like Claude Code / Cursor)
                    hive_event = {"type": msg_type, "content": raw_content}
                    
                    if msg_type in ("status", "log", "error"):
                        # Non-content events: send empty delta.content
                        # so OpenAI-compat clients ignore them, but Hive UI
                        # reads hive_event for rich rendering
                        content = ""
                    else:
                        content = raw_content
                    
                if content or hive_event:
                    # Strip heartbeat if it leaks through
                    if content:
                        content = content.replace("\u200B", "")
                    
                    chunk = {
                        "id": "chatcmpl-swarm",
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": request.model,
                        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                    }
                    if hive_event:
                        chunk["hive_event"] = hive_event
                    yield f"data: {json.dumps(chunk)}\n\n"
            
            # Finish
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming (accumulate all rendered output)
        gen = chat_swarm(last_msg, history=history)
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
        
        return {
            "id": "chatcmpl-swarm",
            "object": "chat.completion",
            "created": 1234567890,
            "model": request.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": full_resp}, "finish_reason": "stop"}]
        }
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


# --- Ops Infrastructure Health Endpoint ---
@app.get("/api/v1/ops/health")
async def ops_health():
    """Infrastructure health: Docker containers + control plane service checks."""
    import subprocess
    import socket
    import requests as _requests
    from config import CONTROL_NODE_IP, LANGFUSE_HOST

    exec_plane = []
    ctrl_plane = []
    running_count = 0
    status_msg = "ONLINE"

    # Execution Plane: Docker Socket
    try:
        result = subprocess.run(
            ["curl", "-s", "--unix-socket", "/var/run/docker.sock",
             "http://localhost/containers/json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            containers = json.loads(result.stdout)
            running_count = len(containers)
            for c in containers:
                name = c.get("Names", ["/unknown"])[0].lstrip("/")
                image = c.get("Image", "unknown").split("/")[-1].split(":")[0]
                uptime = c.get("Status", "Unknown")
                exec_plane.append({"name": name, "image": image, "uptime": uptime, "status": "running"})
        else:
            status_msg = f"Docker: {result.stderr[:60]}"
    except Exception as e:
        status_msg = f"Docker Error: {str(e)[:60]}"

    # Control Plane: HTTP/TCP Health Checks
    cp_services = [
        {"name": "Langfuse",      "url": f"{LANGFUSE_HOST}/api/public/health", "port": 3000},
        {"name": "PostgreSQL",    "url": None, "port": 5432},
        {"name": "SPIRE Server",  "url": None, "port": 8081},
        {"name": "MinIO API",     "url": f"http://{CONTROL_NODE_IP}:9190/minio/health/live", "port": 9190},
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

    return {
        "status": status_msg,
        "running_count": running_count,
        "execution_plane": exec_plane,
        "control_plane": ctrl_plane,
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
                    "id": t.get("id"),
                    "timestamp": t.get("timestamp"),
                    "name": t.get("name", "Unknown"),
                    "input_preview": str(t.get("input", ""))[:120],
                    "latency": t.get("latency"),
                    "level": t.get("level", "DEFAULT"),
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
            "trace": trace_data,
            "observations": observations,
            "langfuse_url": f"{lf_host}/project/default/traces/{trace_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Training Runs Endpoint ---
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
                "id": run_dir.name,
                "base_model": cfg.get("base_model", "unknown"),
                "started_at": cfg.get("started_at"),
                "num_epochs": cfg.get("num_epochs"),
                "status": status,
                "adapter_ready": adapter_ready,
                "gguf_files": gguf_files,
            })
    return {"runs": runs}


# --- Model Catalog Endpoint ---
@app.get("/api/v1/training/catalog")
async def model_catalog():
    """
    Model catalog: Ollama available models on all nodes + local trained GGUF files.
    Serves as the foundation for the model promotion workflow (GGUF → Ollama import).
    """
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
                        "modified_at": m.get("modified_at"),
                        "node": label,
                        "digest": (m.get("digest") or "")[:12],
                    })
        except Exception as e:
            catalog["errors"].append(f"{label}: {str(e)[:80]}")
    base_dir = _Path(TRAINING_OUTPUT_DIR)
    if base_dir.exists():
        for gguf in sorted(base_dir.rglob("*.gguf")):
            stat = gguf.stat()
            catalog["local_gguf"].append({
                "name": gguf.stem,
                "path": str(gguf.relative_to(base_dir)),
                "size_mb": round(stat.st_size / 1_048_576, 1),
                "run_id": gguf.parent.name,
            })
    return catalog


# --- RAG Knowledge Ingestion Endpoint ---
class IngestRequest(BaseModel):
    text: str
    metadata: dict = {}

class IngestFileRequest(BaseModel):
    file_path: str

@app.post("/api/v1/knowledge/ingest")
async def ingest_knowledge(req: IngestRequest):
    """
    Ingest a text document into the Architect's PgVector knowledge base.
    Splits text into chunks and embeds into the vector DB.
    """
    from config import AGNO_DB_URL
    if not AGNO_DB_URL or "dell_wyse_ip" in AGNO_DB_URL:
        raise HTTPException(status_code=503, detail="PgVector DB not configured (AGNO_DB_URL)")

    try:
        from phi.knowledge.text import TextKnowledgeBase
        from phi.vectordb.pgvector import PgVector

        kb = TextKnowledgeBase(
            sources=[],
            vector_db=PgVector(
                table_name="architect_knowledge",
                db_url=AGNO_DB_URL,
            ),
        )
        # Use PgVector's insert directly via the knowledge base
        from phi.document import Document
        doc = Document(content=req.text, meta_data=req.metadata)
        kb.vector_db.insert([doc])
        logger.info(f"[RAG] Ingested document ({len(req.text)} chars)")
        return {"status": "ingested", "chars": len(req.text), "metadata": req.metadata}
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"RAG dependencies missing: {e}")
    except Exception as e:
        logger.error(f"[RAG] Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/knowledge/ingest_file")
async def ingest_knowledge_file(req: IngestFileRequest):
    """
    Ingest a file from the workspace into the knowledge base.
    Supports .txt, .md, .py, .json files.
    """
    import os as _os
    file_path = req.file_path

    # Validate path is within workspace
    workspace_root = "/workspace"
    resolved = _os.path.realpath(file_path)
    if not resolved.startswith(workspace_root):
        raise HTTPException(status_code=403, detail="Path must be within /workspace")

    if not _os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    # Delegate to the text ingestion endpoint logic
    from config import AGNO_DB_URL
    if not AGNO_DB_URL or "dell_wyse_ip" in AGNO_DB_URL:
        raise HTTPException(status_code=503, detail="PgVector DB not configured")

    try:
        from phi.knowledge.text import TextKnowledgeBase
        from phi.vectordb.pgvector import PgVector
        from phi.document import Document

        kb = TextKnowledgeBase(
            sources=[],
            vector_db=PgVector(
                table_name="architect_knowledge",
                db_url=AGNO_DB_URL,
            ),
        )
        doc = Document(content=content, meta_data={"source": file_path, "type": _os.path.splitext(file_path)[1]})
        kb.vector_db.insert([doc])
        logger.info(f"[RAG] Ingested file: {file_path} ({len(content)} chars)")
        return {"status": "ingested", "file": file_path, "chars": len(content)}
    except Exception as e:
        logger.error(f"[RAG] File ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # If run directly via python, use uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
