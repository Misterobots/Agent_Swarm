# BMO Voice Assistant — Development Guide

## Repository Structure

```
Home_AI_Lab/
├── agents/
│   ├── main.py                          # FastAPI app — voice endpoints
│   ├── specialized/
│   │   ├── voice_assistant.py           # Core BMO agent (LLM + tools + memory)
│   │   ├── bmo_dialogue.py              # Dialogue state tracker + mood system
│   │   ├── bmo_memory.py                # SQLAlchemy models for conversation memory
│   │   ├── voice_cloning.py             # TTS orchestration (samples → Fish Audio → RVC)
│   │   └── voice_samples_map.py         # Pre-recorded phrase → file mapping
│   ├── bmo_voice/
│   │   ├── server.py                    # FastAPI GPU service (Kokoro + RVC + Whisper)
│   │   ├── pygame_face.py               # Animated face renderer
│   │   ├── Dockerfile                   # CUDA 12.4 base image
│   │   ├── requirements.txt             # Python dependencies
│   │   ├── models/                      # RVC model files (bmo.pth, bmo.index)
│   │   └── voice_samples/               # Pre-recorded WAV files
│   ├── tools/
│   │   ├── home_assistant.py            # HA REST API wrapper
│   │   └── assistant_tools.py           # WeatherTool, TimeTool, NewsTool
│   └── utils/
│       └── gpu_queue.py                 # Redis GPU mutex with VRAM zone management
├── scripts/
│   └── voice_satellite_v2.py            # Raspberry Pi voice pipeline
├── execution_plane/
│   ├── docker-compose.yml               # Service definitions
│   └── Dockerfile                       # agent-runtime image
└── network.env                          # Network topology (IPs, credentials)
```

## Environment Variables

### agent-runtime (voice_assistant.py, voice_cloning.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `BMO_LLM_MODEL` | `qwen3.5:9b` | Ollama model for conversation |
| `BMO_ENGINE_URL` | `http://bmo_voice_gpu:8000/speak` | RVC voice synthesis endpoint |
| `VOICE_ENGINE_HOST` | `http://voice_engine_gpu:8020` | Generic Kokoro TTS host |
| `FISH_AUDIO_API_KEY` | (empty) | Fish Audio cloud TTS (optional fallback) |
| `FISH_AUDIO_MODEL_ID` | `323847d4c5394c678e5909c2206725f6` | Fish Audio BMO model |
| `AGNO_DB_URL` | (required) | PostgreSQL connection string for memory |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama inference endpoint |
| `REDIS_HOST` | `redis_queue` | Redis for GPU mutex |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | (optional) | Redis auth |
| `HOME_ASSISTANT_URL` | `http://192.168.2.100:8123` | HA API |
| `HOME_ASSISTANT_TOKEN` | (required) | HA long-lived access token |
| `HOME_LAT` / `HOME_LON` | `41.8781` / `-87.6298` | Weather location |

### voice_satellite_v2.py (Raspberry Pi)

Reads from `network.env`:
| Variable | Description |
|----------|-------------|
| `EXECUTION_NODE_IP` or `JUSTIN_PC_IP` | Server IP for API calls |

Hardcoded constants in the script:
| Constant | Value | Description |
|----------|-------|-------------|
| `SAMPLE_RATE` | 16000 | Wake word detection rate |
| `HW_RATE` | 48000 | Hardware mic sample rate |
| `CHUNK_SIZE` | 1280 | 80ms audio chunks |
| `WAKE_THRESHOLD` | 0.5 | Wake word confidence |
| `VAD_SILENCE_TIMEOUT` | 1.5s | Silence before stop recording |
| `VAD_MAX_DURATION` | 15.0s | Max recording length |
| `VAD_MIN_SPEECH` | 0.3s | Minimum valid speech |
| `CONVERSATION_TIMEOUT` | 30.0s | Idle before requiring wake word |
| `SESSION_INACTIVITY` | 300.0s | Idle before session end |

## API Endpoints

