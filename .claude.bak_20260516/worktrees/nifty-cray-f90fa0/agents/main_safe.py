from fastapi import FastAPI
import uvicorn
import os
import sys

# Ensure agents dir is in path
if "/app/agents" not in sys.path:
    sys.path.append("/app/agents")

from logger_setup import setup_logger
from dispatcher import dispatcher

app = FastAPI()
logger = setup_logger("MainSafe")

@app.get("/")
async def root():
    return {"status": "SAFE MODE ONLINE"}

if __name__ == "__main__":
    print("--- STARTING SAFE MODE ---")
    uvicorn.run(app, host="0.0.0.0", port=8000)
