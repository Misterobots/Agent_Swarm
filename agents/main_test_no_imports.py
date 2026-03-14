
from fastapi import FastAPI
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    logger.info("Starting Minimal Server (No Imports)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
