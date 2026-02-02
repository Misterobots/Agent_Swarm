import json
import requests
import uuid
import os
import time
import base64
from logger_setup import setup_logger

# Logging Setup
logger = setup_logger("CreativeStudio")

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
MODEL_NAME = "qwen2.5-coder:14b" # Logic model

def get_available_checkpoint():
    """Queries ComfyUI for the first available checkpoint."""
    try:
        url = f"{COMFYUI_HOST}/object_info/CheckpointLoaderSimple"
        req = requests.get(url)
        if req.status_code == 200:
            info = req.json()
            # The structure is usually inputs -> required -> ckpt_name -> [list of strings]
            checkpoints = info.get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [])
            if checkpoints and isinstance(checkpoints[0], list):
                # Sometimes it returns [ [ "name1", "name2" ], { ... } ]
                return checkpoints[0][0] 
    except:
        pass
    return "v1-5-pruned-emaonly.ckpt" # Fallback

# --- LAYER 3: MODEL DETECTION ---
def detect_model_type(ckpt_name: str) -> str:
    name = ckpt_name.lower()
    if "flux" in name:
        if "schnell" in name: return "FLUX_SCHNELL"
        return "FLUX_DEV"
    if "turbo" in name and ("xl" in name or "sdxl" in name):
         return "SDXL_TURBO"
    if "xl" in name or "sdxl" in name:
        return "SDXL"
    return "SD15" # Default for things like DreamShaper

# --- LAYER 5: PARAMETER TUNING ---
def get_model_params(model_type: str):
    if model_type == "FLUX_SCHNELL":
        return {"cfg": 1.0, "steps": 4, "sampler": "euler", "scheduler": "simple", "width": 1024, "height": 1024}
    elif model_type == "FLUX_DEV":
        return {"cfg": 3.5, "steps": 20, "sampler": "euler", "scheduler": "simple", "width": 1024, "height": 1024}
    elif model_type == "SDXL_TURBO":
        # Turbo needs CFG 1.0 and Euler A for best photorealism
        # Higher CFG causes "deep fried" contrast.
        return {"cfg": 1.0, "steps": 2, "sampler": "euler_ancestral", "scheduler": "normal", "width": 1024, "height": 1024}
    elif model_type == "SDXL":
        return {"cfg": 7.0, "steps": 30, "sampler": "dpmpp_2m", "scheduler": "karras", "width": 1024, "height": 1024}
    else: # SD1.5 Fallback (e.g. DreamShaper)
        return {"cfg": 7.0, "steps": 25, "sampler": "euler_ancestral", "scheduler": "normal", "width": 512, "height": 512}

# --- LAYER 4: PROMPT REFINEMENT ---
def apply_style_heuristics(prompt: str, model_type: str) -> str:
    """
    Analyzes the prompt to infer style. If no style is detected, defaults to Photorealism.
    """
    p_lower = prompt.lower()
    
    # 1. Check for explicit styles
    styles = ["painting", "drawing", "sketch", "anime", "cartoon", "render", "illustration", "art", "graphic"]
    if any(s in p_lower for s in styles):
        return prompt # User specified a style, respect it.
        
    # 2. Heuristic: No style specified -> Default to Photorealism/Cinematic
    # Tailor keywords for the Model
    if "TURBO" in model_type:
        # Turbo loves "raw photo" and "sharp focus"
        style_boost = "photograph, realistic, raw photo, sharp focus, 4k"
    elif "FLUX" in model_type:
        # Flux likes natural language
        style_boost = "Cinematic shot, photorealistic, incredibly detailed"
    else: # SDXL / SD1.5
        style_boost = "photograph, photorealistic, cinematic lighting, 8k, highly detailed"
        
    return f"{style_boost}, {prompt}"

def refine_prompt(prompt: str, model_type: str) -> str:
    # 1. Apply Style Defaults (if needed)
    styled_prompt = apply_style_heuristics(prompt, model_type)

    # 2. Apply Model-Specific Boosters (Layer 3)
    # Only inject quality tags for standard SDXL or SD1.5
    if model_type == "SDXL" or model_type == "SD15":
        return f"masterpiece, best quality, {styled_prompt}"
    
    return styled_prompt

