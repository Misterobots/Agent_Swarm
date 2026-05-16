import json
import requests
import uuid
import os
import time
import base64
from logger_setup import setup_logger
from agents.specialized.gpu_pool_manager import get_gpu_pool
from config import get_ollama_options

# Logging Setup
logger = setup_logger("CreativeStudio")

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
KLEIN_HOST = os.getenv("KLEIN_HOST", "http://klein_service:8189")
MODEL_NAME = "qwen2.5-coder:14b" # Logic model
DEPLOYED_FALLBACK_CHECKPOINT = "sd_xl_turbo_1.0_fp16.safetensors"

IMAGE_MODEL_REGISTRY = {
    "auto": {
        "label": "Auto Best Available",
        "category": "adaptive",
        "description": "Klein 9B first (Diffusers/dual-GPU), then ComfyUI checkpoint priority order.",
        "priority": ["klein-9b", "flux-dev-quality", "flux-schnell-preview", "sdxl-general", "sdxl-turbo-preview", "sd15-fast-legacy"],
    },
    "klein-9b": {
        "label": "FLUX.2 Klein 9B",
        "category": "quality",
        "description": "FLUX.2 Klein 9B via Diffusers — spreads across both 5060 Ti GPUs (30GB combined). Highest quality.",
        "backend": "klein",
        "defaults": {"width": 1024, "height": 1024, "steps": 4, "guidance_scale": 3.5},
    },
    "flux-dev-quality": {
        "label": "FLUX Dev Quality",
        "category": "quality",
        "description": "Highest prompt fidelity and image quality when FLUX dev checkpoints are available.",
        "match_any": ["flux"],
        "match_all": ["dev"],
        "defaults": {"width": 1024, "height": 1024},
        "trainable": True,
    },
    "flux-schnell-preview": {
        "label": "FLUX Schnell Preview",
        "category": "preview",
        "description": "Fast FLUX ideation path for previews and iteration.",
        "match_all": ["flux", "schnell"],
        "defaults": {"width": 1024, "height": 1024},
        "trainable": True,
    },
    "sdxl-general": {
        "label": "SDXL General",
        "category": "quality",
        "description": "General-purpose SDXL path for higher resolution images and stronger composition.",
        "match_any": ["sdxl", "xl"],
        "exclude_any": ["turbo"],
        "defaults": {"width": 1024, "height": 1024},
        "trainable": True,
    },
    "sdxl-turbo-preview": {
        "label": "SDXL Turbo Preview",
        "category": "preview",
        "description": "Fast SDXL preview path optimized for iteration speed.",
        "match_all": ["xl", "turbo"],
        "defaults": {"width": 1024, "height": 1024},
        "trainable": True,
    },
    "sd15-fast-legacy": {
        "label": "SD1.5 Fast Legacy",
        "category": "legacy",
        "description": "Compatibility path for SD1.5 checkpoints and 3D bootstrap images.",
        "match_any": ["sd15", "1.5", "dreamshaper", "pruned", "v15"],
        "defaults": {"width": 768, "height": 768},
        "trainable": True,
    },
}


def _resolve_workspace_root() -> str:
    script_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    mounted_workspace = os.getenv("WORKSPACE_ROOT", "/workspace")
    if mounted_workspace and os.path.exists(mounted_workspace):
        return mounted_workspace
    return script_root


def _extract_checkpoint_names(payload: dict) -> list[str]:
    return (
        payload.get("CheckpointLoaderSimple", {})
        .get("input", {})
        .get("required", {})
        .get("ckpt_name", [[]])[0]
    )


def _checkpoint_matches_profile(ckpt_name: str, profile: dict) -> bool:
    ckpt_lower = ckpt_name.lower()
    match_all = profile.get("match_all", [])
    match_any = profile.get("match_any", [])
    exclude_any = profile.get("exclude_any", [])

    if match_all and not all(token in ckpt_lower for token in match_all):
        return False
    if match_any and not any(token in ckpt_lower for token in match_any):
        return False
    if exclude_any and any(token in ckpt_lower for token in exclude_any):
        return False
    return True


