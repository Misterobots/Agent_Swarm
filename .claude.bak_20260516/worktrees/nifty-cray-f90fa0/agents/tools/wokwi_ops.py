
import json
import os

# Resolve path relative to this tool file (agents/tools/wokwi_ops.py -> workspace/simulations)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
SIMULATION_DIR = os.path.join(ROOT_DIR, "workspace", "simulations")

def create_simulation(project_name: str, board_type: str = "board-esp32-devkit-c-v4") -> str:
    """
    Initializes a new Wokwi project folder with a default diagram.json.
    
    Args:
        project_name (str): Name of the simulation (e.g., "blinky_v1")
        board_type (str): Wokwi board ID (default: esp32)
        
    Returns:
        str: Success message with path.
    """
    project_path = os.path.join(SIMULATION_DIR, project_name)
    os.makedirs(project_path, exist_ok=True)
    
    diagram = {
        "version": 1,
        "author": "IoT Agent",
        "editor": "wokwi",
        "parts": [
            { "type": board_type, "id": "esp", "top": 0, "left": 0, "attrs": {} }
        ],
        "connections": []
    }
    
    with open(os.path.join(project_path, "diagram.json"), 'w') as f:
        json.dump(diagram, f, indent=2)
        
    return f"Simulation created at {project_path}. Add files (main.cpp) to run."

def add_part(project_name: str, part_type: str, part_id: str, x: int, y: int, color: str = "") -> str:
    """
    Adds a part to the simulation diagram.
    """
    path = os.path.join(SIMULATION_DIR, project_name, "diagram.json")
    if not os.path.exists(path):
        return "Error: Project does not exist."
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    attrs = {}
    if color: attrs["color"] = color
    
    data["parts"].append({
        "type": part_type,
        "id": part_id,
        "top": y,
        "left": x,
        "attrs": attrs
    })
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        
    return f"Added {part_type} ({part_id}) to {project_name}"

def connect_wires(project_name: str, connections: list) -> str:
    """
    Adds wire connections.
    Connections format: [ ["source", "target", "color", []], ... ]
    Example: [ ["esp:D2", "led1:A", "green", []] ]
    """
    path = os.path.join(SIMULATION_DIR, project_name, "diagram.json")
    if not os.path.exists(path): return "Error: Project missing"
    
    with open(path, 'r') as f: data = json.load(f)
    
    for conn in connections:
        data["connections"].append(conn)
        
    with open(path, 'w') as f: json.dump(data, f, indent=2)
    
    return "Wires connected."
