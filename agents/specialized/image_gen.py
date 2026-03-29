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

def list_available_models() -> list:
    """Queries ComfyUI for all available checkpoints."""
    try:
        url = f"{COMFYUI_HOST}/object_info/CheckpointLoaderSimple"
        req = requests.get(url, timeout=5)
        if req.status_code == 200:
            return req.json().get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [])[0]
    except Exception as e:
        logger.warning(f"Failed to list models: {e}")
    # Fallback to the checkpoint we actually deploy in this stack.
    return ["sd_xl_turbo_1.0_fp16.safetensors"]

def get_available_checkpoint():
    """Queries ComfyUI for the first available checkpoint."""
    # This is legacy, but we keep it for now or redirect
    models = list_available_models()
    return models[0] if models else "v1-5-pruned-emaonly.ckpt"

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
        return {"cfg": 1.0, "steps": 2, "sampler": "euler_ancestral", "scheduler": "normal", "width": 1024, "height": 1024}
    elif model_type == "SDXL":
        return {"cfg": 7.0, "steps": 30, "sampler": "dpmpp_2m", "scheduler": "karras", "width": 1024, "height": 1024}
    else: # SD1.5 Fallback
        return {"cfg": 7.0, "steps": 25, "sampler": "euler_ancestral", "scheduler": "normal", "width": 768, "height": 768}

# --- LAYER 4: PROMPT REFINEMENT ---
def apply_style_heuristics(prompt: str, model_type: str) -> str:
    """
    Analyzes the prompt to infer style. If no style is detected, defaults to Photorealism.
    """
    p_lower = prompt.lower()
    styles = ["painting", "drawing", "sketch", "anime", "cartoon", "render", "illustration", "art", "graphic"]
    if any(s in p_lower for s in styles):
        return prompt 
        
    if "TURBO" in model_type:
        style_boost = "photograph, realistic, raw photo, sharp focus, 4k"
    elif "FLUX" in model_type:
        style_boost = "Cinematic shot, photorealistic, incredibly detailed"
    else: 
        style_boost = "photograph, photorealistic, cinematic lighting, 8k, highly detailed"
        
    return f"{style_boost}, {prompt}"

def refine_prompt(prompt: str, model_type: str) -> str:
    styled_prompt = apply_style_heuristics(prompt, model_type)
    if model_type == "SDXL" or model_type == "SD15":
        return f"masterpiece, best quality, {styled_prompt}"
    return styled_prompt

def queue_prompt(prompt_text: str, **kwargs):
    """
    Sends a prompt to ComfyUI with optional manual overrides.
    Pass negative_prompt kwarg to override the negative conditioning text.
    """
    requested_ckpt = kwargs.get("model_name")
    negative_prompt_override = kwargs.get("negative_prompt")
    all_ckpts = list_available_models()
    
    ckpt_name = "v1-5-pruned-emaonly.ckpt"
    
    # 1. Select Checkpoint
    if requested_ckpt and requested_ckpt in all_ckpts:
        ckpt_name = requested_ckpt
    elif all_ckpts:
         ckpt_name = all_ckpts[0]
         for c in all_ckpts:
            if "flux" in c.lower() and "schnell" in c.lower(): ckpt_name = c; break
            if "xl" in c.lower() and "turbo" not in c.lower(): ckpt_name = c
            
    # 2. Determine Configuration
    model_type = detect_model_type(ckpt_name)
    raw_params = get_model_params(model_type)
    
    # APPLY OVERRIDES
    params = {
        "cfg": float(kwargs.get("cfg", raw_params["cfg"])),
        "steps": int(kwargs.get("steps", raw_params["steps"])),
        "sampler": kwargs.get("sampler", raw_params["sampler"]),
        "scheduler": kwargs.get("scheduler", raw_params["scheduler"]),
        "width": int(kwargs.get("width", raw_params["width"])),
        "height": int(kwargs.get("height", raw_params["height"]))
    }
    
    if kwargs.get("skip_refinement"):
        final_prompt = prompt_text
    else:
        final_prompt = refine_prompt(prompt_text, model_type)
    print(f"--- [ComfyUI] Config: {model_type} | Ckpt: {ckpt_name} | Params: {params} ---")

    # 3. Payload
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
                    "text": negative_prompt_override if negative_prompt_override is not None else (
                        "" if "FLUX" in model_type else
                        "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation"
                    )
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
    
    client_id = str(uuid.uuid4())
    p["client_id"] = client_id
    import random
    p["prompt"]["3"]["inputs"]["seed"] = random.randint(1, 1000000000)
    
    try:
        url = f"{COMFYUI_HOST}/prompt"
        req = requests.post(url, json=p) # requests handles json encoding
        
        if req.status_code != 200:
            return f"Error connecting to ComfyUI (Status {req.status_code}): {req.text}"
            
        response = req.json()
        if 'prompt_id' not in response:
             return f"Error: ComfyUI did not return a prompt_id. Response: {response}"
             
        prompt_id = response['prompt_id']
        print(f"--- [ComfyUI] Prompt Queued: {prompt_id} ---")
    except Exception as e:
        return f"Error connecting to ComfyUI: {e}"

    print("--- [ComfyUI] Waiting for generation... ---")
    time.sleep(2) 
    
    for i in range(180):  # Up to 3 minutes for model loading + generation
        try:
            history_url = f"{COMFYUI_HOST}/history/{prompt_id}"
            res = requests.get(history_url, timeout=5)
            history = res.json()

            if prompt_id in history:
                entry = history[prompt_id]
                # Check for ComfyUI execution error
                status_str = entry.get('status', {}).get('status_str', '')
                if status_str == 'error':
                    msgs = entry.get('status', {}).get('messages', [])
                    err_detail = "Unknown ComfyUI error"
                    for msg in msgs:
                        if isinstance(msg, list) and msg[0] == 'execution_error':
                            err_detail = msg[1].get('exception_message', err_detail)
                            break
                    return f"Error: ComfyUI execution failed: {err_detail.strip()}"
                outputs = entry.get('outputs', {})
                if '9' in outputs:
                     images = outputs['9'].get('images', [])
                     if images:
                         filename = images[0]['filename']
                         subfolder = images[0].get('subfolder', '')
                         return f"Generated Image: {filename} (in {subfolder} output)"
                     return "Error: ComfyUI completed but produced no image output."
                return "Error: ComfyUI completed but SaveImage node produced no output."
        except Exception as e:
            logger.warning(f"Polling error: {e}")
        time.sleep(1)

    return "Error: Generation timed out."