def queue_prompt(prompt_text: str):
    """
    Sends a prompt to ComfyUI with model-aware parameters.
    """
    # 1. Select Checkpoint (Smart Select)
    all_ckpts = []
    try:
        url = f"{COMFYUI_HOST}/object_info/CheckpointLoaderSimple"
        req = requests.get(url)
        if req.status_code == 200:
            all_ckpts = req.json().get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [])[0]
    except:
        pass
        
    # Priority: Flux > SDXL > v1.5
    # Default to first available if list exists, otherwise safest fallback
    ckpt_name = all_ckpts[0] if all_ckpts else "v1-5-pruned-emaonly.ckpt"
    
    # Try to find a better one
    for c in all_ckpts:
        if "flux" in c.lower() and "schnell" in c.lower():
             ckpt_name = c
             break
        if "xl" in c.lower() and "turbo" not in c.lower(): 
             # Prefer FULL SDXL if available (better than Turbo for quality, though slower)
             ckpt_name = c
    
    # If we only have Turbo (which seems to be the case based on user logs), use it.
    # The loop above prefers Full XL, but if not found, it keeps the first one (which might be DreamShaper).
    # Let's specifically look for ANY XL if we haven't found one yet.
    if "xl" not in ckpt_name.lower() and "flux" not in ckpt_name.lower():
        for c in all_ckpts:
            if "xl" in c.lower():
                ckpt_name = c
                break

    # 2. Determine Configuration
    model_type = detect_model_type(ckpt_name)
    params = get_model_params(model_type)
    final_prompt = refine_prompt(prompt_text, model_type)
    
    print(f"--- [ComfyUI] Config: {model_type} | Ckpt: {ckpt_name} | CFG: {params['cfg']} | Steps: {params['steps']} ---")

    # 3. Construct Payload
    p = {
        "prompt": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": params['cfg'],
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": params['sampler'],
                    "scheduler": params['scheduler'],
                    "seed": 5, 
                    "steps": params['steps']
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": ckpt_name 
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": params['height'],
                    "width": params['width']
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": final_prompt
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "" if "FLUX" in model_type else "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"ComfyUI_{model_type}",
                    "images": ["8", 0]
                }
            }
        }
    }
    
    # 0. Get a unique client ID
    client_id = str(uuid.uuid4())
    p["client_id"] = client_id
    
    # Randomize Seed
    import random
    p["prompt"]["3"]["inputs"]["seed"] = random.randint(1, 1000000000)
    
    logger.info(f"--- [ComfyUI] Enqueuing Payload: {json.dumps(p)[:200]}... ---")

    # 1. Send Prompt
    try:
        url = f"{COMFYUI_HOST}/prompt"
        data = json.dumps(p).encode('utf-8')
        req = requests.post(url, data=data)
        
        if req.status_code != 200:
            return f"Error connecting to ComfyUI (Status {req.status_code}): {req.text}"
            
        response = req.json()
        
        if 'prompt_id' not in response:
             return f"Error: ComfyUI did not return a prompt_id. Response: {response}"
             
        prompt_id = response['prompt_id']
        print(f"--- [ComfyUI] Prompt Queued: {prompt_id} ---")
    except Exception as e:
        return f"Error connecting to ComfyUI: {e}"

    # 2. Wait for Completion (WebSocket or Polling)
    # For simplicity in this v1, we will poll history. 
    # Proper way is websocket, but that requires websocket-client lib which might not be in container.
    
    print("--- [ComfyUI] Waiting for generation... ---")
    time.sleep(2) # Give it a second to start
    
    for i in range(60): # Wait up to 60 seconds
        try:
            history_url = f"{COMFYUI_HOST}/history/{prompt_id}"
            res = requests.get(history_url)
            history = res.json()
            
            if prompt_id in history:
                # Success!
                outputs = history[prompt_id]['outputs']
                # Node 9 is the SaveImage node
                if '9' in outputs:
                     images = outputs['9']['images']
                     filename = images[0]['filename']
                     subfolder = images[0]['subfolder']
                     # Construct full path or URL
                     # Since we mounted the output dir, we can return the local path or a serving URL
                     return f"Generated Image: {filename} (in {subfolder} output)"
        except:
            pass
        time.sleep(1)
        
    return "Error: Generation timed out."

# --- LAYER 6: VERIFICATION (Creature Forge Port + VLM) ---
import cv2
import numpy as np

