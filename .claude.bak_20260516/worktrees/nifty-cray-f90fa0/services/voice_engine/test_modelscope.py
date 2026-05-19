import sys
try:
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks
    print("Imported modelscope pipeline")
    
    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    print(f"Loading pipeline for {model_id}...")
    
    tts_pipeline = pipeline(task=Tasks.text_to_speech, model=model_id)
    print("Pipeline loaded successfully!")
    
except Exception as e:
    print(f"Error loading pipeline: {e}")
    sys.exit(1)
