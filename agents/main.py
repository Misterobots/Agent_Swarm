
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
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import requests
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
        "audio_path": response_msg.metadata.get("audio_path") if response_msg.metadata else None,
        "session_id": agent.session_id,
    }

@app.post("/v1/voice/end_session")
async def voice_end_session():
    """
    End the current BMO voice session — triggers summary + fact extraction.
    Call when the satellite disconnects or the user says goodbye.
    """
    global _voice_agent
    agent = get_voice_agent()
    agent.end_session()
    session_id = agent.session_id
    _voice_agent = None  # Next request starts a fresh session
    return {"status": "session_ended", "session_id": session_id}

@app.post("/v1/voice/new_session")
async def voice_new_session():
    """
    Force-start a new BMO session (ends the current one first).
    """
    global _voice_agent
    if _voice_agent is not None:
        _voice_agent.end_session()
    _voice_agent = None
    agent = get_voice_agent()
    return {"status": "new_session", "session_id": agent.session_id}

@app.post("/v1/voice/stream")
async def voice_stream(request: VoiceRequest):
    """
    Streaming voice endpoint — sentence-pipelined TTS.
    
    Pipeline: user text → LLM response → split into sentences →
    generate TTS for each sentence → stream audio chunks as they complete.
    
    First audio chunk arrives after the first sentence is synthesized,
    not after the entire response. Reduces perceived latency significantly.
    """
    import re as _re
    from fastapi.responses import StreamingResponse
    from specialized.voice_assistant import Message
    from specialized.voice_samples_map import get_sample_path, find_sample_in_response
    
    agent = get_voice_agent()
    user_text = request.text.strip()
    
    # 1. Check for pre-recorded sample (instant response)
    sample_path = get_sample_path(user_text)
    if sample_path:
        full_path = f"/app/agents/bmo_voice/voice_samples/{sample_path}"
        agent._persist_turn(user_text, user_text)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                return Response(content=f.read(), media_type="audio/wav")
    
    # 2. Get LLM response (non-streaming for now — sentence pipelining happens at TTS level)
    response_msg = agent.process(Message(role="user", content=user_text))
    response_text = response_msg.content
    
    # 3. Check for sample match in response
    sample_match = find_sample_in_response(response_text)
    if sample_match:
        full_path = f"/app/agents/bmo_voice/voice_samples/{sample_match}"
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                audio_data = f.read()
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={"X-BMO-Text": response_text[:200], "X-BMO-Session": agent.session_id},
            )
    
    # 4. Sentence-pipelined TTS: split response, stream each sentence's audio
    BMO_TTS_URL = os.getenv("BMO_ENGINE_URL", "http://bmo_voice_gpu:8000/speak/stream")
    
    def stream_sentences():
        sentences = _re.split(r'(?<=[.!?])\s+', response_text.strip())
        sentences = [s for s in sentences if s.strip()]
        
        for sentence in sentences:
            try:
                resp = requests.post(
                    BMO_TTS_URL,
                    params={"text": sentence},
                    timeout=30,
                    stream=True,
                )
                if resp.status_code == 200:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
            except Exception as e:
                logger.warning(f"Sentence TTS failed: {e}")
                continue
    
    return StreamingResponse(
        stream_sentences(),
        media_type="audio/wav",
        headers={"X-BMO-Text": response_text[:200], "X-BMO-Session": agent.session_id},
    )

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
