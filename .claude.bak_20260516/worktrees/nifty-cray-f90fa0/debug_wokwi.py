
import sys
import os
sys.path.append(os.getcwd())
from agents.tools.wokwi_ops import create_simulation

print("Testing Wokwi Tool...")
try:
    res = create_simulation("debug_test_1")
    print(res)
    
    # Check if it exists where we think it should
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname("agents/tools/wokwi_ops.py"), "../../")) # Manual path logic to match tool
    expected_path = os.path.join(os.getcwd(), "workspace", "simulations", "debug_test_1")
    
    if os.path.exists(expected_path):
        print(f"SUCCESS: Folder found at {expected_path}")
    else:
        print(f"FAILURE: Folder not found at {expected_path}")
        
except Exception as e:
    print(f"ERROR: {e}")
