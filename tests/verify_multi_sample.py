import requests
import time
import os
import wave

def create_dummy_wav(filename, duration=1.0):
    with open(filename, 'wb') as f:
        with wave.open(f, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            wav_file.writeframes(b'\x00\x00' * int(44100 * duration))

def test_multi_sample_cloning():
    url = "http://localhost:8020/tts"
    
    # Create 3 dummy wavs
    refs = ["ref1.wav", "ref2.wav", "ref3.wav"]
    files = []
    
    try:
        for i, ref in enumerate(refs):
            create_dummy_wav(ref)
            f = open(ref, "rb")
            # Requests format for multiple files with same key: ('key', (filename, file_obj, content_type))
            files.append(('reference_audio', (ref, f, 'audio/wav')))

        data = {
            'text': 'This is a test with multiple reference audios.',
            'prompt_text': 'This is a reference prompt.'
        }

        print(f"Sending request with {len(files)} reference files...")
        response = requests.post(url, data=data, files=files, timeout=120)
        
        if response.status_code == 200:
            print("SUCCESS: Voice Engine returned 200 OK")
            with open("output_multi.wav", "wb") as f:
                f.write(response.content)
            print("Saved output_multi.wav")
        else:
            print(f"FAILURE: Voice Engine returned {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        for _, (name, f, _) in files:
            f.close()
        for ref in refs:
            if os.path.exists(ref):
                os.remove(ref)

if __name__ == "__main__":
    test_multi_sample_cloning()
