import os
import requests
import json

OPENHANDS_URL = os.getenv("OPENHANDS_URL", "http://openhands:3000")

def run_command(command: str) -> str:
    """
    Executes a command via the OpenHands Sandbox.
    
    Args:
        command (str): The shell command to execute.
        
    Returns:
        str: The output of the command or error message.
    """
    url = f"{OPENHANDS_URL}/api/chat"
    
    # Construct the payload mimicking a user request
    payload = {
        "messages": [
            {
                "role": "user",
                "content": f"Execute the following command in the sandbox and return ONLY the output:\n{command}"
            }
        ],
        "model": "qwen2.5-coder:14b", # Ensure this matches a valid model in OpenHands
        "temperature": 0
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Parse the 'content' from the assistant's reply
        # Note: Response structure depends on OpenHands API, assuming standard OpenAI-compat or similar
        if "choices" in result and len(result["choices"]) > 0:
             return result["choices"][0]["message"]["content"]
        elif "message" in result:
             return result["message"]
        else:
             return f"Unexpected response format: {json.dumps(result)}"
             
    except Exception as e:
        return f"Error executing command: {str(e)}"
