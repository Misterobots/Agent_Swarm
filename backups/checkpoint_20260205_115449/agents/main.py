
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager
from metrics import AGENT_STATE
from prometheus_client import make_asgi_app
from dispatcher import dispatcher, Event, EventType
from router import handle_task_event

# Logging
from logger_setup import setup_logger

logger = setup_logger("Main")
logger.info("--- [Logging] Loki Handler Attached via Shared Setup ---")

# --- API Models ---
class TaskRequest(BaseModel):
    task: str
    source: str = "api"

class TaskResponse(BaseModel): # Added TaskResponse
    status: str
    result: str

# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Swarm Engine...")
    
    # 1. Register Routers to Dispatcher
    dispatcher.register(EventType.USER_TASK, handle_task_event)
    
    # 2. Reset Metrics
    AGENT_STATE.labels(agent_name="Router").set(1)
    AGENT_STATE.labels(agent_name="Security").set(1)
    AGENT_STATE.labels(agent_name="Architect").set(1)
    
    logger.info("Swarm Engine Online. Waiting for events...")
    yield
    # Shutdown
    logger.info("Shutting down Swarm Engine...")

# --- App Definition ---
app = FastAPI(lifespan=lifespan, title="Home AI Lab Swarm API")

# Mount Prometheus Metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "online", "system": "Home AI Lab Swarm"}

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

    return {"status": "accepted", "message": "Task queued for execution"}

# --- OpenAI-Compatible Chat Endpoint (For VS Code Extensions) ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "default"
    stream: bool = False

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """
    Standard Chat API to allow external tools (VS Code) to talk to the Swarm.
    """
    from fastapi.responses import StreamingResponse
    from router import chat_swarm
    import json

    # Extract latest prompt
    last_msg = request.messages[-1].content
    
    # We treat the API client as a "Power User" (likely VS Code)
    # We can inject context based on the model or client if needed.
    
    if request.stream:
        async def stream_generator():
            full_content = ""
            # Stream the Swarm response
            for update in chat_swarm(last_msg):
                if update['type'] == 'response':
                    # Calculate delta
                    delta = update['content'][len(full_content):]
                    full_content = update['content']
                    
                    if delta:
                        chunk = {
                            "id": "chatcmpl-swarm",
                            "object": "chat.completion.chunk",
                            "created": 1234567890,
                            "model": request.model,
                            "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
            
            # Finish
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming
        full_resp = ""
        for update in chat_swarm(last_msg):
            if update['type'] == 'response':
                full_resp = update['content']
        
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

if __name__ == "__main__":
    # Dev mode run
    uvicorn.run(app, host="0.0.0.0", port=8000)
