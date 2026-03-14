import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.router import chat_swarm

def test_mars_streaming():
    print("🚀 Testing MarsRL (CODE) Streaming & Termination...")
    query = "Write a fast Fibonacci function in Python."
    
    has_message = False
    has_response = False
    has_status = False
    
    print(f"Query: {query}")
    
    try:
        # We only need a few updates to verify it's working
        counter = 0
        for update in chat_swarm(query):
            u_type = update.get("type")
            content = update.get("content", "")
            
            if u_type == "status":
                has_status = True
                print(f"⏳ [STATUS] {content}")
            elif u_type == "message":
                has_message = True
                sys.stdout.write(".")
                sys.stdout.flush()
            elif u_type == "response":
                has_response = True
                print(f"\n✅ [RESPONSE RECEIVED] Length: {len(content)}")
                break # We got what we needed
            elif u_type == "log":
                print(f"📖 [LOG] {content}")
            
            counter += 1
            if counter > 500: # Safety break
                print("\n⚠️ Test took too many steps, breaking.")
                break

        if has_message and has_response and has_status:
            print("\n✨ SUCCESS: MarsRL streamed tokens and yielded a final response.")
        else:
            print(f"\n❌ FAILURE: Missing events. has_message={has_message}, has_response={has_response}, has_status={has_status}")
            sys.exit(1)

    except Exception as e:
        print(f"\n🔥 ERROR during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_mars_streaming()
