from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import os
import sys

# Add tools to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from agents.tools.iot_ops import get_states, call_service
from agents.tools.mqtt_ops import mqtt_publish, mqtt_subscribe
from agents.tools.esphome_ops import esphome_compile, esphome_upload
from agents.tools.wokwi_ops import create_simulation, add_part, connect_wires

def get_iot_agent() -> Agent:
    """
    Returns the configured IoT Controller Agent.
    """
    MODEL_NAME = "qwen2.5-coder:14b"
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # System Instructions for the Expanded IoT Agent
    INSTRUCTIONS = """
    YOUR GOAL is to interpret user requests to control the physical environment OR develop new IoT devices.
    
    ### PROTOCOLS:
    
    1. **HOME AUTOMATION (Existing Devices)**:
       - Use `get_states()` and `call_service()` via Home Assistant.
       - "Turn on the kitchen lights" -> `call_service("light", "turn_on", ...)`
       
    2. **FIRMWARE DEVELOPMENT (New Devices)**:
       - **SIMULATE FIRST**: If asked to "Create a blinking LED", ALWAYS use Wokwi first.
         - `create_simulation("blink_v1")`
         - `add_part(...)` to build the circuit.
         - Tell the user: "I created the simulation. Please verify in VS Code."
       - **TEST**: Use `mqtt_publish` to test local message handling if needed.
       - **DEPLOY**: Only use `esphome_compile` or `upload` if explicitly requested to "Flash" or "Deploy".
       
    3. **DIRECT MQTT**:
       - Use `mqtt_publish` if the user specifies a raw topic like "cmnd/tasmota/POWER".

    ### SAFETY GUARDRAILS:
    - NEVER upload firmware without simulating first unless overridden.
    - NEVER control locks/alarms without confirmation.
    """

    return Agent(
        name="IoT Controller",
        model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
        description="You are the Home Automation Specialist. You control lights, switches, and scenes via Home Assistant, and develop firmware via Wokwi/ESPHome.",
        instructions=INSTRUCTIONS,
        tools=[get_states, call_service, mqtt_publish, mqtt_subscribe, esphome_compile, esphome_upload, create_simulation, add_part, connect_wires],
        show_tool_calls=True,
        markdown=True
    )

if __name__ == "__main__":
    # Test Run
    agent = get_iot_agent()
    agent.print_response("Turn on the studio lights")
