
# Hardware Diagnostic Script
import os
import sys
import numpy as np
import sounddevice as sd

def test_hardware():
    print("Testing Audio Hardware...")
    try:
        devices = sd.query_devices()
        print(f"Found {len(devices)} devices")
        for i, d in enumerate(devices):
            print(f"Device {i}: {d['name']}")
            
        print("\nAttempting playback on default device...")
        fs = 48000
        duration = 1.0  # seconds
        frequency = 440.0  # Hz
        t = np.linspace(0, duration, int(fs * duration), False)
        # Generate varied waveform to test potential frequency response issues
        audio = (np.sin(2 * np.pi * frequency * t) * 0.5 + 
                np.sin(2 * np.pi * (frequency * 1.5) * t) * 0.3).astype(np.float32)
        
        sd.play(audio, fs)
        sd.wait()
        print("Playback attempt complete")
        
    except Exception as e:
        print(f"Hardware test failed: {e}")

if __name__ == "__main__":
    test_hardware()
