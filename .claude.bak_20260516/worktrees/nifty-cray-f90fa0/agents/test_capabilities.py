from church import run_swarm
import time

if __name__ == "__main__":
    print("--- [Test] Triggering Agent Capability Verification ---")
    prompt = "Create a file named 'hello_swarm.py' that prints 'Hello from the Agentic Swarm!'.Then, execute that file and return the output."
    
    run_swarm(prompt)
    
    print("--- [Test] Verification Request Sent. Check Mission Control for live logs. ---")
