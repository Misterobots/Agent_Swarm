import json
import requests
import uuid
import os
import time
import shutil
import logging
from phi.agent import Agent
from phi.model.ollama import Ollama

# Logging Setup
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
MODEL_NAME = "qwen2.5-coder:14b"

# Directories (Mapped Volumes)
COMFY_INPUT_DIR = "/app/comfy_io/input"
COMFY_OUTPUT_DIR = "/app/comfy_io/output"
TEMPLATE_DIR = "/app/agents/templates"

def generate_3d_model(image_path: str, workflow_name: str = "workflow_hunyuan_paint.json") -> str:
    """
    Takes an input image, copies it to ComfyUI input, and triggers a 3D generation workflow.
    
    Args:
        image_path (str): Path to the source 2D image (e.g., from ImageGen agent).
        workflow_name (str): Name of the JSON workflow file template.
        
    Returns:
        str: Path to the generated 3D model (GLB/OBJ).
    """
    
    # 1. Validate Input
    if not os.path.exists(image_path):
        return f"Error: Source image not found at {image_path}"
    
    # 2. Prepare Workflow Template
    template_path = os.path.join(TEMPLATE_DIR, workflow_name)
    if not os.path.exists(template_path):
        return f"Error: Workflow template '{workflow_name}' not found in {TEMPLATE_DIR}. Please add it."
        
    try:
        with open(template_path, 'r') as f:
            workflow = json.load(f)
            
        # Check for UI Format (Common mistake)
        if "last_node_id" in workflow or "nodes" in workflow:
            return "Error: The workflow file is in ComfyUI 'UI Format' (contains 'last_node_id'). The Agent requires 'API Format'. Please enable Dev Mode in ComfyUI and use 'Save (API Format)'."
            
    except Exception as e:
        return f"Error loading workflow template: {e}"

    # 3. Hand-off Image to ComfyUI
    # We copy the file to the mounted 'input' directory so ComfyUI can see it
    filename = os.path.basename(image_path)
    # Ensure unique name to avoid conflicts
    unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
    target_input_path = os.path.join(COMFY_INPUT_DIR, unique_filename)
    
    try:
        shutil.copy(image_path, target_input_path)
        print(f"--- [Forge] Copied input to: {target_input_path} ---")
    except Exception as e:
        return f"Error copying image to ComfyUI input: {e}"

    # 4. Inject Image and Seed into Workflow
    import random
    seed_value = random.randint(1, 1000000000000)
    
    def recursive_replace(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = recursive_replace(v)
        elif isinstance(obj, list):
            for i in range(len(obj)):
                obj[i] = recursive_replace(obj[i])
        elif isinstance(obj, str):
            if "{{INPUT_IMAGE}}" in obj:
                return obj.replace("{{INPUT_IMAGE}}", unique_filename)
            if "{{SEED}}" in obj:
                # If the string is EXACTLY {{SEED}}, return int.
                # If part of string, replace and return string.
                if obj == "{{SEED}}":
                    return seed_value
                return obj.replace("{{SEED}}", str(seed_value))
        return obj

    # Apply replacement to the entire workflow structure
    workflow = recursive_replace(workflow)
    logger.info(f"--- [Forge] Applied Seed: {seed_value} ---")

    # 5. Queue Prompt
    payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}
    
    try:
        url = f"{COMFYUI_HOST}/prompt"
        req = requests.post(url, json=payload)
        
        if req.status_code != 200:
            return f"Error form ComfyUI (Status {req.status_code}): {req.text}"
            
        response = req.json()
        
        if 'prompt_id' not in response:
            # ComfyUI often sends {"error": {"type": "...", "message": "..."}}
            return f"ComfyUI Rejected Workflow: {json.dumps(response)}"
            
        prompt_id = response['prompt_id']
        logger.info(f"--- [Forge] 3D Generation Queued: {prompt_id} ---")
    except Exception as e:
        return f"Error connecting to ComfyUI API: {e}"

    # 6. Poll for Result
    logger.info("--- [Forge] Waiting for 3D generation (Max 20 Minutes)... ---")
    time.sleep(5) 
    
    timeout_seconds = 1200 # 20 Minutes (Increased from 10)
    start_time = time.time()
    
    while (time.time() - start_time) < timeout_seconds:
        try:
            # Check History (Did it finish?)
            history_url = f"{COMFYUI_HOST}/history/{prompt_id}"
            res = requests.get(history_url)
            history = res.json()
            
            if prompt_id in history:
                logger.info("--- [Forge] Generation Complete. Parsing outputs... ---")
                outputs = history[prompt_id]['outputs']
                
                # Robust Output Finding (Ported from hybridService.ts)
                for node_id, node_output in outputs.items():
                    # Check all known keys for 3D models
                    possible_keys = ['models', 'meshes', 'mesh', 'glb_path', 'files', 'images']
                    
                    found_files = []
                    for key in possible_keys:
                        if key in node_output:
                            val = node_output[key]
                            if isinstance(val, list): found_files.extend(val)
                            elif isinstance(val, str): found_files.append({'filename': val, 'subfolder': '', 'type': 'output'})
                            elif isinstance(val, dict): found_files.append(val)
                            
                    for item in found_files:
                        if isinstance(item, dict) and 'filename' in item:
                            fname = item['filename']
                            # Look for 3D extensions
                            if fname.endswith('.glb') or fname.endswith('.obj') or fname.endswith('.3mf'):
                                full_path = os.path.join(COMFY_OUTPUT_DIR, item.get('subfolder', ''), fname)
                                logger.info(f"--- [Forge] Found 3D Model: {full_path} ---")
                                return f"3D Model Generated Successfully: {full_path}"
                                
                return "Error: Generation finished but no 3D model file (.glb/.obj) was found in outputs."

            # Check Queue (Is it still running?)
            # This prevents premature timeouts if the queue is deep or processing is slow
            queue_url = f"{COMFYUI_HOST}/queue"
            q_res = requests.get(queue_url)
            q_data = q_res.json()
            
            # Queue data format: { "queue_pending": [...], "queue_running": [...] }
            is_pending = any(item[1] == prompt_id for item in q_data.get('queue_pending', []))
            is_running = any(item[1] == prompt_id for item in q_data.get('queue_running', []))
            
            if is_pending:
                # If pending, we can reset start_time to avoid timeout while waiting in line
                # start_time = time.time() # Optional: specialized agent doesn't want to wait forever?
                pass
            
            if not is_pending and not is_running:
                # It's not in history, not in pending, not in running.
                # Did it fail silently? Or just moved to history in the split second between calls?
                # We'll give it a few more retries before declaring lost.
                pass

            time.sleep(5)
        except Exception as e:
            logger.info(f"Polling error: {e}")
            time.sleep(5)
            
    return "Error: 3D Generation operation timed out after 20 minutes."

def get_forge_agent():
    return Agent(
        name="Creature Forge",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description="I am the 3D Blacksmith. I turn images into 3D models using the Forge pipeline.",
        instructions="Use `generate_3d_model` to convert 2D concept art into 3D assets. You need a source image path first.",
        tools=[generate_3d_model],
        show_tool_calls=True,
    )

if __name__ == "__main__":
    # Test
    agent = get_forge_agent()
    agent.print_response("Status check")
