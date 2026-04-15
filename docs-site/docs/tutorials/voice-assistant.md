---
title: "Tutorial: Voice Assistant"
---

# Build a Voice Assistant

Set up voice input and output to talk to Agent Swarm.

## What You'll Learn

- How to enable voice input (STT)
- How to enable voice output (TTS)
- How voice integrates with the agent pipeline

## Prerequisites

- A microphone connected to the device running the browser
- Voice services enabled on the Execution Node

## Step 1: Verify Voice Services

```bash
# Check Whisper (STT) is running
curl http://{{ execution_node_ip }}:9000/health

# Check Piper (TTS) is running
curl http://{{ execution_node_ip }}:5500/health
```

## Step 2: Enable Voice in the UI

In the Hive UI (`http://{{ gateway_node_ip }}/`):

1. Click the **microphone icon** in the chat input area
2. Grant browser microphone permission when prompted
3. Speak your message

The audio is sent to Whisper for transcription, then processed as text.

## Step 3: Enable Voice Output

Agent responses can be spoken aloud:

1. Open **Settings** in the UI
2. Enable **Text-to-Speech**
3. Select a voice (Piper offers multiple voices)

Responses will be both displayed as text and played as audio.

## Step 4: Try a Conversation

Speak naturally:

> "What's the weather like?"
> "Turn on the living room lights"
> "Tell me a joke"

The system handles the full loop: speech → text → agent → text → speech.

## Step 5: Adjust Voice Settings

| Setting | Effect |
|---------|--------|
| Voice model | Changes the speaker voice |
| Speed | Adjusts speech rate |
| Auto-listen | Automatically starts listening after TTS finishes |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Microphone not detected | Check browser permissions |
| Poor transcription | Reduce background noise, speak clearly |
| No audio output | Check browser audio permissions and volume |

## Next Steps

- [User Guide: Voice](../user-guide/voice.md) — full voice reference
- [Create IoT Automation](iot-automation.md) — combine voice with smart home
