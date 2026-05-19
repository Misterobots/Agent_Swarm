from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Response
from fastapi.responses import FileResponse # Keep for backward compat if needed, though we use Response now
from rvc_python.infer import RVCInference
import os
import soundfile as sf
import soundfile as sf
import torch
from faster_whisper import WhisperModel

# Monkey Patch torch.load to fix "weights_only=True" breaking RVC/Fairseq
# This is required for PyTorch 2.6+ / Nightly with older models
original_load = torch.load
def safe_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return original_load(*args, **kwargs)
torch.load = safe_load

import soundfile as sf


# Configure Espeak for Kokoro/Phonemizer
# We point directly to the system-installed espeak-ng to avoid 'espeakng-loader' issues
import os
os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"
os.environ["PHONEMIZER_ESPEAK_PATH"] = "/usr/bin/espeak-ng"

# Monkey patch for Kokoro/Misaki compatibility with newer phonemizer
# This must happen BEFORE importing kokoro
try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_data_path = lambda x: None
except ImportError:
    pass

from kokoro import KPipeline

app = FastAPI()

# Initialize Kokoro TTS (CPU fallback handled automatically or by torch)
# 'a' is for American English
try:
    print("Loading Kokoro TTS...")
    # Verify CUDA availability for Kokoro
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline = KPipeline(lang_code='a', device=device, repo_id='hexgrad/Kokoro-82M')
    print(f"Kokoro TTS Loaded on {device}.")
except Exception as e:
    print(f"ERROR Loading Kokoro TTS: {e}")
    pipeline = None

# Initialize RVC Inference
# Models should be mounted to /app/models
MODEL_PATH = "models/bmo.pth"
INDEX_PATH = "models/bmo.index"

# Check if models exist, otherwise warn (soft failure for container startup)
if not os.path.exists(MODEL_PATH) or not os.path.exists(INDEX_PATH):
    print(f"WARNING: Model files not found at {MODEL_PATH} or {INDEX_PATH}")
    rvc = None
else:
    print("Loading RVC Model...")
    try:
        rvc = RVCInference(device="cuda")
        rvc.load_model(MODEL_PATH)
        # rvc.set_index(INDEX_PATH) # If index loading is separate, otherwise check API
        print("RVC Model Loaded Successfully.")
    except Exception as e:
        print(f"ERROR Loading RVC Model: {e}")
        rvc = None

# Initialize Whisper STT
try:
    print("Loading Whisper STT...")
    # usage: device="cuda" for GPU, "cpu" for CPU
    stt_device = "cuda" if torch.cuda.is_available() else "cpu"
    # medium.en is robust. small.en is faster.
    stt_model = WhisperModel("medium.en", device=stt_device, compute_type="float16" if stt_device=="cuda" else "int8")
    print(f"Whisper STT Loaded on {stt_device}.")
except Exception as e:
    print(f"ERROR Loading Whisper STT: {e}")
    stt_model = None

@app.post("/speak")
async def speak(background_tasks: BackgroundTasks, text: str = None, file: UploadFile = File(None), pitch: int = 0, speed: float = 1.0, method: str = "rmvpe"):
    if text is None and file is None:
         raise HTTPException(status_code=400, detail="Either 'text' or 'file' must be provided.")

    temp_input_wav = "temp_input.wav"
    output_wav = "output.wav"

    def cleanup_files():
        if os.path.exists(temp_input_wav):
            os.remove(temp_input_wav)
        if os.path.exists(output_wav):
            os.remove(output_wav)

    try:
        # 1. Handle Input (Text -> WAV or Audio File -> WAV)
        if text:
            print(f"Generating Kokoro TTS for: {text} (speed={speed})")
            if pipeline is None:
                raise HTTPException(status_code=503, detail="Kokoro TTS failed to load.")
            
            # Generate Audio
            # voice='af_bella' is higher pitched and less breathy than 'af_heart', better for BMO.
            generator = pipeline(text, voice='af_bella', speed=speed)
            
            # Combine all segments
            all_audio = []
            for i, (gs, ps, audio) in enumerate(generator):
                all_audio.append(audio)
            
            if not all_audio:
                 raise HTTPException(status_code=500, detail="Kokoro generated no audio.")
                 
            full_audio = torch.cat(all_audio, dim=0) if len(all_audio) > 0 else all_audio[0]
            
            # Save to WAV
            # Kokoro usually outputs at 24000Hz
            sf.write(temp_input_wav, full_audio.cpu().numpy(), 24000)

        else:
            print("Processing uploaded audio file...")
            with open(temp_input_wav, "wb") as f:
                f.write(await file.read())


        # 2. Run RVC Inference (If available)
        if rvc:
            print(f"Running RVC Inference on {temp_input_wav} -> {output_wav} with pitch={pitch}, method={method}...")
            if not os.path.exists(temp_input_wav):
                print(f"CRITICAL ERROR: Input file {temp_input_wav} does not exist!")
                raise HTTPException(status_code=500, detail="Intermediate audio file creation failed.")
                
            try:
                # rvc-python infer_file signature: input_path, output_path. Params set via set_params.
                # Tuning for BMO:
                # index_rate=0.75: heavily favour the BMO training data (accent/timbre) over the input
                # filter_radius=3: median filtering to reduce artifacts
                # protect=0.33: protect voiceless consonants from artifacts
                rvc.set_params(f0up_key=pitch, f0method=method, index_rate=0.75, filter_radius=3, protect=0.33)
                rvc.infer_file(temp_input_wav, output_wav)
            except Exception as rvc_error:
                print(f"RVC Inference Failed: {rvc_error}")
                raise HTTPException(status_code=500, detail=f"RVC Logic Failed: {rvc_error}")

            if not os.path.exists(output_wav):
                print(f"CRITICAL ERROR: Output file {output_wav} was not created by RVC!")
                raise HTTPException(status_code=500, detail="RVC failed to create output file.")
                
            final_output = output_wav
            print("RVC Success.")
        else:
            print("WARNING: RVC Model not loaded. Returning raw TTS/Input audio.")
            final_output = temp_input_wav

        # 3. Return Result
        # Read file to memory to avoid race conditions with cleanup
        with open(final_output, "rb") as f:
            audio_data = f.read()
        
        # Cleanup files immediately
        cleanup_files()
        
        print(f"Returning {len(audio_data)} bytes of audio.")
        return Response(content=audio_data, media_type="audio/wav")

    except HTTPException as he:
        cleanup_files()
        raise he
    except Exception as e:
        cleanup_files()
        print(f"UNHANDLED EXCEPTION: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")


@app.post("/listen")
async def listen(file: UploadFile = File(...)):
    """Transcribe uploaded audio file to text."""
    if not stt_model:
        raise HTTPException(status_code=503, detail="STT Model not loaded.")
    
    temp_filename = "temp_stt.wav"
    
    try:
        # Save uploaded file
        with open(temp_filename, "wb") as f:
            f.write(await file.read())
            
        # Transcribe
        segments, info = stt_model.transcribe(temp_filename, beam_size=5)
        text = " ".join([segment.text for segment in segments]).strip()
        
        print(f"STT Transcript: '{text}' (prob: {info.language_probability:.2f})")
        return {"text": text}
        
    except Exception as e:
        print(f"STT Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except: 
                pass
