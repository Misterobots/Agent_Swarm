import requests
import os

def test_stt():
    url = "http://localhost:8020/stt"
    # Use absolute path based on script location
    audio_file = os.path.join(os.path.dirname(__file__), "test_audio.wav")
    
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} not found. Please ensure it exists.")
        return

    print(f"Sending {audio_file} to STT engine...")
    try:
        with open(audio_file, "rb") as f:
            files = {"audio_file": (audio_file, f, "audio/wav")}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS: STT Response Received")
            print(f"Transcription: '{result.get('text')}'")
        else:
            print(f"FAILED: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_stt()
