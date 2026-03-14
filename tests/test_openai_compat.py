import requests
import json
import time

BASE_URL = "http://localhost:8008"

def test_chat_completions_streaming():
    print("--- Testing /v1/chat/completions (Streaming, Standard Mode) ---")
    payload = {
        "model": "swarm-standard",
        "messages": [
            {"role": "user", "content": "My name is Justin."},
            {"role": "assistant", "content": "Hello Justin! How can I help you?"},
            {"role": "user", "content": "What is my name?"}
        ],
        "stream": True
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, stream=True)
    
    if response.status_code != 200:
        print(f"FAILED: Status {response.status_code}")
        print(response.text)
        return

    full_text = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                data_str = line_str[len("data: "):]
                if data_str == "[DONE]":
                    break
                
                try:
                    data = json.loads(data_str)
                    content = data["choices"][0]["delta"].get("content", "")
                    # print(f"Chunk: {repr(content)}")
                    full_text += content
                except Exception as e:
                    print(f"Error parsing chunk: {e}")

    print(f"Full Response: {full_text}")
    if "Justin" in full_text:
        print("SUCCESS: History recognized (Name found in response)")
    else:
        print("FAILED: History might be missing (Name not found)")
        
    if "> ⏳" in full_text or "> 🛠️" in full_text:
        print("FAILED: Internal logs detected in output (Standard Mode failure)")
    else:
        print("SUCCESS: Internal logs suppressed")

def test_chat_completions_non_streaming():
    print("\n--- Testing /v1/chat/completions (Non-Streaming, Standard Mode) ---")
    payload = {
        "model": "swarm-standard",
        "messages": [
            {"role": "user", "content": "Tell me a very short joke."}
        ],
        "stream": False
    }
    
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    
    if response.status_code != 200:
        print(f"FAILED: Status {response.status_code}")
        print(response.text)
        return
        
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    print(f"Response: {content}")
    
    if "> ⏳" in content or "> 🛠️" in content:
        print("FAILED: Internal logs detected in output")
    else:
        print("SUCCESS: Internal logs suppressed")

if __name__ == "__main__":
    try:
        test_chat_completions_streaming()
        test_chat_completions_non_streaming()
    except Exception as e:
        print(f"Test crashed: {e}")
