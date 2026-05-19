
import os
import sys

print("-" * 30)
print(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH')}")
print("-" * 30)
print(f"sys.path: {sys.path}")
print("-" * 30)

user_nvidia = '/home/runner/.local/lib/python3.11/site-packages/nvidia'
system_nvidia = '/usr/local/lib/python3.11/site-packages/nvidia'

print(f"Checking User Path: {user_nvidia}")
exists_user = os.path.exists(user_nvidia)
print(f"Exists: {exists_user}")
if exists_user:
    try:
        cudnn_lib = os.path.join(user_nvidia, 'cudnn', 'lib')
        if os.path.exists(cudnn_lib):
            print(f"  Files in cudnn/lib: {os.listdir(cudnn_lib)}")
        else:
            print("  cudnn/lib directory not found in user path.")
    except Exception as e:
        print(f"  Error listing: {e}")

print("-" * 30)
print(f"Checking System Path: {system_nvidia}")
exists_system = os.path.exists(system_nvidia)
print(f"Exists: {exists_system}")
if exists_system:
    try:
        cudnn_lib = os.path.join(system_nvidia, 'cudnn', 'lib')
        if os.path.exists(cudnn_lib):
             # Just print first few to avoid truncation
             files = os.listdir(cudnn_lib)
             print(f"  Files in cudnn/lib (first 5): {files[:5]}")
        else:
            print("  cudnn/lib directory not found in system path.")
    except Exception as e:
        print(f"  Error listing: {e}")