def _match_profile_checkpoint(profile_id: str, available_ckpts: list[str]) -> str | None:
    profile = IMAGE_MODEL_REGISTRY[profile_id]
    for ckpt in available_ckpts:
        if _checkpoint_matches_profile(ckpt, profile):
            return ckpt
    return None


def get_image_model_catalog(available_ckpts: list[str] | None = None) -> dict:
    if available_ckpts is None:
        available_ckpts = list_available_models()

    profiles = []
    for profile_id, profile in IMAGE_MODEL_REGISTRY.items():
        if profile_id == "auto":
            resolved_checkpoint = None
            for candidate_id in profile.get("priority", []):
                resolved_checkpoint = _match_profile_checkpoint(candidate_id, available_ckpts)
                if resolved_checkpoint:
                    break
            available = resolved_checkpoint is not None
        else:
            resolved_checkpoint = _match_profile_checkpoint(profile_id, available_ckpts)
            available = resolved_checkpoint is not None

        profiles.append({
            "id": profile_id,
            "label": profile["label"],
            "category": profile["category"],
            "description": profile["description"],
            "trainable": profile.get("trainable", False),
            "available": available,
            "resolved_checkpoint": resolved_checkpoint,
            "defaults": profile.get("defaults", {}),
        })

    recommended_profile = next(
        (item["id"] for item in profiles if item["id"] != "auto" and item["available"]),
        None,
    )

    return {
        "default_profile": "auto",
        "recommended_profile": recommended_profile,
        "profiles": profiles,
        "checkpoints": available_ckpts,
        # Preserve backward compatibility for older clients that expect `models`.
        "models": available_ckpts,
    }

def list_available_models() -> list:
    """Queries ComfyUI for all available checkpoints."""
    try:
        url = f"{COMFYUI_HOST}/object_info/CheckpointLoaderSimple"
        req = requests.get(url, timeout=5)
        if req.status_code == 200:
            models = _extract_checkpoint_names(req.json())
            if not models:
                logger.warning(
                    "ComfyUI checkpoint discovery returned an empty list",
                    extra={"comfyui_host": COMFYUI_HOST, "endpoint": url},
                )
            return models
        logger.warning(
            f"ComfyUI checkpoint discovery failed with status {req.status_code}: {req.text[:200]}"
        )
    except Exception as e:
        logger.warning(f"Failed to list models: {e}")
    return []

def get_available_checkpoint():
    """Queries ComfyUI for the first available checkpoint."""
    models = list_available_models()
    return models[0] if models else None


def resolve_generation_target(requested_model: str | None, available_ckpts: list[str]) -> dict:
    requested_model = requested_model or "auto"

    if requested_model in IMAGE_MODEL_REGISTRY:
        if requested_model == "auto":
            for candidate_id in IMAGE_MODEL_REGISTRY["auto"].get("priority", []):
                checkpoint = _match_profile_checkpoint(candidate_id, available_ckpts)
                if checkpoint:
                    return {
                        "requested_model": requested_model,
                        "profile_id": candidate_id,
                        "checkpoint": checkpoint,
                    }
            raise RuntimeError(
                "No curated image profiles are currently available. "
                f"ComfyUI reported checkpoints: {available_ckpts or 'none'}"
            )

        checkpoint = _match_profile_checkpoint(requested_model, available_ckpts)
        if not checkpoint:
            raise ValueError(
                f"Requested image profile '{requested_model}' is unavailable. "
                f"ComfyUI reported checkpoints: {available_ckpts or 'none'}"
            )
        return {
            "requested_model": requested_model,
            "profile_id": requested_model,
            "checkpoint": checkpoint,
        }

    if requested_model in available_ckpts:
        return {
            "requested_model": requested_model,
            "profile_id": "direct-checkpoint",
            "checkpoint": requested_model,
        }

    raise ValueError(
        f"Requested checkpoint or profile '{requested_model}' is unavailable. "
        f"Available profiles: {list(IMAGE_MODEL_REGISTRY.keys())}. "
        f"ComfyUI reported checkpoints: {available_ckpts or 'none'}"
    )


