
import sys
import os
import shutil

# Add agents directory to path to import specialized modules
sys.path.append("/app/agents")

try:
    from specialized.image_gen import generate_image
except ImportError:
    # If running locally (not in container), adjust path
    sys.path.append(os.path.join(os.getcwd(), "agents"))
    from specialized.image_gen import generate_image

# Prompt for the background
PROMPT = "Abstract Technology Background, Blue and Purple, High Tech, Circuitry, Neural Network, 4k, smooth gradient, dark theme, cybernetic, masterpiece"

print(f"--- Starting Local Generation: '{PROMPT}' ---")

# Run generation
# Force FLUX_SCHNELL if available for speed, or let auto-detect
result = generate_image(prompt=PROMPT, steps=4, width=1920, height=1080)

print(f"--- Result: {result} ---")

if "Generated Image:" in result:
    # Extract filename
    # Format: "Generated Image: filename.png (in subfolder output) | Verified..."
    import re
    match = re.search(r"Generated Image: ([\w\.-]+)", result)
    if match:
        filename = match.group(1)
        print(f"SUCCESS: Created {filename}")
        
        # In Docker, the file is in /app/comfy_io/output (mapped volume)
        # OR /app/agents/delivered_artifacts
        
        # We want to ensure it's available to the host docs/assets
        # The 'generate_image' function copies it to 'delivered_artifacts' in workspace root.
        # So we should find it there.
    else:
        print("FAILED to parse filename.")
        sys.exit(1)
else:
    print("GENERATION FAILED.")
    sys.exit(1)
