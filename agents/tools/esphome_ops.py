
import subprocess
import os
import logging

def esphome_compile(config_path: str) -> str:
    """
    Compiles an ESPHome YAML configuration file into firmware.
    
    Args:
        config_path (str): Absolute path to the .yaml config file.
        
    Returns:
        str: specific output of the compilation process or error.
    """
    if not os.path.exists(config_path):
        return f"Error: Config file not found at {config_path}"
        
    try:
        # Assuming esphome is installed in the path (or in the venv)
        # We run 'esphome compile config.yaml'
        result = subprocess.run(
            ["esphome", "compile", config_path],
            capture_output=True,
            text=True,
            timeout=300 # 5 minute timeout for compilation
        )
        
        if result.returncode == 0:
            return "Compilation Successful. Firmware binary is ready."
        else:
            return f"Compilation Failed:\n{result.stderr}"
            
    except Exception as e:
        return f"Execution Error: {str(e)}"

def esphome_upload(config_path: str, device: str) -> str:
    """
    Uploads firmware to a specific device/address.
    """
    try:
        result = subprocess.run(
            ["esphome", "upload", config_path, "--device", device],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return "Upload Successful."
        else:
            return f"Upload Failed:\n{result.stderr}"
    except Exception as e:
        return f"Execution Error: {str(e)}"