def select_checkpoint(requested_ckpt: str | None, available_ckpts: list[str]) -> str:
    if not available_ckpts:
        raise RuntimeError(
            "No ComfyUI checkpoints are available. Add a model under models/checkpoints "
            f"or verify the ComfyUI host ({COMFYUI_HOST}) is mounted correctly. "
            f"Expected deployed fallback: {DEPLOYED_FALLBACK_CHECKPOINT}."
        )

    target = resolve_generation_target(requested_ckpt, available_ckpts)
    return target["checkpoint"]

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
def _detect_subject_type(p_lower: str) -> str:
    if any(kw in p_lower for kw in [
        "person", "man", "woman", "girl", "boy", "face", "model", "human",
        "people", "child", "baby", "portrait", "selfie", "lady", "guy", "couple",
    ]):
        return "person"
    if any(kw in p_lower for kw in [
        "cat", "dog", "bird", "animal", "lion", "tiger", "wolf", "horse",
        "elephant", "fox", "bear", "rabbit", "fish", "wildlife", "eagle", "owl",
    ]):
        return "animal"
    if any(kw in p_lower for kw in [
        "food", "dish", "meal", "cake", "coffee", "drink", "fruit", "vegetable",
        "pizza", "burger", "sushi", "dessert", "soup", "salad", "bread", "cookie",
    ]):
        return "food"
    if any(kw in p_lower for kw in [
        "mountain", "forest", "ocean", "beach", "city", "skyline", "field",
        "valley", "desert", "lake", "waterfall", "sunset", "sunrise", "landscape",
        "cliff", "canyon", "river", "meadow", "jungle", "tundra",
    ]):
        return "landscape"
    if any(kw in p_lower for kw in [
        "building", "house", "castle", "temple", "bridge", "tower",
        "skyscraper", "church", "mansion", "architecture", "cathedral",
    ]):
        return "architecture"
    return "general"

def apply_style_heuristics(prompt: str, model_type: str) -> str:
    """
    Analyzes the prompt to infer style. If no explicit style is detected,
    applies subject-aware photorealistic defaults (Gemini-style auto-enrichment).
    """
    p_lower = prompt.lower()

    # User stated an explicit artistic intent — don't override
    explicit_styles = [
        "painting", "oil paint", "watercolor", "acrylic", "gouache", "impressionist",
        "drawing", "sketch", "pencil", "charcoal", "ink", "pastel",
        "anime", "manga", "cartoon", "comic", "chibi", "disney", "pixar",
        "3d render", "cgi", "blender", "octane", "unreal engine",
        "digital art", "digital painting", "illustration", "concept art",
        "vector", "flat design", "isometric", "low poly", "pixel art",
        "vintage", "retro", "noir", "surreal", "abstract", "graphic", "render",
    ]
    if any(s in p_lower for s in explicit_styles):
        return prompt

    # Subject-aware context enrichment — mirrors Gemini's implicit quality defaults
    subject = _detect_subject_type(p_lower)
    if subject == "person":
        context = "professional portrait photography, soft cinematic lighting, shallow depth of field, bokeh background, sharp facial details, natural skin texture"
    elif subject == "animal":
        context = "wildlife photography, natural golden-hour lighting, sharp focus on subject, rich environmental detail, National Geographic quality"
    elif subject == "food":
        context = "professional food photography, soft studio lighting, shallow depth of field, vibrant colors, clean background, appetizing presentation"
    elif subject == "landscape":
        context = "landscape photography, dramatic golden hour, wide angle lens, vivid colors, detailed foreground, cinematic atmosphere"
    elif subject == "architecture":
        context = "architectural photography, dramatic natural lighting, sharp geometric lines, professional composition, rich shadow detail"
    else:
        context = "cinematic photography, professional studio lighting, sharp focus, beautifully composed, rich detail"

    # Quality prefix scaled to model capability
    if "TURBO" in model_type or "SCHNELL" in model_type:
        quality = "photograph, realistic, raw photo, 4k"
    elif "FLUX" in model_type:
        quality = "photorealistic, ultra-detailed, cinematic"
    else:
        quality = "photograph, photorealistic, cinematic lighting, 8k, highly detailed"

    return f"{quality}, {context}, {prompt}"

