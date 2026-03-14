import subprocess
import tempfile
import os
import wave

def create_dummy_wav(filename, duration=1.0):
    with open(filename, 'wb') as f:
        with wave.open(f, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            wav_file.writeframes(b'\x00\x00' * int(44100 * duration))

def test_concat():
    f1 = "test1.wav"
    f2 = "test2.wav"
    out = "merged.wav"
    
    create_dummy_wav(f1)
    create_dummy_wav(f2)
    
    print(f"Concatenating {f1} and {f2} to {out}...")
    try:
        subprocess.run(["sox", f1, f2, out], check=True, capture_output=True)
        print("Success!")
        if os.path.exists(out):
             print(f"Output size: {os.path.getsize(out)}")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"Stderr: {e.stderr.decode()}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_concat()
