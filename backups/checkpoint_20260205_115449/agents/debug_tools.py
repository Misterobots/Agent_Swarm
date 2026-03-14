from architect_agent import get_architect_agent
from tools.file_ops import write_file

if __name__ == "__main__":
    print("--- [Debug] Checking Tool Registration ---")
    agent = get_architect_agent()
    print(f"Agent Name: {agent.name}")
    print(f"Tools Registered: {[t.__name__ for t in agent.tools]}")
    
    print("\n--- [Debug] Testing write_file directly ---")
    result = write_file("debug_direct.txt", "This is a direct write test.")
    print(f"write_file result: {result}")