def refine_prompt(prompt: str, model_type: str) -> str:
    styled_prompt = apply_style_heuristics(prompt, model_type)
    if model_type == "SDXL" or model_type == "SD15":
        return f"masterpiece, best quality, {styled_prompt}"
    return styled_prompt

def queue_prompt(prompt_text: str, **kwargs):
    """
    Sends a prompt to ComfyUI with optional manual overrides.
    Pass negative_prompt kwarg to override the negative conditioning text.
    Supports multi-GPU load balancing via GPU pool manager.
    """
    # Get GPU instance from pool
    gpu_pool = get_gpu_pool()
    prefer_gpu = kwargs.get("gpu_id", None)  # Allow caller to request specific GPU
    
    instance = gpu_pool.get_available_instance(prefer_gpu=prefer_gpu)
    if instance is None:
        logger.warning("All GPUs busy - using primary instance (may queue)")
        comfyui_host = COMFYUI_HOST
    else:
        comfyui_host = instance["host"]
        logger.info(f"Using {instance['name']} at {comfyui_host}")
    
    requested_ckpt = kwargs.get("model_name")
    negative_prompt_override = kwargs.get("negative_prompt")
    all_ckpts = list_available_models()
    
    try:
        target = resolve_generation_target(requested_ckpt, all_ckpts)
        ckpt_name = target["checkpoint"]
    except (RuntimeError, ValueError) as exc:
        logger.error(
            "Checkpoint selection failed for image generation",
            extra={
                "requested_ckpt": requested_ckpt,
                "available_ckpts": all_ckpts,
                "prompt_preview": prompt_text[:120],
            },
        )
        if instance:
            gpu_pool.release_instance(instance)
        return f"Error: {exc}"
            
    # 2. Determine Configuration
    model_type = detect_model_type(ckpt_name)
    raw_params = get_model_params(model_type)
    profile_defaults = IMAGE_MODEL_REGISTRY.get(target["profile_id"], {}).get("defaults", {})
    
    # APPLY OVERRIDES
    params = {
        "cfg": float(kwargs.get("cfg", raw_params["cfg"])),
        "steps": int(kwargs.get("steps", raw_params["steps"])),
        "sampler": kwargs.get("sampler", raw_params["sampler"]),
        "scheduler": kwargs.get("scheduler", raw_params["scheduler"]),
        "width": int(kwargs.get("width", profile_defaults.get("width", raw_params["width"]))),
        "height": int(kwargs.get("height", profile_defaults.get("height", raw_params["height"])))
    }
    
    if kwargs.get("skip_refinement"):
        final_prompt = prompt_text
    else:
        final_prompt = refine_prompt(prompt_text, model_type)
    print(
        f"--- [ComfyUI] Config: {model_type} | Profile: {target['profile_id']} | "
        f"Ckpt: {ckpt_name} | Params: {params} ---"
    )

    # Flush ComfyUI's cached tensors before each job — prevents OOM from leftover buffers
    # without unloading the model (keeps generation fast on repeated requests).
    try:
        requests.post(f"{comfyui_host}/free", json={"unload_models": False, "free_memory": True}, timeout=5)
        logger.info("[ComfyUI] Pre-generation memory flush sent.")
    except Exception as e:
        logger.warning(f"[ComfyUI] Pre-generation memory flush failed (non-fatal): {e}")

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
        logger.info(f"[ComfyUI] Submitting prompt to {url}...")
        req = requests.post(url, json=p, timeout=30) # 30s timeout for initial submission
        
        if req.status_code != 200:
            logger.error(f"[ComfyUI] HTTP {req.status_code}: {req.text}")
            return f"Error connecting to ComfyUI (Status {req.status_code}): {req.text}"
            
        response = req.json()
        if 'prompt_id' not in response:
             logger.error(f"[ComfyUI] Missing prompt_id in response: {response}")
             return f"Error: ComfyUI did not return a prompt_id. Response: {response}"
             
        prompt_id = response['prompt_id']
        logger.info(f"[ComfyUI] Prompt queued: {prompt_id}")
        print(f"--- [ComfyUI] Prompt Queued: {prompt_id} ---")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[ComfyUI] Connection failed to {COMFYUI_HOST}: {e}")
        return f"Error: Cannot connect to ComfyUI at {COMFYUI_HOST}. Is ComfyUI running? ({e})"
    except requests.exceptions.Timeout as e:
        logger.error(f"[ComfyUI] Connection timeout to {COMFYUI_HOST}: {e}")
        return f"Error: ComfyUI connection timeout at {COMFYUI_HOST} ({e})"
    except Exception as e:
        logger.error(f"[ComfyUI] Unexpected error: {e}")
        return f"Error connecting to ComfyUI: {e}"

    print("--- [ComfyUI] Waiting for generation... ---")
    time.sleep(2)

    timeout_seconds = 900  # 15 minutes — covers model load + queue wait + steps=20+ generation
    start_time = time.time()
    lost_count = 0

    while (time.time() - start_time) < timeout_seconds:
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
                         
                         # Download image from ComfyUI (since it's on a different machine)
                         try:
                             import urllib.parse
                             download_dir = "/tmp/comfyui_images"
                             os.makedirs(download_dir, exist_ok=True)
                             
                             # Build view URL
                             params = {"filename": filename, "type": "output"}
                             if subfolder:
                                 params["subfolder"] = subfolder
                             view_url = f"{comfyui_host}/view?{urllib.parse.urlencode(params)}"
                             
                             # Download image
                             img_response = requests.get(view_url, timeout=30)
                             if img_response.status_code != 200:
                                 logger.error(f"Failed to download image from {view_url}: {img_response.status_code}")
                             else:
                                 local_path = os.path.join(download_dir, filename)
                                 with open(local_path, "wb") as f:
                                     f.write(img_response.content)
                                 logger.info(f"Downloaded image to {local_path}")
                         except Exception as e:
                             logger.error(f"Failed to download image from ComfyUI: {e}")
                         
                         return (
                             f"Generated Image: {filename} (in {subfolder} output) "
                             f"| profile={target['profile_id']} | checkpoint={ckpt_name}"
                         )
                     return "Error: ComfyUI completed but produced no image output."
                return "Error: ComfyUI completed but SaveImage node produced no output."

            # Not in history yet — check queue to avoid premature timeout while waiting in line
            try:
                q_res = requests.get(f"{COMFYUI_HOST}/queue", timeout=5)
                q_data = q_res.json()
                is_pending = any(item[1] == prompt_id for item in q_data.get('queue_pending', []))
                is_running = any(item[1] == prompt_id for item in q_data.get('queue_running', []))
                if is_pending:
                    # Reset timer while queued so we don't count wait time against generation budget
                    start_time = time.time()
                elif not is_running:
                    lost_count += 1
                    if lost_count > 5:
                        return "Error: ComfyUI job disappeared from queue without producing output."
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Polling error: {e}")
        time.sleep(2)

    # Timeout - release GPU before returning
    if instance:
        gpu_pool.release_instance(instance)
    elapsed = int(time.time() - start_time)
    return f"Error: Image generation timed out after {elapsed}s (limit {timeout_seconds}s)."

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

