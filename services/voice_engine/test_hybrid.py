import traceback
import sys

try:
    print("Importing modelscope snapshot_download...")
    from modelscope.hub.snapshot_download import snapshot_download
    print("Importing transformers...")
    from transformers import AutoModel, AutoTokenizer

    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    print(f"Downloading model {model_id}...")
    model_dir = snapshot_download(model_id)
    print(f"Model downloaded to {model_dir}")

    print("Loading Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    
    print("Loading Model...")
    model = AutoModel.from_pretrained(model_dir, trust_remote_code=True)
    print("Model Loaded Successfully!")
    
except Exception:
    traceback.print_exc()
    sys.exit(1)
