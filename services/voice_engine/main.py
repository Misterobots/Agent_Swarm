
import os
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
try:
    from modelscope import AutoTokenizer
    # Qwen3-TTS architecture is not recognized by Transformers AutoModel yet
    # We load the implementation class directly from the installed qwen-tts library
    from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel as AutoModel
    print("--- Using Native Qwen3TTSModel ---")
except ImportError:
    from transformers import AutoModel, AutoTokenizer
    print("--- Using Transformers API (Fallback) ---")
from transformers.generation import GenerationConfig
import soundfile as sf
import tempfile
import io
import subprocess
from funasr import AutoModel as FunASRModel # For STT (Renamed to avoid collision with Qwen3TTSModel)

# Initialize FastAPI
app = FastAPI(title="Qwen3-TTS Voice Engine")

# Configuration
MODEL_PATH = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"  # Base model supports zero-shot cloning
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PORT = int(os.getenv("PORT", 8020))

print(f"--- [Voice Engine] Starting on {DEVICE} ---")

# Audio Effects (Sox)
EFFECTS = {
    "Old Radio": ["highpass", "500", "lowpass", "2000", "overdrive", "10"],
    "Telephony": ["highpass", "400", "lowpass", "3400"],
    "Cave": ["reverb", "50", "50", "100"],
    "Cathedral": ["reverb", "80", "80", "100"],
    "Small Room": ["reverb", "20", "20", "100"],
    "Chipmunk": ["pitch", "300"],
    "Deep Voice": ["pitch", "-300"],
    "Robot": ["overdrive", "10", "echo", "0.8", "0.8", "5", "0.7"],
    "Alien": ["flanger"],
    "Ethereal": ["reverb", "50", "50", "100", "reverse", "reverb", "50", "50", "100", "reverse"],
    "Overdrive": ["overdrive", "20"],
    "Megaphone": ["overdrive", "20", "highpass", "1000", "lowpass", "3000"],
    "Underwater": ["lowpass", "400"],
    "Walkie Talkie": ["overdrive", "15", "highpass", "500", "lowpass", "2500"],
    "Phaser": ["phaser", "0.8", "0.74", "3", "0.4", "0.5"],
    "Tremolo": ["tremolo", "6", "40"],
    "BMO": ["highpass", "200", "lowpass", "3000", "overdrive", "3", "pitch", "100", "speed", "1.1"] 
}

# Global Model Variables
model = None
tokenizer = None
stt_model = None

def load_model():
    global model, tokenizer, stt_model

    # Load TTS model independently so a failure doesn't block STT
    try:
        print(f"Loading TTS Model: {MODEL_PATH}...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32
        )
        print("TTS Model Loaded Successfully.")
    except Exception as e:
        print(f"WARNING: TTS Model failed to load: {e}")
        model = None
        tokenizer = None

    # Load STT model independently so a TTS failure doesn't prevent transcription
    try:
        print("Loading STT Model: iic/SenseVoiceSmall...")
        stt_device = "cuda" if torch.cuda.is_available() else "cpu"
        stt_model = FunASRModel(
            model="iic/SenseVoiceSmall",
            trust_remote_code=True,
            device=stt_device,
        )
        print("STT Model Loaded Successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: STT Model failed to load: {e}")
        stt_model = None
        # We don't crash app so we can see logs, but inference will fail
        pass

@app.on_event("startup")
async def startup_event():
    load_model()

