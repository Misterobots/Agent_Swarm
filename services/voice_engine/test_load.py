import torch
from modelscope import AutoTokenizer
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel

MODEL_PATH = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

print(f"Testing load of {MODEL_PATH}...")
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    print("Tokenizer loaded.")
    model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="auto", trust_remote_code=True)
    print("Model loaded.")
except Exception as e:
    print(f"Error: {e}")
