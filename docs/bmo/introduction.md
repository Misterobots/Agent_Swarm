# BMO Voice Assistant — Introduction

BMO is a conversational voice assistant modeled after the beloved character from *Adventure Time*. It runs as a distributed system across a Raspberry Pi (voice satellite) and a GPU-equipped server (inference engine), providing natural voice interaction with smart home control, general knowledge, and Adventure Time personality.

## What BMO Can Do

- **Smart Home Control** — Turn lights on/off, check sensors, control fans and switches through Home Assistant integration.
- **General Conversation** — Chat about anything with a playful, childlike personality. BMO tells stories, plays word games, sings little songs, and shares opinions.
- **Weather, Time & News** — Fetch real-time information using dedicated tool integrations.
- **Conversation Memory** — Remembers facts about you across sessions (your name, preferences, past conversations) stored in PostgreSQL with 30-day rolling retention and permanent summaries.
- **Multi-Turn Dialogue** — Follows context across turns. If you say "turn on the bedroom light" then "make it dimmer", BMO understands the reference.
- **Voice Synthesis** — Speaks in a custom BMO voice using Kokoro TTS + RVC voice cloning, with 60+ pre-recorded sample phrases for instant responses.
- **Always-On Listening** — Wake word detection ("Hey BMO"), voice activity detection (Silero VAD), and barge-in support (interrupt BMO mid-sentence).

## System Architecture

```
┌────────────────────────────────────┐
│         Raspberry Pi (BMO)         │
│   ┌──────────────────────────┐     │
│   │   voice_satellite_v2.py  │     │
│   │  Wake Word · VAD · Audio │     │
│   └──────────┬───────────────┘     │
│   ┌──────────┴───────────────┐     │
│   │     pygame_face.py       │     │
│   │  HDMI Face Display (30fps)│    │
│   └──────────────────────────┘     │
└──────────────┬─────────────────────┘
               │ HTTP (LAN)
┌──────────────┴─────────────────────┐
│     Execution Node (Justin-PC)     │
│        RTX 5060 Ti — 16 GB        │
│                                    │
│  ┌─────────────┐  ┌────────────┐  │
│  │ agent-runtime│  │  bmo-voice │  │
│  │   :8008     │  │   :8100    │  │
│  │  LLM Agent  │  │ Kokoro+RVC │  │
│  │  HA Tools   │  │  Whisper   │  │
│  └──────┬──────┘  └────────────┘  │
│         │                          │
│  ┌──────┴──────┐                  │
│  │   Ollama    │                  │
│  │   :11434    │                  │
│  │ qwen3.5:9b  │                  │
│  └─────────────┘                  │
└────────────────────────────────────┘
               │
┌──────────────┴─────────────────────┐
│      Control Node (192.168.2.102)  │
│  PostgreSQL :5432 (memory)         │
│  Redis :6379 (GPU mutex)           │
│  Langfuse :3000 (observability)    │
└────────────────────────────────────┘
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `voice_satellite_v2.py` | Raspberry Pi | Wake word, VAD, audio I/O, state machine, barge-in |
| `pygame_face.py` | Raspberry Pi | Animated face display (23 expressions, smooth transitions) |
| `voice_assistant.py` | agent-runtime | Core LLM agent with tools, memory, dialogue tracking |
| `bmo_dialogue.py` | agent-runtime | Multi-turn state tracker with mood system |
| `bmo_memory.py` | agent-runtime | PostgreSQL-backed conversation and fact storage |
| `voice_cloning.py` | agent-runtime | TTS orchestration (samples → Fish Audio → RVC) |
| `server.py` | bmo-voice | GPU service: Kokoro TTS, RVC inference, Whisper STT |
| `voice_samples_map.py` | agent-runtime | 60+ pre-recorded BMO phrases for instant playback |

## Voice Pipeline (Per Utterance)

1. **Wake** — Satellite detects "Hey BMO" via OpenWakeWord, plays two-tone ping.
2. **Listen** — Silero VAD records speech, stops after 1.5s silence (15s max).
3. **Transcribe** — Audio posted to Whisper STT on the GPU server.
4. **Think** — Agent runtime builds context (time, mood, memory, conversation history), sends to qwen3.5:9b with tool calling.
5. **Speak** — Response text checked against sample map; if no match, sent to Kokoro TTS → RVC for BMO voice cloning.
6. **Play** — WAV streamed back to Pi, played through HDMI. Barge-in monitor runs in parallel.

## Mood System

BMO has an emotional state that influences its tone and face expression:

| Mood | Trigger | Face |
|------|---------|------|
| Happy | Positive words (thanks, awesome, great) | `happy` — squinted eyes, big smile |
| Curious | Questions (what, why, how, tell me) | `look_up` — eyes tracking upward |
| Playful | Fun words (game, play, joke, adventure) | `excited` — wide eyes, huge smile |
| Concerned | Negative words or repeated errors | `sad` — droopy eyes, downturned mouth |
| Sleepy | Low intensity decay over time | `sleepy` — eyes closed |

Mood decays toward neutral `happy` over time. The mood hint is injected into the LLM context so BMO's word choice matches its emotional state.

## Network Topology

| Node | IP | Role |
|------|----|------|
| Home Assistant | 192.168.2.100 | Smart home hub |
| Justin-PC | 192.168.2.101 | GPU inference (Ollama, TTS, STT) |
| Control Node | 192.168.2.102 | PostgreSQL, Redis, Langfuse |
| R730 Gateway | 192.168.2.103 | Traefik reverse proxy, secondary inference |

The Raspberry Pi connects directly to the execution node over the LAN. All inter-service communication within the execution node uses Docker networking.
