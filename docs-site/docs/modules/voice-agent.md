---
title: "Module: Voice Agent"
---

# Voice Agent

Text-to-speech, voice cloning, and BMO character interaction.

## Files

| File | Purpose |
|------|---------|
| `agents/specialized/voice_assistant.py` | Voice interaction handler |
| `agents/specialized/bmo_agent.py` | BMO character personality |

## Voice Stack

| Component | Port | Purpose |
|-----------|------|---------|
| Qwen3-TTS | 5050 | Primary text-to-speech |
| RVC | (internal) | Voice cloning/conversion |
| BMO Driver | 5060 | Character voice with personality |

## BMO Agent

BMO is a character-driven voice assistant inspired by Adventure Time's BMO:

- Personality: Cheerful, curious, slightly quirky
- Voice: Custom voice model via RVC
- Capabilities: All standard chat + voice output
- Hardware: Can run on satellite devices (ESP32-S3)

## Voice Synthesis Flow

1. Agent generates text response
2. Text sent to Qwen3-TTS for speech synthesis
3. Optionally processed through RVC for voice conversion
4. Audio returned as WAV/MP3

## Satellite Devices

BMO can run on IoT satellite devices:

| Device | Purpose |
|--------|---------|
| ESP32-S3 | Wake word detection, audio capture |
| Raspberry Pi | Local voice processing |

The satellite captures audio → sends to Agent Runtime → gets TTS response.

## Related

- [User Guide: Voice](../user-guide/voice.md) — user-facing guide
- [User Guide: IoT Control](../user-guide/iot-control.md) — device integration


