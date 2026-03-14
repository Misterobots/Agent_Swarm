import sounddevice as sd
import numpy as np

def run_advanced_test():
    print("--- Advanced USB Audio Diagnostic ---")
    
    # Target device is 2 (Logitech G933)
    target_device = 2
    
    # Common USB audio quirk configurations
    test_configs = [
        {"samplerate": 48000, "channels": 1, "dtype": 'int16'},
        {"samplerate": 48000, "channels": 2, "dtype": 'int16'},
        {"samplerate": 44100, "channels": 1, "dtype": 'int16'},
        {"samplerate": 44100, "channels": 2, "dtype": 'int16'},
        {"samplerate": 48000, "channels": 1, "dtype": 'float32'},
    ]
    
    success = False
    
    for config in test_configs:
        print(f"\nTesting Config: {config}")
        try:
            recording = sd.rec(
                int(2 * config['samplerate']), 
                samplerate=config['samplerate'], 
                channels=config['channels'], 
                dtype=config['dtype'],
                device=target_device
            )
            sd.wait()
            
            max_amp = np.max(np.abs(recording))
            avg_amp = np.mean(np.abs(recording))
            print(f"  Max: {max_amp}, Avg: {avg_amp:.4f}")
            
            if max_amp > 0:
                print(f"  ✅ SUCCESS! Data received with this configuration.")
                success = True
                break
            else:
                print("  ❌ Flatline (0 data received).")
                
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            
    if not success:
        print("\n❌ All configurations failed to capture data from the hardware.")
        print("\nPotential Root Causes for Raspberry Pi USB Audio Silence:")
        print("1. Hidden 'Capture Switch': Run 'amixer -c 2 scontrols' to look for unlisted mute toggles.")
        print("2. USB Power Delivery: The Pi might not be providing enough current to fully power the ADC in the G933 dongle. Try a powered USB hub.")

if __name__ == "__main__":
    run_advanced_test()
