import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.tools.home_assistant import HomeAssistantTool

def test_ha_connection():
    print("--- Verifying Home Assistant Connection ---")
    
    # Check Env Vars (Mocking loading since we are outside container for this test script, 
    # but in real usage inside container they are set)
    # For this local test to work, we need to set them manually or load from .env if we were running locally.
    # However, since we are running this inside the container context (hopefully), it should work.
    # Wait, running `python tests/verify_ha.py` from host won't have the container env vars.
    # We should run this script INSIDE the agent_runtime container.
    
    try:
        ha = HomeAssistantTool()
        print(f"URL: {ha.base_url}")
        # print(f"Token: {ha.token[:10]}...") 

        # Try to get state of a common entity
        state = ha.get_state("sun.sun")
        
        if "error" in state:
            print(f"FAILED: {state['error']}")
        else:
            print("SUCCESS: Connected to Home Assistant")
            print(f"Entity: sun.sun")
            print(f"State: {state.get('state')}")
            print(f"Attributes: {state.get('attributes')}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_ha_connection()
