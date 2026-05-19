
import sys
import os

# Add agents directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "agents")))

from agents.router import chat_swarm

def test_streaming():
    query = "Who was Marcus Aurelius?"
    print(f"Testing stream for: {query}")
    
    has_message = False
    has_response = False
    has_status = False
    
    try:
        for update in chat_swarm(query):
            u_type = update.get("type")
            content = update.get("content")
            
            if u_type == "status":
                has_status = True
                print(f"📡 [STATUS] {content}")
            elif u_type == "message":
                has_message = True
                print(".", end="", flush=True)
            elif u_type == "log":
                print(f"\n📖 [LOG] {content}")
            elif u_type == "response":
                has_response = True
                print(f"\n✅ [RESPONSE RECEIVED] Length: {len(content)}")
                break # We should break here according to ui.py change
                
        if has_message and has_response:
            print("\n✨ SUCCESS: Stream worked correctly and yielded final response.")
        else:
            print(f"\n❌ FAILURE: Missing events. has_message={has_message}, has_response={has_response}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n🔥 CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_streaming()
