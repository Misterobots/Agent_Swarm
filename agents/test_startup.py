
print("Step 1: Importing logging...")
import logging
print("Step 2: Importing sys/os...")
import sys, os
print("Step 3: Importing fastapi...")
from fastapi import FastAPI
print("Step 4: Importing uvicorn...")
import uvicorn
print("Step 5: Importing logger_setup...")
import logger_setup
print("Step 6: Importing dispatcher...")
import dispatcher
print("Step 7: Importing router...")
try:
    import router
    print("Step 7 SUCCESS")
except Exception as e:
    print(f"Step 7 FAILED: {e}")
print("Step 8: Define App...")
app = FastAPI()
@app.get("/")
async def root(): return {"status": "ok"}
print("Step 9: Startup Check Done.")