@app.post("/tts")
async def text_to_speech(
    text: str = Form(...),
    reference_audio: list[UploadFile] = File(None),
    prompt_text: str = Form(None),
    effect: str = Form(None)
):
    """
    Generate speech from text, optionally cloning a voice from reference_audio files.
    """
    global model, tokenizer
    
    if not model:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    temp_files = []
    try:
        # 1. Process Reference Audio(s)
        ref_audio_paths = []
        if reference_audio:
            for audio_file in reference_audio:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    content = await audio_file.read()
                    tmp.write(content)
                    tmp.flush()
                    ref_audio_paths.append(tmp.name)
                    temp_files.append(tmp.name)
        
        # Concatenate multiple reference audios into one if needed
        final_ref_audio_path = None
        if ref_audio_paths:
            if len(ref_audio_paths) > 1:
                # Use sox to concatenate
                merged_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                merged_tmp.close()
                temp_files.append(merged_tmp.name)
                
                import subprocess
                # sox file1.wav file2.wav ... output.wav
                try:
                    subprocess.run(["sox"] + ref_audio_paths + [merged_tmp.name], check=True)
                    final_ref_audio_path = merged_tmp.name
                except Exception as e:
                    print(f"Error concatenating audio with sox: {e}")
                    # Fallback to first file
                    final_ref_audio_path = ref_audio_paths[0]
            else:
                final_ref_audio_path = ref_audio_paths[0]

        # 2. Determine Cloning Mode
        # If prompt_text is provided, we use ICL mode (higher quality usually)
        # If not, we use x_vector_only_mode (purely acoustic cloning)
        x_vector_only = True
        if prompt_text:
            x_vector_only = False
            
        print(f"Generating TTS for: '{text}' | Ref: {final_ref_audio_path} | Mode: {'X-Vector' if x_vector_only else 'ICL'}")


        
        # 3. Generate Audio
        # Qwen3-TTS generate_voice_clone returns list of numpy arrays (batched), we take the first one
        # We pass a single text and a single (concatenated) reference audio path in a list of size 1
        output_audios, sample_rate = model.generate_voice_clone(
            text=[text],
            ref_audio=[final_ref_audio_path] if final_ref_audio_path else None,
            ref_text=[prompt_text] if prompt_text else None,
            x_vector_only_mode=x_vector_only,
            do_sample=True,
            top_p=0.8,
            temperature=0.8
        )
        
        if not output_audios:
             raise HTTPException(status_code=500, detail="Generation failed (empty output)")
             
        audio_data = output_audios[0]

        # 4. Post-Processing & Conversion
        raw_output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        temp_files.append(raw_output_path)
        sf.write(raw_output_path, audio_data, sample_rate)
        
        final_output_path = raw_output_path
        
        if effect and effect in EFFECTS:
            print(f"Applying Effect: {effect}")
            effect_output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            temp_files.append(effect_output_path)
            
            # Construct command: sox input.wav output.wav <effect_args>
            cmd = ["sox", raw_output_path, effect_output_path] + EFFECTS[effect]
            try:
                subprocess.run(cmd, check=True)
                final_output_path = effect_output_path
            except Exception as e:
                print(f"Effect application failed: {e}")
                # Fallback to raw output if effect fails
        
        with open(final_output_path, "rb") as f:
            wav_content = f.read()
            
        return Response(content=wav_content, media_type="audio/wav")

    except Exception as e:
        print(f"Inference Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp files
                    pass

@app.post("/stt")
async def speech_to_text(
    audio_file: UploadFile = File(...)
):
    """
    Transcribe speech to text using SenseVoiceSmall.
    """
    global stt_model
    if stt_model is None:
        return Response(content="STT Model not loaded", status_code=500)
        
    temp_path = ""
    try:
        # Save upload to temp file
        suffix = os.path.splitext(audio_file.filename)[1]
        if not suffix:
            suffix = ".wav" # Default
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio_file.read())
            temp_path = tmp.name
            
        print(f"--- [STT] Processing: {temp_path} ---")
        
        # Inference
        # SenseVoiceSmall returns a list of results
        res = stt_model.generate(
            input=temp_path,
            cache={},
            language="auto",  # or "zn", "en", "yue", "ja", "ko"
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        
        # Result format check needed, usually res[0]['text']
        print(f"STT Result Raw: {res}")
        text = ""
        if isinstance(res, list) and len(res) > 0:
            text = res[0].get("text", "")
        
        return {"text": text}

    except Exception as e:
        print(f"STT Error: {e}")
        return Response(content=f"Error: {str(e)}", status_code=500)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
