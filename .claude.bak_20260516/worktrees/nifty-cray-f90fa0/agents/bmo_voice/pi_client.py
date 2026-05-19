import argparse
import requests
import sys
import os
import time

# Optional Audio Libraries (Only needed for Voice-to-Voice)
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: Audio Libs Missing ({e})")
    AUDIO_AVAILABLE = False

# Configuration
SAMPLE_RATE = 44100
CHANNELS = 1
DEFAULT_DURATION = 5  # Seconds

def record_audio(duration):
    if not AUDIO_AVAILABLE:
        print("Error: Audio libraries not installed. Run: pip install sounddevice soundfile numpy")
        return None
    
    print(f"🎤 Recording for {duration} seconds... (Speak like BMO!)", end="", flush=True)
    audio_data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS)
    sd.wait()
    print(" Done.")
    
    # Save to temp file
    filename = "temp_input.wav"
    sf.write(filename, audio_data, SAMPLE_RATE)
    return filename

def play_audio(filename, device=None):
    if not AUDIO_AVAILABLE:
        print(f"Audio saved to {filename} (Playback unavailable)")
        return

    print(f"🔊 Playing response...")
    data, fs = sf.read(filename, dtype='int16')
    
    # Fix for HDMI: Ensure Stereo (2 channels)
    if data.ndim == 1:
        data = np.column_stack((data, data))
        
    sd.play(data, fs, device=device)
    sd.wait()

def main():
    parser = argparse.ArgumentParser(description="BMO Voice Client (Pi Edition)")
    parser.add_argument("--host", required=False, help="IP Address of the Hive Server (e.g., 192.168.1.X or Tailscale IP)")
    parser.add_argument("--port", default="8100", help="Port of the BMO Service (Default: 8100)")
    parser.add_argument("--text", help="Text-to-Speech Mode: Text to speak")
    parser.add_argument("--record", action="store_true", help="Voice-to-Voice Mode: Record microphone")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Recording duration in seconds")
    parser.add_argument("--pitch", type=int, default=3, help="Pitch shift in semitones (Default: 3 for BMO)")
    parser.add_argument("--method", default="rmvpe", help="RVC Method (Default: rmvpe)")
    parser.add_argument("--device", type=int, default=None, help="Output Device ID (Run --list-devices to see available)")
    parser.add_argument("--list-devices", action="store_true", help="List available audio devices and exit")
    
    args = parser.parse_args()

    # List Devices Mode
    if args.list_devices:
        if AUDIO_AVAILABLE:
            print(sd.query_devices())
        else:
            print("Audio libraries not installed.")
        return

    if not args.host:
        print("❌ Error: --host argument is required (unless using --list-devices)")
        sys.exit(1)
    
    url = f"http://{args.host}:{args.port}/speak"
    
    files = None
    params = {
        "pitch": args.pitch,
        "method": args.method
    }
    
    # Mode Selection
    if args.text:
        print(f"🤖 Mode: Text-to-Speech")
        print(f"📄 Input: '{args.text}'")
        params = {"text": args.text}
        
    elif args.record:
        print(f"🎭 Mode: Voice-to-Voice (Puppeteer)")
        if not AUDIO_AVAILABLE:
            print("❌ Error: Missing audio libraries. Please install: pip install sounddevice soundfile numpy")
            return
            
        wav_file = record_audio(args.duration)
        if not wav_file:
            return
            
        print(f"📤 Uploading audio to Hive...")
        files = {'file': open(wav_file, 'rb')}
        
    else:
        print("❌ Error: Please specify either --text or --record")
        return

    # Send Request
    try:
        start_time = time.time()
        response = requests.post(url, params=params, files=files)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            print(f"✅ Success! (Latency: {latency:.2f}s)")
            
            # Save Output
            output_filename = "bmo_response.wav"
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            
            # Play Output
            if AUDIO_AVAILABLE:
                play_audio(output_filename, device=args.device)
            else:
                print(f"💾 Audio saved to {output_filename}")
                
        else:
            print(f"❌ Server Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        
    finally:
        # Cleanup temp file
        if args.record and files:
            files['file'].close()
            if os.path.exists("temp_input.wav"):
                os.remove("temp_input.wav")

if __name__ == "__main__":
    main()
