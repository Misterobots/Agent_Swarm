
import logging
import sys
import os
import uuid
# Ensure agents dir is in path
if "/app/agents" not in sys.path:
    sys.path.append("/app/agents")
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
    session_id: Optional[str] = None  # conversation ID for multi-turn history

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

    # Extract history (all but the last message), convert Pydantic models to dicts
    history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]
    # Extract latest prompt
    last_msg = request.messages[-1].content
    
    # Check for "Standard Mode" (OpenAI Compatibility)
    # Suppresses internal logs/status updates
    is_standard_mode = request.model.startswith("swarm-") or request.model == "default"
    
    if request.stream:
        async def stream_generator():
            # Get generator from the swarm router
            import logging
            logger = logging.getLogger("uvicorn")
            try:
                gen = chat_swarm(last_msg, session_id=request.session_id or "default_session", history=history)
            except Exception as e:
                logger.error(f"[Stream] chat_swarm init failed: {e}")
                yield f"data: {json.dumps({'id':'chatcmpl-swarm','object':'chat.completion.chunk','created':0,'model':request.model,'choices':[{'index':0,'delta':{'content':f'Error: {e}'},'finish_reason':None}]})}\n\n"
                yield "data: [DONE]\n\n"
                return

            update_count = 0
            try:
                for update in gen:
                    update_count += 1
                    logger.debug(f"[Stream] update #{update_count}: {update}")
                    # Update is expected to be a dict: {"type": ..., "content": ...}
                    if not isinstance(update, dict):
                        continue

                    msg_type = update.get("type", "response")
                    raw_content = update.get("content", "")

                    # In standard mode, forward status as typed chunks; only yield assistant segments, errors, and status
                    if is_standard_mode:
                        if msg_type == "status":
                            # Send status as a typed delta so the UI can render a thinking indicator
                            status_chunk = {
                                "id": "chatcmpl-swarm",
                                "object": "chat.completion.chunk",
                                "created": 1234567890,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": {"content": raw_content, "type": "status"}, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(status_chunk)}\n\n"
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
            # Finish
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming (accumulate all rendered output)
        gen = chat_swarm(last_msg, session_id=request.session_id or "default_session", history=history)
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
        "dataset_size": {"exported": 0, "synthetic": 0},
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

class ActionFigureRequest(BaseModel):
    prompt: str
    workflow: str = "workflow_triposg.json"
    target_height: int = 150
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
                concept_prompt = f"Concept art for 3d modeling, neutral background: {req.prompt}"
                _art_jobs[job_id]["result"] = "Generating concept art..."
                img_result = await _art_asyncio.to_thread(generate_image, concept_prompt)
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

            _art_jobs[job_id]["result"] = "Generating 3D model (this may take several minutes)..."
            from specialized.forge_agent import generate_3d_model
            result = await _art_asyncio.to_thread(generate_3d_model, image_path, req.workflow)
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
                f"T-pose character concept art for 3D action figure, "
                f"full body front view, neutral gray background, "
                f"arms extended to sides, symmetrical pose: {req.prompt}"
            )
            _art_jobs[job_id]["result"] = "Generating T-pose concept art..."
            img_result = await _art_asyncio.to_thread(generate_image, concept_prompt)
            match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
            if not match:
                _art_job_finish(job_id, "error", f"Concept art failed: {img_result}")
                return
            image_path = f"/app/comfy_io/output/{match.group(1)}"

            import os
            if not os.path.exists(image_path):
                _art_job_finish(job_id, "error", f"Concept art image not found at {image_path}")
                return

            _art_jobs[job_id]["result"] = "Generating 3D mesh and segmenting into posable parts..."
            from specialized.action_figure_agent import generate_action_figure
            result = await _art_asyncio.to_thread(generate_action_figure, image_path, req.workflow)
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


if __name__ == "__main__":
    # If run directly via python, use uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
