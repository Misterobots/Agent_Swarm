import sounddevice as sd
import numpy as np
import time

def test_mic(duration=3, samplerate=16000):
    print("\n--- Audio Device Diagnostic ---")
    print(sd.query_devices())
    print(f"\nDefault Input Device: {sd.default.device[0]}")
    
    print(f"\nTesting recording for {duration} seconds at {samplerate}Hz...")
    try:
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()
        
        # Calculate max volume to see if it captured anything
        max_amplitude = np.max(np.abs(recording))
        mean_amplitude = np.mean(np.abs(recording))
        
        print("\n--- Recording Results ---")
        print(f"Max Volume (Amplitude): {max_amplitude} (out of 32767)")
        print(f"Average Volume: {mean_amplitude:.2f}")
        
        if max_amplitude == 0:
            print("❌ WARNING: Complete silence detected. The microphone is either muted, disconnected, or the wrong device is selected.")
        elif max_amplitude < 500:
            print("⚠️ WARNING: Audio was captured, but it is extremely quiet. Make sure the microphone is close or turn up your system input volume.")
        else:
            print("✅ SUCCESS: Audio successfully captured at a healthy volume!")
            
    except Exception as e:
        print(f"\n❌ ERROR during recording: {e}")

if __name__ == "__main__":
    test_mic()
