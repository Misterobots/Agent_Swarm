# BMO Voice Assistant — Usage Guide

## Starting BMO

### 1. Start the GPU Services (Execution Node)

SSH into Justin-PC (192.168.2.101) and bring up the Docker stack:

```bash
cd ~/Home_AI_Lab/execution_plane
docker compose up -d agent-runtime bmo-voice ollama
```

Verify services are healthy:

```bash
# Agent runtime
curl http://localhost:8008/health

# BMO voice engine (Kokoro + RVC + Whisper)
curl http://localhost:8100/health

# Ollama with qwen3.5:9b loaded
curl http://localhost:11434/api/tags
```

### 2. Start the Voice Satellite (Raspberry Pi)

SSH into the BMO Pi and run:

```bash
cd ~/Home_AI_Lab/scripts
python3 voice_satellite_v2.py
```

The satellite will:
- Auto-detect the USB microphone (Plantronics/Blackwire preferred)
- Auto-detect the HDMI audio output device
- Load the OpenWakeWord model (`hey_beeMo.onnx`)
- Load Silero VAD for speech detection
- Start the pygame face renderer on HDMI
- Enter IDLE state, displaying the neutral face

### 3. Verify Connectivity

The satellite reads network configuration from `network.env`. It connects to:

| Endpoint | URL | Purpose |
|----------|-----|---------|
| STT | `http://{EXECUTION_NODE_IP}:8020/stt` | Speech-to-text (Whisper) |
| Chat | `http://{EXECUTION_NODE_IP}:8008/v1/voice/chat` | Send text, get response + audio |
| Stream | `http://{EXECUTION_NODE_IP}:8008/v1/voice/stream` | Streaming TTS pipeline |
| Session | `http://{EXECUTION_NODE_IP}:8008/v1/voice/new_session` | Session lifecycle |

## Talking to BMO

### Wake Word

Say **"Hey BMO"** clearly. You'll hear a two-tone ping (1047 Hz + 1319 Hz) confirming BMO is listening. The face changes to the `acknowledged` expression, then transitions to `listening`.

### Speaking

Speak naturally after the ping. BMO records until:
- 1.5 seconds of silence (end of utterance)
- 15 seconds maximum (hard cap)
- Less than 0.3 seconds of speech is discarded as noise

### Conversation Flow

BMO supports continuous conversation. After responding, if BMO's answer ends with a question or open-ended statement, the satellite stays in LISTENING mode — no need to say the wake word again.

A session times out after:
- **30 seconds** of no speech — returns to IDLE (wake word required)
- **5 minutes** of total inactivity — session is finalized and summarized

### Barge-In (Interrupting BMO)

If BMO is talking and you want to interrupt, just start speaking. The barge-in monitor detects 240ms of continuous speech and:
1. Kills the audio playback immediately
2. Switches to LISTENING mode
3. Records your new utterance

## What You Can Say

### Smart Home Control

```
"Hey BMO, turn on the bedroom light"
"Make it dimmer"                          ← follow-up, BMO resolves context
"What about the kitchen?"                 ← room follow-up
"Turn off all the lights"
"What's the temperature in the garage?"
"Is the front door locked?"
"List my devices"
```

BMO uses Home Assistant tool calling. Entity IDs are resolved from natural language (e.g., "bedroom light" → `light.bedroom`).

### Weather

```
"Hey BMO, what's the weather like?"
"Will it rain tomorrow?"
"Is it going to be cold this weekend?"
```

### Time and Date

```
"Hey BMO, what time is it?"
"What day is it?"
```

### News

```
"Hey BMO, what's in the news?"
"Tell me the headlines"
```

### Casual Conversation

```
"Hey BMO"                                ← BMO greets you naturally
"Tell me a joke"
"Tell me a story about Finn and Jake"
"Let's play twenty questions"
"Sing me a song"
"What's your favorite sport?"            ← "Football!"
"I'm bored"
"Good night, BMO"                        ← BMO may suggest a bedtime story
```

### Memory-Aware Interactions

BMO remembers facts about you across sessions:

```
"My name is Justin"                      ← stored as a user fact
(next session)
"Hey BMO"                                ← "Hey Justin!" (recalls naturally)
"I got a new cat named Mochi"
(later)
"How's Mochi?"                           ← BMO remembers the cat
```

BMO never announces that it's recalling memories — it just uses them naturally.

## Pre-Recorded Samples

BMO has 60+ pre-recorded voice samples that play instantly (zero latency) when triggered. These include:

| Category | Examples |
|----------|----------|
| Greetings | "hello", "hi", "hey" |
| Emotions | "yay", "ouch", "whoa", "hahaha" |
| Games | "who wants to play video games", "total domination" |
| Reactions | "hmm", "interesting", "well" |
| Time of day | "good morning", "good night", "sweet dreams" |

The sample check happens before TTS generation, so common phrases are instant.

## Session Management

### Automatic Sessions

Sessions are created automatically on the first utterance after a wake word. Each session:
- Gets a unique session ID
- Maintains conversation context (16-turn window for active topics, 8 for chitchat)
- Summarizes every 10 user turns
- Extracts personal facts for long-term memory

### Manual Session Control (API)

```bash
# Create a new session
curl -X POST http://192.168.2.101:8008/v1/voice/new_session

# End the current session (triggers summary + fact extraction)
curl -X POST http://192.168.2.101:8008/v1/voice/end_session

# Chat directly (bypassing the satellite)
curl -X POST http://192.168.2.101:8008/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hey BMO, what time is it?"}'
```

## BMO's Face

The pygame face renderer displays BMO's emotional state on HDMI:

| Expression | When |
|------------|------|
| `neutral` | Idle, waiting |
| `acknowledged` | Wake word detected (brief bounce) |
| `listening` | Recording speech (subtle eye tracking) |
| `thinking` | Processing with LLM (one eye half-closed) |
| `happy` | Positive interaction (squinted eyes, smile) |
| `excited` | Playful mood (wide eyes, open mouth) |
| `sad` | Concerned mood (droopy eyes) |
| `sleeping` | Late at night or low activity |
| `error` | Something went wrong (zigzag mouth) |

Expressions transition smoothly over 0.5 seconds with lerp interpolation. Random blinks occur every 3-7 seconds. Eyes drift in idle cycles.
