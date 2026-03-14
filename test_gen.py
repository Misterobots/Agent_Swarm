import json
import requests
import time
import uuid
import os
import shutil

COMFY_HOST = "http://comfyui_gpu:8188"
WORKFLOW_PATH = "/app/agents/templates/workflow_hunyuan_paint.json"
INPUT_DIR = "/app/comfy_io/input"

def generate():
    # 1. Load Workflow
    try:
        with open(WORKFLOW_PATH, 'r') as f:
            workflow = json.load(f)
    except Exception as e:
        print(f"Error loading workflow: {e}")
        return

    # 2. Inject Dummy Image (We assume one exists or we create one? Let's assume input_example.png or just use a placeholder text if workflow allows, but image-to-3d needs image)
    # Let's create a dummy file on the fly if python allows, or copy one?
    # Better: List input dir first to see if anything is there. 
    # For now, let's assume valid JSON is enough to queue, but if it refers to a non-existent image, it will fail *in execution*.
    
    # 3. Queue Prompt
    prompt_id = str(uuid.uuid4())
    p = {"prompt": workflow, "client_id": prompt_id}
    
    print("Queueing Prompt...")
    res = requests.post(f"{COMFY_HOST}/prompt", json=p)
    if res.status_code != 200:
        print(f"Error queuing: {res.text}")
        return
    
    pid = res.json().get('prompt_id')
    print(f"Prompt ID: {pid}")

    # 4. Poll
    while True:
        history = requests.get(f"{COMFY_HOST}/history/{pid}").json()
        if history:
            print("Generation Complete!")
            # Check for outputs
            print(history)
            break
        print("Waiting...")
        time.sleep(2)

if __name__ == "__main__":
    generate()
