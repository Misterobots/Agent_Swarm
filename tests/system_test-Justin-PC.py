import sys
import os
import time

# Add root to path so we can import agents
# Add root to path so we can import agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Add agents dir to path for internal agent imports (e.g. church importing leibniz_agent)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../agents")))

from agents.registry import registry
from agents.dispatcher import detect_intent
from agents.security_agent import get_security_agent

def test_registry():
    print("--- Testing Agent Registry (MAESTRO L7) ---")
    agents = registry.list_agents()
    print(f"Loaded {len(agents)} agents.")
    
    architect = registry.get_card("Architect")
    if architect and architect.security_level == "L3_ADMIN":
        print("✅ Architect Identity Verified (L3_ADMIN)")
    else:
        print("❌ Architect Identity Mismatch")
        sys.exit(1)

    sec = registry.get_card("Security")
    if sec and "process.kill" in sec.capabilities:
        print("✅ Security Agent Capabilities Verified")
    else:
        print("❌ Security Agent Capabilities Missing")
        sys.exit(1)

def test_security_rbac():
    print("\n--- Testing RBAC (Role Based Access Control) ---")
    sec_agent = get_security_agent()
    
    # Architect should have file write access
    if sec_agent.validate_permission("Architect", "file_ops.write"):
        print("✅ Architect authorized for file_ops.write")
    else:
        print("❌ Architect denied valid permission")
        sys.exit(1)
        
    # Art Director should NOT have file write access
    if not sec_agent.validate_permission("Art Director", "file_ops.write"):
        print("✅ Art Director correctly blocked from file_ops.write")
    else:
        print("❌ Art Director INVALIDLY authorized for file_ops.write")
        sys.exit(1)

def test_intent_routing():
    print("\n--- Testing Intent Detection Logic ---")
    
    # Heuristic Checks (unit level)
    query_code = "write a python script"
    intent = detect_intent(query_code)
    if intent == "CODE":
         print(f"✅ Code Intent Detected for '{query_code}'")
    else:
         print(f"❌ Failed Code Intent: {intent}")
         
    query_img = "generate an image of a cat"
    intent = detect_intent(query_img)
    if intent == "IMAGE":
         print(f"✅ Image Intent Detected for '{query_img}'")
    else:
         print(f"❌ Failed Image Intent: {intent}")

if __name__ == "__main__":
    print("🚀 Starting System Smoke Test...\n")
    try:
        test_registry()
        test_security_rbac()
        test_intent_routing()
        print("\n✨ ALL SYSTEM TESTS PASSED")
    except Exception as e:
        print(f"\n🔥 TEST FAILURE: {e}")
        sys.exit(1)
