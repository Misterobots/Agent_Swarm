import requests
import os

def test_effect():
    url = "http://localhost:8020/tts"
    
    # Simple x-vector mode
    data = {
        "text": "This is a test of the BMO effect. Who wants to play video games?",
        "effect": "BMO",
        "prompt_text": "Safe to ignore"
    }
    
    # Creating a small dummy wav (3 seconds of white noise)
    import wave
    import random
    import struct
    
    duration = 3
    sample_rate = 16000
    num_samples = duration * sample_rate
    
    with wave.open("dummy_ref.wav", "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        # Generate random noise
        # 32767 is max amplitude for 16-bit audio
        noise_data = b''.join(struct.pack('h', int(random.uniform(-10000, 10000))) for _ in range(num_samples))
        wav_file.writeframes(noise_data)

    files = [
        ('reference_audio', ('dummy_ref.wav', open('dummy_ref.wav', 'rb'), 'audio/wav'))
    ]
    
    print(f"Sending request with effect: {data['effect']}...")
    try:
        response = requests.post(url, data=data, files=files)
        
        if response.status_code == 200:
            with open("output_effect.wav", "wb") as f:
                f.write(response.content)
            print("SUCCESS: Voice Engine returned 200 OK")
            print(f"Saved output_effect.wav (Size: {len(response.content)} bytes)")
        else:
            print(f"FAILED: {response.text}")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if os.path.exists("dummy_ref.wav"):
            os.remove("dummy_ref.wav")

if __name__ == "__main__":
    test_effect()
