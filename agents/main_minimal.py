
from fastapi import FastAPI
import uvicorn
import time

app = FastAPI()

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "minimal-test",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "MarsRL"
            }
        ]
    }

@app.get("/")
async def root():
    return {"status": "minimal-online"}

if __name__ == "__main__":
    print("Starting MINIMAL Swarm API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
