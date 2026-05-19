
import torch
import os
import sys
import traceback

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

try:
    print(f"Torch Version: {torch.__version__}")
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"Torch Path: {os.path.dirname(torch.__file__)}")
    print(f"CuDNN Version: {torch.backends.cudnn.version()}")
except Exception:
    traceback.print_exc()

print(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH')}")

try:
    import nvidia.cudnn
    print(f"Nvidia CuDNN Package detected at: {os.path.dirname(nvidia.cudnn.__file__)}")
    print(f"Nvidia CuDNN Version: {nvidia.cudnn.__version__ if hasattr(nvidia.cudnn, '__version__') else 'Unknown'}")
except ImportError:
    print("Nvidia CuDNN Package NOT installed via pip.")
except Exception:
    traceback.print_exc()

# Check for libcudnn in torch lib
try:
    torch_lib_path = os.path.join(os.path.dirname(torch.__file__), 'lib')
    print(f"Checking {torch_lib_path} for libcudnn:")
    if os.path.exists(torch_lib_path):
        files = [f for f in os.listdir(torch_lib_path) if 'cudnn' in f]
        print(files)
    else:
        print(f"Path {torch_lib_path} does not exist.")
except Exception as e:
    print(f"Error checking torch lib: {e}")
