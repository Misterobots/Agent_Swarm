---
title: Voice
---

# Voice

Interact with BMO — a physical robot character with cloned voice synthesis — and use text-to-speech generation.

## How to Access

- **UI**: Navigate to **Voice** workspace in the Hive Mind sidebar
- **API**: `POST /v1/voice/chat` for voice-specific interactions
- **Physical**: BMO satellite device with microphone input

## Quick Example

> *"Hey BMO, tell me a joke"*

The system:

1. Processes your text (or transcribed speech)
2. Generates a response through the standard agent pipeline
3. Synthesizes audio using the BMO voice profile via RVC
4. Returns both text and audio

## Detailed Usage

### Voice Synthesis Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **TTS** | Qwen3-TTS (1.7B) | Text-to-speech synthesis |
| **RVC** | Retrieval-based Voice Conversion | Voice cloning / character voice |
| **BMO Driver** | Custom | Character-specific voice mapping |

### Voice API

```bash
curl -X POST http://{{ gateway_node_ip }}/swarm/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Tell me about space"}]}'
```

Response includes both text and an audio file path:

```json
{
  "text": "Space is really cool! There are billions of stars...",
  "audio_path": "/voice_samples/response_001.wav"
}
```

### Voice Samples

Pre-recorded BMO voice samples are available at:

```
http://{{ execution_node_ip }}:{{ agent_runtime_port }}/voice_samples/{filename}
```

### Satellite Devices

Raspberry Pi voice satellites can connect to the system. See `scripts/voice_satellite.py` for the satellite client implementation.

## Tips & Common Patterns

!!! tip "Natural Phrasing"
    BMO responds best to conversational language. It maintains the BMO character personality in responses.

!!! warning "GPU Usage"
    Voice synthesis (especially RVC) requires GPU resources. If Ollama is handling a large inference, voice may queue.

## Related

- [Module: BMO Voice](../modules/voice-agent.md) — RVC synthesis service
- [Module: Voice Engine](../modules/voice-agent.md) — Qwen3-TTS service
- [Tutorial: Voice Interaction](../tutorials/voice-assistant.md) — guided walkthrough
- [Troubleshooting: Voice](../troubleshooting/voice.md)
