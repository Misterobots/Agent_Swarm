import requests
import time
import os

def test_voice_cloning():
    url = "http://localhost:8020/tts"
    
    # create a dummy wav file
    with open("dummy_ref.wav", "wb") as f:
        # minimal wav header + silence
        # This is just to have a valid file structure, content doesn't matter much for a quick smoke test 
        # but better to have something that looks like audio
        # writing 1 second of silence at 44.1kHz
        import wave
        with wave.open(f, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            wav_file.writeframes(b'\x00\x00' * 44100)

    files = {
        'reference_audio': open('dummy_ref.wav', 'rb')
    }
    data = {
        'text': 'This is a test of the voice cloning system.',
        'prompt_text': 'This is a reference prompt.'
    }

    try:
        print("Sending request to Voice Engine...")
        response = requests.post(url, data=data, files=files, timeout=120) # Long timeout for first run
        
        if response.status_code == 200:
            print("SUCCESS: Voice Engine returned 200 OK")
            with open("output_test.wav", "wb") as f:
                f.write(response.content)
            print("Saved output_test.wav")
        else:
            print(f"FAILURE: Voice Engine returned {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        files['reference_audio'].close()
        if os.path.exists("dummy_ref.wav"):
            os.remove("dummy_ref.wav")

if __name__ == "__main__":
    # Wait for service to be potentially ready
    # time.sleep(10)
    test_voice_cloning()