### agent-runtime (:8008)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/voice/chat` | Send text, receive `{text, audio_path, session_id, expression}` |
| POST | `/v1/voice/stream` | Streaming TTS — splits into sentences, yields WAV chunks |
| POST | `/v1/voice/new_session` | Create a new BMO session |
| POST | `/v1/voice/end_session` | End session (triggers summary + fact extraction) |
| GET | `/voice_samples/{filename}` | Serve pre-recorded WAV files |

### bmo-voice (:8100)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/speak?text=...&pitch=0&speed=1.0` | Text → Kokoro TTS → RVC → WAV |
| POST | `/speak/stream?text=...` | Sentence-pipelined streaming TTS |
| POST | `/listen` | Upload audio file → Whisper STT → text |

## Key Classes and Functions

### VoiceAssistantAgent (voice_assistant.py)

```python
class VoiceAssistantAgent:
    def __init__(self, user_id: str = "default")
    def process(self, message: Message) -> Message      # Main pipeline
    def end_session(self) -> None                        # Finalize + summarize
```

The `process()` pipeline:
1. Check `voice_samples_map` for instant sample match
2. Run `DialogueTracker.resolve_context()` for follow-up resolution
3. Check `DialogueTracker.should_clarify()` for ambiguous input
4. Build enriched context (time + mood + memory + conversation)
5. Send to phi Agent (Ollama with tool calling)
6. Update dialogue state and mood
7. Persist turn to database, trigger periodic summarization
8. Check response for embedded sample phrases
9. Generate voice via `clone_voice(text, effect="BMO")`
10. Return `Message` with `audio_path` and `expression` in metadata

### DialogueTracker (bmo_dialogue.py)

```python
class DialogueTracker:
    def classify_topic(self, text: str) -> str           # Regex topic classification
    def detect_followup(self, user_text: str) -> bool    # Pronoun/device heuristics
    def resolve_context(self, user_text: str) -> str     # Inject state hints
    def should_clarify(self, user_text: str) -> bool     # Ambiguity detection
    def update(self, user_text, assistant_text) -> None   # Post-turn state update
    def get_mood_hint(self) -> str                        # LLM mood context hint
    def get_face_expression(self) -> str                  # Mood → expression name
```

Mood transitions are driven by regex pattern matching on user input:
- Positive words → happy (intensity +0.2)
- Playful words → playful (0.7)
- Questions → curious (0.6)
- Negative words → concerned (0.5)
- Consecutive errors → concerned (scales with count)
- No signals → decay toward neutral happy (-0.1 per turn)

### Memory Functions (bmo_memory.py)

```python
save_message(session_id, role, content, user_id)
get_recent_messages(session_id, limit=16) -> List[Dict]
save_session_summary(session_id, summary, turn_count, user_id)
get_recent_summaries(user_id, limit=3) -> List[str]
get_user_profile(user_id) -> List[str]
update_user_profile(user_id, new_facts: List[str])
cleanup_old_messages(days=30) -> int
```

Tables auto-create via `Base.metadata.create_all()` on first import. The 30-day retention applies only to `BmoConversation`; summaries and profiles are permanent.

### Voice Generation (voice_cloning.py)

```python
clone_voice(text, reference_audio_path=None, prompt_text=None, effect=None) -> str
```

TTS chain for `effect="BMO"`:
1. **Sample check** — exact match in `voice_samples_map` → instant return
2. **Fish Audio API** — if `FISH_AUDIO_API_KEY` is set, try cloud TTS
3. **Local RVC** — Kokoro-82M → RVC (bmo.pth + bmo.index) with GPU lock
4. **GPU lock** — `request_lock("voice", timeout=30)` from `gpu_queue.py`
5. **Fail-open** — if `gpu_queue` unavailable, run without lock

Output is resampled to 44100 Hz, 16-bit PCM mono for HDMI playback.

### GPU Queue (gpu_queue.py)

```python
@contextmanager
request_lock(context: str, timeout: int = 300)
```

