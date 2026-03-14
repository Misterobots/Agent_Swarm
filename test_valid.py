import requests
import json
import time
import uuid

HOST = "http://comfyui_gpu:8188"

def get_checkpoints():
    try:
        res = requests.get(f"{HOST}/object_info/CheckpointLoaderSimple")
        if res.status_code == 200:
            return res.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    except:
        pass
    return []

def test_gen():
    ckpts = get_checkpoints()
    print(f"Available Checkpoints: {ckpts}")
    if not ckpts:
        print("ERROR: No checkpoints found. Cannot test generation.")
        return

    ckpt = ckpts[0]
    print(f"Using Checkpoint: {ckpt}")

    # Minimal Workflow (Text -> Image)
    # IDs: 1: Load Chkpt, 2: Empty Latent, 3: KSampler, 4: VAE Decode, 5: Save Image, 6: CLIP Text (Pos), 7: CLIP Text (Neg)
    prompt = {
        "3": {
            "inputs": {
                "seed": 12345, "steps": 10, "cfg": 8, "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
                "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["2", 0]
            },
            "class_type": "KSampler"
        },
        "4": {
            "inputs": { "samples": ["3", 0], "vae": ["1", 2] },
            "class_type": "VAEDecode"
        },
        "5": {
            "inputs": { "filename_prefix": "Test_5060", "images": ["4", 0] },
            "class_type": "SaveImage"
        },
        "1": {
            "inputs": { "ckpt_name": ckpt },
            "class_type": "CheckpointLoaderSimple"
        },
        "2": {
            "inputs": { "width": 512, "height": 512, "batch_size": 1 },
            "class_type": "EmptyLatentImage"
        },
        "6": {
            "inputs": { "text": "A futuristic city", "clip": ["1", 1] },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": { "text": "blurry, low quality", "clip": ["1", 1] },
            "class_type": "CLIPTextEncode"
        }
    }

    p = {"prompt": prompt, "client_id": str(uuid.uuid4())}
    print("Queueing...")
    res = requests.post(f"{HOST}/prompt", json=p)
    print(f"Queue Response: {res.text}")
    
    if res.status_code == 200:
        pid = res.json()['prompt_id']
        print(f"Tracking ID: {pid}")
        # Poll
        for _ in range(30):
            time.sleep(2)
            h = requests.get(f"{HOST}/history/{pid}").json()
            if pid in h:
                print("SUCCESS: Generation Complete!")
                return
        print("TIMEOUT awaiting generation.")

if __name__ == "__main__":
    test_gen()
