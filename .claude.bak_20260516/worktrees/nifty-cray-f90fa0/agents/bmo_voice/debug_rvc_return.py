
import os
import soundfile as sf
import torch
from rvc_python.infer import RVCInference
from rvc_python.modules.vc.modules import VC

# Setup dummy wav
os.system("ffmpeg -f lavfi -i \"sine=frequency=1000:duration=1\" test.wav -y > /dev/null 2>&1")

# Load Model
rvc = RVCInference(device="cuda")
rvc.load_model("models/bmo.pth")

# Access VC directly to test vc_single
print("Testing vc_single return type...")
try:
    wav_opt = rvc.vc.vc_single(
        sid=0,
        input_audio_path="test.wav",
        f0_up_key=0,
        f0_method="rmvpe",
        file_index="",
        index_rate=0,
        filter_radius=3,
        resample_sr=0,
        rms_mix_rate=0,
        protect=0.33,
        f0_file="",
        file_index2=""
    )
    with open("debug_output.txt", "w") as f:
        f.write(repr(wav_opt))
    print("Debug output written to debug_output.txt")
except Exception as e:
    print(f"Error: {e}")
