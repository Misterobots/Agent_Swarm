
import sys
import logging

print("\033[93m[Antigravity Patch] INITIALIZING PATCH NODE...\033[0m")

try:
    import diffusers.utils.import_utils
    
    # 1. Force is_xformers_available to always return False
    diffusers.utils.import_utils.is_xformers_available = lambda: False
    
    # 2. Force the internal cached variable to False (if it exists)
    if hasattr(diffusers.utils.import_utils, "_xformers_available"):
        diffusers.utils.import_utils._xformers_available = False
        
    msg = "\033[93m[Antigravity Patch] Successfully disabled xformers in diffusers library via AAA_Antigravity_Patch.\033[0m"
    print(msg)
    logging.warning(msg)
    
except ImportError:
    print("[Antigravity Patch] diffusers library not found, skipping patch.")
except Exception as e:
    print(f"[Antigravity Patch] Failed to apply patch: {e}")

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
