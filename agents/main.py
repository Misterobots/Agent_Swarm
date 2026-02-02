
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
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

# --- External Logging Endpoint ---
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

if __name__ == "__main__":
    # Dev mode run
    uvicorn.run(app, host="0.0.0.0", port=8000)