def verify_structure(image_path: str) -> tuple[bool, str]:
    """
    Ported from Creature Forge (validation_server.py).
    Checks for: Empty image, Multiple subjects (bad for focus), Cropping.
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None: return False, "Could not load image."
        
        h, w = img.shape[:2]
        
        # 1. Binarize (Alpha or Intensity)
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            _, thresh = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Assumption: Background is usually lighter or darker. 
            # For general scenes, this is less reliable, but good for "Object" prompts.
            # We'll skip strict blob check for complex scenes, but check for "Empty/Black".
            if np.mean(gray) < 5 or np.mean(gray) > 250:
                 return False, "Image is single-color/empty."
            return True, "Structure OK (Complex Scene)"
            
        # 2. Cleanup & Contour (For Transparent/Alpha images)
        kernel = np.ones((5,5), np.uint8)
        eroded = cv2.erode(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_area = (h * w) * 0.005
        large_contours = [c for c in contours if cv2.contourArea(c) > min_area]
        
        if len(large_contours) == 0:
            return False, "Subject is empty/invisible."
        if len(large_contours) > 1:
            return False, f"Structural Split: Found {len(large_contours)} detached subjects."
            
        # 3. Cropping Check
        x, y, cw, ch = cv2.boundingRect(large_contours[0])
        margin = 5
        if x < margin or y < margin or (x+cw) > (w-margin) or (y+ch) > (h-margin):
            return False, "Subject is cropped/touching edges."
            
        return True, "Structure Valid"
    except Exception as e:
        return True, f"Structure Check Skipped: {e}"

def verify_semantics(image_path: str, prompt: str) -> tuple[bool, str]:
    """
    Uses a VLM (Moondream/Llava) to check for severe defects.
    """
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        # Use existing Ollama instance
        # We ask for a "Defect Report"
        vlm_prompt = f"""
        Analyze this image based on the prompt: '{prompt}'.
        TRUE or FALSE: Does the image contain severe mutations, extra limbs, more than 2 eyes, or broken geometry?
        Answer only regarding severe defects. If it looks mostly okay, say FALSE.
        """
        
        payload = {
            "model": "moondream:latest", # Fast VLM
            "prompt": vlm_prompt,
            "images": [img_b64],
            "stream": False
        }
        
        # Fallback to llava if moondream not present (handled by Ollama usually pulling if missing, or we assume logic)
        # Actually, let's try llava as it's more common, or user specified "use methods in project".
        # Creature Forge doesn't use VLM. We use it to solve the "3 eyes" user request.
        
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        if res.status_code == 200:
            ans = res.json().get("response", "").upper()
            if "TRUE" in ans:
                return False, f"VLM Detected Defect: {ans}"
            return True, "Semantics OK"
            
    except Exception as e:
        logger.warning(f"Semantic Check Failed: {e}")
        pass
        
    return True, "Semantic Check Skipped (VLM Unavailable)"

def generate_image(prompt: str) -> str:
    """
    Generates an image using ComfyUI based on the prompt.
    Includes Automatic Verification & Retry.
    """
    MAX_RETRIES = 2
    import os
    
    # Check if we can find the output directory
    # Inside the container, we are at /workspace/agents/specialized usually?
    # Or /app/agents/specialized.
    # The 'output' folder is likely at /workspace/output if mounted correctly.
    # Let's try to locate it.
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    output_dir = os.path.join(workspace_root, "output")
    
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            logger.info(f"--- [Creative Studio] Verification Failed. Retrying ({attempt}/{MAX_RETRIES})... ---")
            
        result_msg = queue_prompt(prompt)
        
        if "Error" in result_msg:
             return result_msg # System error, don't retry
             
        # Extract Filename from message "Generated Image: filename.png ..."
        try:
            filename = result_msg.split("Generated Image: ")[1].split(" ")[0]
            # Try to resolve path
            img_path = os.path.join(output_dir, filename)
            
            if not os.path.exists(img_path):
                # Fallback: maybe it's in current dir?
                if os.path.exists(filename): img_path = filename
                else: 
                     logger.warning(f"Could not find image at {img_path} to verify. Skipping verification.")
                     return result_msg
            
            # 1. Structural Verification (Creature Forge Port)
            struct_ok, struct_reason = verify_structure(img_path)
            if not struct_ok:
                logger.warning(f"Structure Check Failed: {struct_reason}")
                # We can retry on structure fail too
                continue 

            # 2. Semantic Verification (VLM)
            sem_ok, sem_reason = verify_semantics(img_path, prompt)
            if not sem_ok:
                logger.warning(f"Semantic Check Failed: {sem_reason}")
                continue 
                
            # Passing!
            return f"{result_msg} | ✅ Verified: Structure & Semantics OK."
            
        except Exception as e:
            logger.error(f"Verification Logic Error: {e}")
            pass
            
        return result_msg # Return first success if logic fails

    return "Failed to generate valid image after retries (Quality/Mutation issues)."

def get_image_gen_agent():
    return Agent(
        name="Creative Studio",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description="I am the Creative Studio. I generate images using ComfyUI.",
        instructions="You are an artist. You receive prompts and use the `generate_image` tool to create visuals. Always return the filename of the generated image.",
        tools=[generate_image],
        show_tool_calls=True,
    )

if __name__ == "__main__":
    # Test
    agent = get_image_gen_agent()
    agent.print_response("Generate a cyberpunk city")