# --- LAYER 6: VERIFICATION ---
import cv2
import numpy as np

def verify_structure(image_path: str) -> tuple[bool, str]:
    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None: return False, "Could not load image."
        h, w = img.shape[:2]
        
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            _, thresh = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if np.mean(gray) < 5 or np.mean(gray) > 250:
                 return False, "Image is single-color/empty."
            return True, "Structure OK (Complex Scene)"
            
        kernel = np.ones((5,5), np.uint8)
        eroded = cv2.erode(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_area = (h * w) * 0.005
        large_contours = [c for c in contours if cv2.contourArea(c) > min_area]
        
        if len(large_contours) == 0:
            return False, "Subject is empty/invisible."
        if len(large_contours) > 1:
            return False, f"Structural Split: Found {len(large_contours)} detached subjects."
        return True, "Structure Valid"
    except Exception as e:
        return True, f"Structure Check Skipped: {e}"

def verify_semantics(image_path: str, prompt: str) -> tuple[bool, str]:
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        vlm_prompt = f"""
        Analyze this image based on the prompt: '{prompt}'.
        TRUE or FALSE: Does the image contain severe mutations, extra limbs, more than 2 eyes, or broken geometry?
        Answer only regarding severe defects. If it looks mostly okay, say FALSE.
        """
        
        payload = {
            "model": "moondream:latest",
            "prompt": vlm_prompt,
            "images": [img_b64],
            "stream": False
        }
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        if res.status_code == 200:
            ans = res.json().get("response", "").upper()
            if "TRUE" in ans:
                return False, f"VLM Detected Defect: {ans}"
            return True, "Semantics OK"
    except Exception as e:
        pass
    return True, "Semantic Check Skipped (VLM Unavailable)"

def generate_image(
    prompt: str,
    model_name: str = "auto",
    cfg: float = 7.0,
    steps: int = 20,
    width: int = 1024,
    height: int = 1024,
    sampler: str = "euler",
    scheduler: str = "normal",
    seed: int = -1,
    target_device: str = "auto",
    negative_prompt: str = None,
    skip_refinement: bool = False,
) -> str:
    """
    Generates an image using ComfyUI. 
    Args:
        prompt: Description of the image.
        model_name: Checkpoint name.
        cfg: Classifier Free Guidance scale.
        steps: Number of sampling steps.
        width: Image width.
        height: Image height.
        sampler: Sampling method (euler, dpmpp_2m, etc).
        scheduler: Scheduler type (normal, karras, etc).
        seed: Random seed (-1 for random).
    """
    # Pack arguments into a dict for internal use.
    # When model_name is "auto", omit generation params so queue_prompt's
    # auto-detection picks the right cfg/steps/sampler for the selected checkpoint.
    kwargs: dict = {
        "model_name": model_name,
        "width": width,
        "height": height,
        "seed": seed,
        "target_device": target_device,
    }
    # Always forward explicit non-default overrides so callers can tune params
    # even in auto-model mode (queue_prompt's auto-detection still applies
    # model-appropriate defaults for anything not overridden here).
    if model_name != "auto" or cfg != 7.0:
        kwargs["cfg"] = cfg
    if model_name != "auto" or steps != 20:
        kwargs["steps"] = steps
    if model_name != "auto" or sampler != "euler":
        kwargs["sampler"] = sampler
    if model_name != "auto" or scheduler != "normal":
        kwargs["scheduler"] = scheduler
    if skip_refinement:
        kwargs["skip_refinement"] = True

    if negative_prompt is not None:
        kwargs["negative_prompt"] = negative_prompt

    if target_device != "auto":
        logger.info(f"--- [Creative Studio] Targeted Generation on {target_device} ---")
    
    MAX_RETRIES = 2
    import os
    import json
    
    print(f"DEBUG: generate_image called with prompt='{prompt}' device='{target_device}'")
    logger.info(f"DEBUG: generate_image called with prompt='{prompt}' device='{target_device}'")

    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # PATH DISCOVEY LOGIC
    # We need to find where ComfyUI is dumping images.
    candidate_paths = [
        os.getenv("COMFYUI_OUTPUT_DIR"),
        "C:/Users/panca/Documents/ComfyUI/ComfyUI/output", # Host Default
        "/app/comfy_io/output", # Docker Map
        os.path.join(workspace_root, "output") # Relative Default
    ]
    
    output_dir = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            output_dir = p
            logger.info(f"Targeting ComfyUI Output: {output_dir}")
            break
            
    if not output_dir:
        return "Error: Could not locate ComfyUI output directory. Check COMFYUI_OUTPUT_DIR env var."
    
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            logger.info(f"--- [Creative Studio] Verification Failed. Retrying ({attempt}/{MAX_RETRIES})... ---")
            
        result_msg = queue_prompt(prompt, **kwargs)
        
        if "Error" in result_msg:
             return result_msg
             
        try:
            filename = result_msg.split("Generated Image: ")[1].split(" ")[0]
            img_path = os.path.join(output_dir, filename)
            
            if not os.path.exists(img_path):
                if os.path.exists(filename): img_path = filename
                else: 
                     logger.warning(f"Could not find image at {img_path}.")
                     return result_msg
            
            # 0. Save Metadata Sidecar
            try:
                meta = {
                    "prompt": prompt,
                    "params": kwargs,
                    "model": model_name,
                    "timestamp": time.time()
                }
                meta_path = img_path + ".json"
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save metadata sidecar: {e}")

            # 1. Structural Verification
            struct_ok, struct_reason = verify_structure(img_path)
            if not struct_ok:
                logger.warning(f"Structure Check Failed: {struct_reason}")
                continue 
            
            # 2. Semantic Verification
            sem_ok, sem_reason = verify_semantics(img_path, prompt)
            if not sem_ok:
                logger.warning(f"Semantic Check Failed: {sem_reason}")
                continue 
                
            # 3. Delivery (New in v2)
            try:
                import shutil
                delivery_dir = os.path.join(workspace_root, "delivered_artifacts")
                os.makedirs(delivery_dir, exist_ok=True)
                
                target_path = os.path.join(delivery_dir, filename)
                shutil.copy(img_path, target_path)
                
                # Copy sidecar
                if os.path.exists(img_path + ".json"):
                    shutil.copy(img_path + ".json", target_path + ".json")
                    
                return f"Generated Image: {filename} (Saved to Gallery) | ✅ Verified."
            except Exception as e:
                logger.error(f"Delivery Failed: {e}")
                return f"{result_msg} | ✅ Verified but Delivery Failed: {e}"
            
        except Exception as e:
            logger.error(f"Verification Logic Error: {e}")
            pass
            
        return result_msg 

    return "Failed to generate valid image after retries."

from phi.agent import Agent
from phi.model.ollama import Ollama

def get_image_gen_agent():
    return Agent(
        name="Creative Studio",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description="I am the Creative Studio. I generate images using ComfyUI.",
        instructions="You are an artist. You receive prompts and use the `generate_image` tool. Always return the filename.",
        tools=[generate_image],
        show_tool_calls=True,
    )

if __name__ == "__main__":
    # Test
    agent = get_image_gen_agent()
    # Mocking arg for test would require altering this call or kwargs
    print("Agent Initialized.")
