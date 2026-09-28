import json
import requests
import uuid
import os
import time
import shutil
import logging
from phi.agent import Agent
from phi.model.ollama import Ollama
from config import get_ollama_options

# Logging Setup
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://comfyui_gpu:8188")
MODEL_NAME = "qwen2.5-coder:14b"

# Directories (Mapped Volumes)
COMFY_INPUT_DIR = "/app/comfy_io/input"
COMFY_OUTPUT_DIR = "/app/comfy_io/output"
TEMPLATE_DIR = "/app/agents/templates"

# Default TripoSG quality settings
_DEFAULT_STEPS = 150
_DEFAULT_CFG = 5.0


def prepare_image_for_3d(image_path: str) -> str:
    """
    Prepare an image for 3D generation by removing the background
    and compositing the subject onto a black background.

    TripoSG interprets white/bright areas as solid mass, so the subject
    must be isolated against black (0,0,0) for clean geometry.

    Returns path to the prepared image, or None if preparation fails
    (caller should fall back to original image).
    """
    try:
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGBA")

        # Try rembg for high-quality background removal
        try:
            from rembg import remove
            img_nobg = remove(img)
        except ImportError:
            # Fallback: simple white-background threshold removal
            data = np.array(img)
            # Identify near-white pixels (R>240, G>240, B>240)
            white_mask = (data[:, :, 0] > 240) & (data[:, :, 1] > 240) & (data[:, :, 2] > 240)
            data[white_mask, 3] = 0  # Set alpha to transparent
            img_nobg = Image.fromarray(data)

        # Isolate the single largest subject (handles duplicate characters)
        try:
            import cv2
            alpha = np.array(img_nobg)[:, :, 3]
            _, thresh = cv2.threshold(alpha, 30, 255, cv2.THRESH_BINARY)

            # Morphological close to fill small holes before contour detection
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) >= 1:
                largest = max(contours, key=cv2.contourArea)
                mask = np.zeros_like(alpha)
                cv2.drawContours(mask, [largest], -1, 255, cv2.FILLED)

                # --- Ground shadow removal ---
                # Shadow pixels are semi-transparent, low-saturation, and appear near the
                # BOTTOM of the bounding box. We erase the bottom N% of marginal alpha rows.
                nobg_data = np.array(img_nobg)
                x, y, w, h = cv2.boundingRect(largest)
                shadow_row_threshold = y + int(h * 0.92)  # bottom 8% of bbox
                # Any row below 92% bbox height that is <80% opaque gets zeroed
                for row_idx in range(shadow_row_threshold, nobg_data.shape[0]):
                    row_alpha = nobg_data[row_idx, :, 3].astype(float)
                    if row_alpha.mean() < 200:  # mostly translucent → shadow row
                        nobg_data[row_idx, :, 3] = 0
                    else:
                        break  # stop once we hit a solid row (real feet geometry)

                nobg_data[mask == 0, 3] = 0

                # Recalculate bounding box after shadow strip
                alpha_clean = nobg_data[:, :, 3]
                rows_with_content = np.any(alpha_clean > 30, axis=1)
                cols_with_content = np.any(alpha_clean > 30, axis=0)
                if rows_with_content.any() and cols_with_content.any():
                    row_min, row_max = np.where(rows_with_content)[0][[0, -1]]
                    col_min, col_max = np.where(cols_with_content)[0][[0, -1]]
                    pad = max(row_max - row_min, col_max - col_min) // 20  # 5% padding
                    row_min = max(0, row_min - pad)
                    row_max = min(nobg_data.shape[0], row_max + pad)
                    col_min = max(0, col_min - pad)
                    col_max = min(nobg_data.shape[1], col_max + pad)
                    cropped = nobg_data[row_min:row_max, col_min:col_max]
                else:
                    cropped = nobg_data

                # Resize to square (TripoSG expects square input)
                side = max(cropped.shape[0], cropped.shape[1])
                square = np.zeros((side, side, 4), dtype=np.uint8)
                oy = (side - cropped.shape[0]) // 2
                ox = (side - cropped.shape[1]) // 2
                square[oy:oy + cropped.shape[0], ox:ox + cropped.shape[1]] = cropped

                # Add a safe-zone border (~13% on every side) so the subject never
                # crowds the image edge.  Without this, Hunyuan3D hallucinates the
                # image frame itself as solid occluding geometry (visible as flat
                # rectangular slabs flanking the model in the output mesh).
                safe_fraction = 0.13  # ≈13 % border each side → subject fills central 74 %
                padded_side = int(round(side / (1.0 - 2.0 * safe_fraction)))
                padded = np.zeros((padded_side, padded_side, 4), dtype=np.uint8)
                border_px = (padded_side - side) // 2
                padded[border_px:border_px + side, border_px:border_px + side] = square
                img_nobg = Image.fromarray(padded).resize((1024, 1024), Image.LANCZOS)
                logger.info(
                    "[Forge] Isolated subject from %d contours, stripped ground shadow rows",
                    len(contours),
                )
        except Exception as e:
            logger.warning(f"[Forge] Subject isolation skipped: {e}")

        # Composite onto solid black background
        black_bg = Image.new("RGBA", img_nobg.size, (0, 0, 0, 255))
        composite = Image.alpha_composite(black_bg, img_nobg)
        result = composite.convert("RGB")

        # Save alongside original
        base, ext = os.path.splitext(image_path)
        prepared_path = f"{base}_3d_prep{ext}"
        result.save(prepared_path, quality=95)
        logger.info(f"--- [Forge] Prepared image for 3D: {prepared_path} ---")
        return prepared_path

    except Exception as e:
        logger.warning(f"[Forge] Image preparation failed (using original): {e}")
        return None