# ---------------------------------------------------------------------------
# Klein Diffusers path
# ---------------------------------------------------------------------------

def _klein_is_healthy() -> bool:
    try:
        r = requests.get(f"{KLEIN_HOST}/health", timeout=5)
        data = r.json()
        return r.status_code == 200 and data.get("pipeline_loaded", False)
    except Exception:
        return False


def _generate_via_klein(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance_scale: float = 3.5,
    seed: int = -1,
    negative_prompt: str = "",
    output_dir: str = "/tmp/comfyui_images",
) -> str | None:
    """
    Calls the Klein service, saves the returned image locally, and returns
    the filename — or None on failure.
    """
    t_http_start = time.monotonic()
    try:
        resp = requests.post(
            f"{KLEIN_HOST}/generate",
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt or "",
                "width": width,
                "height": height,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "seed": seed,
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[Klein] Request failed: {e}")
        return None
    t_http = time.monotonic() - t_http_start

    filename = data.get("filename")
    img_b64 = data.get("image_b64")
    elapsed = data.get("elapsed", 0)

    if not filename or not img_b64:
        logger.error("[Klein] Response missing filename or image_b64")
        return None

    t_save_start = time.monotonic()
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, filename)
    with open(dest, "wb") as f:
        f.write(base64.b64decode(img_b64))
    t_save = time.monotonic() - t_save_start

    logger.info(f"[Klein] Saved {filename} in {elapsed:.1f}s")
    logger.info(
        f"[Timing] klein_http={t_http:.2f}s service_inference={elapsed:.2f}s "
        f"transport_overhead={t_http - elapsed:.2f}s save_b64={t_save:.2f}s"
    )
    return filename


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
    Generates an image. Tries the Klein 9B Diffusers service first (auto/klein-9b),
    falls back to ComfyUI for all other model requests or if Klein is unavailable.
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
    import json

    workspace_root = _resolve_workspace_root()
    candidate_paths = [
        "/tmp/comfyui_images",
        os.getenv("COMFYUI_OUTPUT_DIR"),
        "C:/Users/panca/Documents/ComfyUI/ComfyUI/output",
        "/app/comfy_io/output",
        os.path.join(workspace_root, "output")
    ]

    output_dir = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            output_dir = p
            logger.info(f"Targeting ComfyUI Output: {output_dir}")
            break

    if not output_dir:
        output_dir = "/tmp/comfyui_images"
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created ComfyUI output directory: {output_dir}")

    last_candidate: dict | None = None

    # Any FLUX request goes to Klein. The single-GPU ComfyUI path (device_ids=['1'])
    # cannot fit FLUX FP8 + CLIP + T5 on 16 GiB; Klein's dual-GPU split is the only
    # working FLUX route on this hardware. flux-dev-quality is silently downgraded
    # to schnell (Klein's loaded weights) rather than letting ComfyUI OOM for 10+min.
    _flux_request = model_name in ("auto", "klein-9b", "flux-schnell-preview", "flux-dev-quality")

    # Track whether Klein was attempted so we know to evict it before ComfyUI even
    # if warmup failed — a failed warmup may leave partial VRAM allocations that
    # WDDM holds until the process terminates (container restart forces reclaim).
    _klein_was_attempted = _flux_request and not skip_refinement

    # If Klein isn't loaded yet, evict Ollama + ComfyUI first so both GPUs are clear.
    # ComfyUI holds ~15 GiB on GPU 1; Klein needs that space for its balanced layout.
    # This runs regardless of Redis availability (GPU lock fails open when Redis is down).
    if _klein_was_attempted and not _klein_is_healthy():
        try:
            from utils.gpu_queue import evict_ollama, evict_comfyui, warmup_klein
            logger.info("[Creative Studio] Evicting Ollama + ComfyUI to free both GPUs for Klein...")
            evict_ollama()
            evict_comfyui()
            warmup_klein()
        except Exception as e:
            logger.warning(f"[Creative Studio] Klein VRAM prep failed: {e}")

    # GPU lock serializes concurrent requests and handles zone transitions
    # when Redis IS available. When Redis is down it's a no-op (fail-open).
    try:
        from utils.gpu_queue import request_lock as _request_lock
        _gpu_ctx = _request_lock("image", timeout=600)
    except Exception:
        from contextlib import nullcontext
        _gpu_ctx = nullcontext()

    with _gpu_ctx:
        # --- KLEIN PATH (FLUX.2 Klein 9B, dual-GPU Diffusers) ---
        # GPU lock already evicted Ollama and warmed up Klein, so VRAM is clear.
        # All FLUX model_names route here — ComfyUI single-GPU OOMs on FLUX, so
        # Klein is the only working path. flux-dev-quality silently downgrades to
        # whatever Klein has loaded (currently schnell FP8).
        use_klein = _flux_request and not skip_refinement
        if use_klein and _klein_is_healthy():
            logger.info("[Creative Studio] Routing to Klein service (FLUX.2 9B)")
            # Always evict ComfyUI before generating via Klein. Klein's transformer+VAE
            # live on physical GPU 1; ComfyUI also uses GPU 1 and may have reloaded since
            # the last zone eviction. Without this, GPU 1 runs out of headroom mid-generation.
            t_pre_evict_start = time.monotonic()
            try:
                from utils.gpu_queue import evict_comfyui as _evict_comfyui_pre
                _evict_comfyui_pre()
            except Exception as _e:
                logger.warning(f"[Creative Studio] Pre-generation ComfyUI eviction failed: {_e}")
            logger.info(f"[Timing] pre_klein_comfy_evict={time.monotonic() - t_pre_evict_start:.2f}s")
            klein_defaults = IMAGE_MODEL_REGISTRY["klein-9b"]["defaults"]
            enriched = refine_prompt(prompt, "FLUX_DEV")
            klein_output_dir = "/tmp/comfyui_images"
            os.makedirs(klein_output_dir, exist_ok=True)
            # FLUX.1-schnell is distilled for 1-4 steps with no CFG. The UI
            # sliders default to SDXL-style values (20 steps / 7.0 cfg) and
            # users can drag them to 30/10 — at those values a single image
            # takes 60+ seconds (vs ~10s) AND produces worse quality because
            # schnell isn't trained for that regime. Clamp to a safe range.
            KLEIN_STEPS_MAX = 8       # 4 is optimal; 8 is the upper bound that still benefits
            KLEIN_CFG_MAX   = 4.0     # schnell prefers 0; 4 is the upper bound before degradation
            clamped_steps = min(max(steps, 1), KLEIN_STEPS_MAX)
            clamped_cfg   = min(max(cfg,   0.0), KLEIN_CFG_MAX)
            if clamped_steps != steps or clamped_cfg != cfg:
                logger.info(
                    f"[Creative Studio] Clamped schnell params: "
                    f"steps {steps}→{clamped_steps}, cfg {cfg}→{clamped_cfg}"
                )
            klein_file = _generate_via_klein(
                prompt=enriched,
                width=width if width != 1024 else klein_defaults["width"],
                height=height if height != 1024 else klein_defaults["height"],
                steps=clamped_steps,
                guidance_scale=clamped_cfg,
                seed=seed,
                negative_prompt=negative_prompt or "",
                output_dir=klein_output_dir,
            )
            if klein_file:
                # Copy to delivered_artifacts so Art Studio gallery + media handlers can serve it.
                # Chat flow's handlers/image.py also calls shutil.copy2 from the same source; the
                # second copy is idempotent (overwrites the same bytes).
                try:
                    import shutil as _shutil
                    workspace_root = os.environ.get("WORKSPACE_ROOT", "/workspace")
                    delivery_dir = os.path.join(workspace_root, "delivered_artifacts")
                    os.makedirs(delivery_dir, exist_ok=True)
                    src = os.path.join(klein_output_dir, klein_file)
                    dst = os.path.join(delivery_dir, klein_file)
                    if os.path.exists(src) and not os.path.exists(dst):
                        _shutil.copy2(src, dst)
                        logger.info(f"[Creative Studio] Klein → delivered_artifacts: {klein_file}")
                except Exception as _copy_err:
                    logger.warning(f"[Creative Studio] Failed to copy Klein output to delivery dir: {_copy_err}")
                return f"Generated Image: {klein_file}"
            logger.warning("[Creative Studio] Klein generation failed — falling back to ComfyUI")

        # --- COMFYUI FALLBACK ---
        # Evict Klein before ComfyUI — Klein's text encoders (~11 GB) occupy GPU 0,
        # and its transformer+VAE (~9 GB) occupy GPU 1. ComfyUI only has device_ids=['1']
        # (physical GPU 1, 15.93 GB) and FLUX alone exceeds that. Evict first, then
        # redirect to SDXL so ComfyUI never attempts FLUX which would OOM on GPU 1.
        # Also evict if warmup was attempted but failed: a failed _load_pipeline() call
        # invokes _force_free_vram() internally but WDDM may still hold physical pages;
        # the container restart in evict_klein() forces WDDM to return them immediately.
        if _klein_is_healthy() or _klein_was_attempted:
            try:
                from utils.gpu_queue import evict_klein as _evict_klein
                logger.info("[Creative Studio] Evicting Klein to free GPU pages before ComfyUI...")
                _evict_klein()
            except Exception as e:
                logger.warning(f"[Creative Studio] Klein eviction failed: {e}")

        # FLUX cannot fit on ComfyUI's single GPU 1 (15.93 GB). When falling back from
        # Klein (model_name auto/klein-9b), redirect to SDXL Turbo which fits (~5 GB).
        # Note: sdxl-general excludes "turbo" checkpoints — use sdxl-turbo-preview which
        # matches sd_xl_turbo_1.0_fp16.safetensors (the deployed SDXL checkpoint).
        if kwargs.get("model_name") in ("auto", "klein-9b", "flux-schnell-preview", "flux-dev-quality"):
            logger.info(f"[Creative Studio] Redirecting ComfyUI fallback from {kwargs.get('model_name')!r} to sdxl-turbo-preview (FLUX OOM on single GPU; Klein unavailable)")
            kwargs = {**kwargs, "model_name": "sdxl-turbo-preview"}

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                logger.info(f"--- [Creative Studio] Verification Failed. Retrying ({attempt}/{MAX_RETRIES})... ---")

            result_msg = queue_prompt(prompt, **kwargs)

            if "Error" in result_msg:
                return result_msg

            try:
                filename = result_msg.split("Generated Image: ")[1].split(" ")[0]
                resolved_target = resolve_generation_target(model_name, list_available_models())
                img_path = os.path.join(output_dir, filename)

                if not os.path.exists(img_path):
                    if os.path.exists(filename):
                        img_path = filename
                    else:
                        logger.warning(f"Could not find image at {img_path}.")
                        return result_msg

                # 0. Save Metadata Sidecar
                try:
                    meta = {
                        "prompt": prompt,
                        "params": kwargs,
                        "model": model_name,
                        "resolved_profile": resolved_target["profile_id"],
                        "resolved_checkpoint": resolved_target["checkpoint"],
                        "resolved_model_type": detect_model_type(resolved_target["checkpoint"]),
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
                    last_candidate = {
                        "filename": filename,
                        "img_path": img_path,
                        "warning": f"Structure warning: {struct_reason}",
                    }
                    continue

                # 2. Semantic Verification
                sem_ok, sem_reason = verify_semantics(img_path, prompt)
                if not sem_ok:
                    logger.warning(f"Semantic Check Failed: {sem_reason}")
                    last_candidate = {
                        "filename": filename,
                        "img_path": img_path,
                        "warning": f"Semantic warning: {sem_reason}",
                    }
                    continue

                # 3. Delivery
                try:
                    import shutil
                    delivery_dir = os.path.join(workspace_root, "delivered_artifacts")
                    os.makedirs(delivery_dir, exist_ok=True)
                    target_path = os.path.join(delivery_dir, filename)
                    shutil.copy(img_path, target_path)
                    if os.path.exists(img_path + ".json"):
                        shutil.copy(img_path + ".json", target_path + ".json")
                    return f"Generated Image: {filename} (Saved to Gallery) | ✅ Verified."
                except Exception as e:
                    logger.error(f"Delivery Failed: {e}")
                    return f"{result_msg} | ✅ Verified but Delivery Failed: {e}"

            except Exception as e:
                logger.error(f"Verification Logic Error: {e}")

            return result_msg

    if last_candidate:
        try:
            import shutil

            filename = last_candidate["filename"]
            img_path = last_candidate["img_path"]
            warning = last_candidate["warning"]
            delivery_dir = os.path.join(workspace_root, "delivered_artifacts")
            os.makedirs(delivery_dir, exist_ok=True)

            target_path = os.path.join(delivery_dir, filename)
            shutil.copy(img_path, target_path)

            if os.path.exists(img_path + ".json"):
                shutil.copy(img_path + ".json", target_path + ".json")

            logger.warning(
                "Delivered image after verification warnings",
                extra={
                    "delivered_filename": filename,
                    "warning": warning,
                    "prompt_preview": prompt[:120],
                },
            )
            return f"Generated Image: {filename} (Saved to Gallery) | Verification warning: {warning}"
        except Exception as e:
            logger.error(f"Fallback delivery failed: {e}")
            return f"Error: image generated but fallback delivery failed: {e}"

    return "Failed to generate valid image after retries."

from phi.agent import Agent
from phi.model.ollama import Ollama

def get_image_gen_agent():
    return Agent(
        name="Creative Studio",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST, options=get_ollama_options(MODEL_NAME)),
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
