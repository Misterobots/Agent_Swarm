
import sys
import logging

# Antigravity Patch to disable xformers in diffusers library
# This is necessary because the system-installed xformers is incompatible with PyTorch Nightly
# and cannot be easily removed. This patch forces diffusers to ignore it.

try:
    import diffusers.utils.import_utils
    
    # 1. Force is_xformers_available to always return False
    diffusers.utils.import_utils.is_xformers_available = lambda: False
    
    # 2. Force the internal cached variable to False (if it exists)
    if hasattr(diffusers.utils.import_utils, "_xformers_available"):
        diffusers.utils.import_utils._xformers_available = False
        
    logging.warning("\033[93m[Antigravity Patch] Successfully disabled xformers in diffusers library via 00_Antigravity_Patch.\033[0m")
    
except ImportError:
    logging.warning("[Antigravity Patch] diffusers library not found, skipping patch.")
except Exception as e:
    logging.error(f"[Antigravity Patch] Failed to apply patch: {e}")

# ComfyUI requires these to be defined
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