Three VRAM zones: `"text"` (Ollama), `"image"` (ComfyUI), `"voice"` (TTS/RVC).

Zone switches trigger selective eviction:
- → text: evict ComfyUI
- → image: evict Ollama
- → voice: evict ComfyUI (keep Ollama for LLM)

Fail-open: if Redis is unreachable, the lock is skipped.

## Adding New Features

### Adding a New Tool

1. Create the tool class in `agents/tools/`:
```python
from phi.tools import Toolkit

class MyTool(Toolkit):
    def __init__(self):
        super().__init__(name="my_tool")
        self.register(self.my_function)

    def my_function(self, param: str) -> str:
        """Docstring becomes the tool description for the LLM."""
        return "result"
```

2. Add it to `VoiceAssistantAgent.__init__()` in `voice_assistant.py`:
```python
self.my_tool = MyTool()
self.llm_agent = Agent(
    model=Ollama(id=BMO_MODEL),
    tools=[self.smart_home, self.weather, self.time_tool, self.news, self.my_tool],
    ...
)
```

3. Update the system prompt to tell BMO when to use the tool.

### Adding New Voice Samples

1. Place the WAV file in `agents/bmo_voice/voice_samples/`.
2. Add the mapping in `voice_samples_map.py`:
```python
VOICE_SAMPLES_MAP = {
    ...
    "your trigger phrase": "YourFile.wav",
}
```

The phrase is normalized (lowercase, punctuation stripped) before matching.

### Adding New Face Expressions

In `pygame_face.py`, add to the expressions dictionary:

```python
"my_expression": {
    "leftEye": {"x": -0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
    "rightEye": {"x": 0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
    "mouth": {"y": 0.15, "width": 0.05, "curve": 0.2, "openness": 0.0, "style": "arc", "offsetX": 0.0},
    "bounce": 0.0,
}
```

Then map it in `bmo_dialogue.py`:
```python
def get_face_expression(self) -> str:
    mood_to_expression = {
        ...
        "my_mood": "my_expression",
    }
```

### Adding New Dialogue Topics

In `bmo_dialogue.py`, add a regex pattern to `_TOPIC_KEYWORDS`:

```python
_TOPIC_KEYWORDS = {
    ...
    "music": re.compile(r'\b(music|song|play|spotify|album|artist)\b', re.IGNORECASE),
}
```

Then update `_build_conversation_context()` in `voice_assistant.py` if the topic needs full context window.

## Building and Deploying

### Build the Docker Images

```bash
cd ~/Home_AI_Lab/execution_plane

# Build agent-runtime
docker compose build agent-runtime

# Build bmo-voice (GPU, takes longer)
docker compose build bmo-voice
```

### RVC Model Files

The BMO voice model must be mounted at `/app/models/` inside the bmo-voice container:
- `bmo.pth` — RVC model weights
- `bmo.index` — FAISS index for voice similarity

These are not in the repository. Train with RVC or obtain from the project's model storage.

### Database Setup

The PostgreSQL database auto-creates tables on first connection. Ensure `AGNO_DB_URL` points to a running PostgreSQL instance with the `agno_memory` database:

```bash
# On the control node
psql -U agno -d agno_memory -c "SELECT COUNT(*) FROM bmo_conversations;"
```

### Testing Locally (Without Pi)

You can test the agent without the voice satellite:

```bash
# Direct chat
curl -X POST http://localhost:8008/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hey BMO, tell me a joke"}'

# Streaming TTS
curl -X POST http://localhost:8008/v1/voice/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Hey BMO, what time is it?"}' \
  --output response.wav
```

## Code Style Notes

- **No markdown in BMO responses.** The system prompt forbids it. TTS breaks on asterisks, bullets, and emojis.
- **Fail-open everywhere.** Memory, GPU queue, and Fish Audio all degrade gracefully. BMO should always respond, even if degraded.
- **Concise responses.** BMO is designed for voice — 1-2 sentences max. The system prompt enforces this.
- **Tool calling is selective.** BMO only uses tools when factual information is needed. Casual conversation never triggers tools.