def generate_3d_model(image_path: str, workflow_name: str = "workflow_triposg.json", quality_overrides: dict = None) -> str:
    """
    Takes an input image, copies it to ComfyUI input, and triggers a 3D generation workflow.
    
    Args:
        image_path (str): Path to the source 2D image (e.g., from ImageGen agent).
        workflow_name (str): Name of the JSON workflow file template.
        quality_overrides (dict): Optional overrides for workflow params (e.g. {"steps": 75, "cfg": 5.0}).
        
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
    steps_value = _DEFAULT_STEPS
    cfg_value = _DEFAULT_CFG
    if quality_overrides:
        steps_value = quality_overrides.get("steps", steps_value)
        cfg_value = quality_overrides.get("cfg", cfg_value)
    
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
                if obj == "{{SEED}}":
                    return seed_value
                return obj.replace("{{SEED}}", str(seed_value))
            if "{{STEPS}}" in obj:
                if obj == "{{STEPS}}":
                    return int(steps_value)
                return obj.replace("{{STEPS}}", str(int(steps_value)))
            if "{{CFG}}" in obj:
                if obj == "{{CFG}}":
                    return float(cfg_value)
                return obj.replace("{{CFG}}", str(cfg_value))
        return obj

    # Apply replacement to the entire workflow structure
    workflow = recursive_replace(workflow)
    logger.info(f"--- [Forge] Applied Seed: {seed_value} ---")

    # 5. Queue Prompt
    payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}
    
    try:
        url = f"{COMFYUI_HOST}/prompt"
        req = requests.post(url, json=payload, timeout=30)

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
    logger.info("--- [Forge] Waiting for 3D generation (Max 30 Minutes)... ---")
    time.sleep(5) 
    
    timeout_seconds = 1800 # 30 Minutes
    start_time = time.time()

    def find_recent_output_file() -> str | None:
        latest_match = None
        latest_mtime = start_time
        for root, _, files in os.walk(COMFY_OUTPUT_DIR):
            for fname in files:
                if not fname.lower().endswith((".glb", ".obj", ".3mf")):
                    continue
                full_path = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(full_path)
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_match = full_path
                    latest_mtime = mtime
        return latest_match

    lost_count = 0
    
    while (time.time() - start_time) < timeout_seconds:
        try:
            # Check History (Did it finish?)
            history_url = f"{COMFYUI_HOST}/history/{prompt_id}"
            res = requests.get(history_url, timeout=10)
            history = res.json()
            
            if prompt_id in history:
                entry = history[prompt_id]
                status_str = entry.get('status', {}).get('status_str', '')
                if status_str == 'error':
                    msgs = entry.get('status', {}).get('messages', [])
                    err_detail = "Unknown ComfyUI error"
                    err_node = ""
                    for msg in msgs:
                        if isinstance(msg, list) and msg[0] == 'execution_error':
                            err_detail = msg[1].get('exception_message', err_detail)
                            err_node = msg[1].get('node_type', '')
                            break
                    node_hint = f" (node: {err_node})" if err_node else ""
                    return f"Error: ComfyUI 3D generation failed{node_hint}: {err_detail.strip()}"

                logger.info("--- [Forge] Generation Complete. Parsing outputs... ---")
                outputs = entry.get('outputs', {})
                
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
                        # Handle dict items (e.g. SaveImage nodes)
                        if isinstance(item, dict) and 'filename' in item:
                            fname = item['filename']
                            subfolder = item.get('subfolder', '')
                        # Handle string items (e.g. SaveTrimesh glb_path)
                        elif isinstance(item, str):
                            fname = item
                            subfolder = ''
                        else:
                            continue
                        # Look for 3D extensions
                        if fname.endswith('.glb') or fname.endswith('.obj') or fname.endswith('.3mf'):
                            full_path = os.path.join(COMFY_OUTPUT_DIR, subfolder, fname)
                            logger.info(f"--- [Forge] Found 3D Model: {full_path} ---")
                            return f"3D Model Generated Successfully: {full_path}"
                                
                fallback_output = find_recent_output_file()
                if fallback_output:
                    logger.info(f"--- [Forge] Found 3D Model via output scan: {fallback_output} ---")
                    return f"3D Model Generated Successfully: {fallback_output}"

                return "Error: Generation finished but no 3D model file (.glb/.obj) was found in outputs or recent output scan."

            # Check Queue (Is it still running?)
            # This prevents premature timeouts if the queue is deep or processing is slow
            queue_url = f"{COMFYUI_HOST}/queue"
            q_res = requests.get(queue_url, timeout=10)
            q_data = q_res.json()
            
            # Queue data format: { "queue_pending": [...], "queue_running": [...] }
            is_pending = any(item[1] == prompt_id for item in q_data.get('queue_pending', []))
            is_running = any(item[1] == prompt_id for item in q_data.get('queue_running', []))
            
            if is_pending:
                # If pending, we can reset start_time to avoid timeout while waiting in line
                # start_time = time.time() # Optional: specialized agent doesn't want to wait forever?
                pass
            
            if not is_pending and not is_running:
                # Not in history, queue, or running — may be lost
                lost_count += 1
                if lost_count > 5:
                    return "Error: ComfyUI job disappeared from queue without producing output."

            time.sleep(5)
        except Exception as e:
            logger.warning(f"Polling error: {e}")
            time.sleep(5)

    return "Error: 3D Generation timed out after 30 minutes."

def get_forge_agent():
    return Agent(
        name="Creature Forge",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST, options=get_ollama_options(MODEL_NAME)),
        description="I am the 3D Blacksmith. I turn images into 3D models using the Forge pipeline.",
        instructions="Use `generate_3d_model` to convert 2D concept art into 3D assets. You need a source image path first.",
        tools=[generate_3d_model],
        show_tool_calls=True,
    )

if __name__ == "__main__":
    # Test
    agent = get_forge_agent()
    agent.print_response("Status check")
