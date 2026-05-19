import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.router import chat_swarm

def test_librarian_streaming():
    print("🚀 Testing Librarian Streaming & Termination...")
    query = "Who was Marcus Aurelius?"
    
    has_message = False
    has_response = False
    
    print(f"Query: {query}")
    
    try:
        for update in chat_swarm(query):
            u_type = update.get("type")
            content = update.get("content", "")
            
            if u_type == "status":
                print(f"⏳ [STATUS] {content}")
            elif u_type == "message":
                has_message = True
                # Print just a few chars of message to show streaming
                if len(content) > 0:
                    sys.stdout.write(content[0])
                    sys.stdout.flush()
            elif u_type == "response":
                has_response = True
                print(f"\n✅ [RESPONSE RECEIVED] Length: {len(content)}")
            elif u_type == "log":
                print(f"📖 [LOG] {content}")

        if has_message and has_response:
            print("\n✨ SUCCESS: Librarian streamed tokens and yielded a final response.")
        else:
            print(f"\n❌ FAILURE: Missing events. has_message={has_message}, has_response={has_response}")
            sys.exit(1)

    except Exception as e:
        print(f"\n🔥 ERROR during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_librarian_streaming()
