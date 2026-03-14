import requests
import sys

URL = "http://127.0.0.1:8000/v1/voice/chat"

def test_voice_endpoint():
    print(f"Testing {URL}...")
    
    payload = {"text": "What is the temperature?"}
    
    try:
        response = requests.post(URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Endpoint responded.")
            print(f"Text: {data.get('text')}")
            print(f"Audio Path: {data.get('audio_path')}")
            
            if data.get("text") and data.get("audio_path"):
                print("✅ PASSED: Both text and audio path returned.")
            else:
                print("❌ FAILED: Missing text or audio path.")
        else:
            print(f"FAILED: Status {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_voice_endpoint()
