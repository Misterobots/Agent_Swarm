---
title: "Troubleshooting: Voice"
---

# Voice Troubleshooting

## Speech-to-Text (STT) Not Working

**Symptom**: Microphone records but no transcription appears.

**Diagnose**:

```bash
# Check Whisper service
curl http://{{ lovelace_ip }}:9000/health
docker logs whisper --tail 30
```

**Fix**:

1. Restart Whisper: `docker compose restart whisper`
2. Check that the Whisper model is loaded
3. Verify audio format compatibility (16kHz WAV preferred)

---

## Text-to-Speech (TTS) Not Working

**Symptom**: No audio plays after responses.

**Diagnose**:

```bash
# Check Piper service
curl http://{{ lovelace_ip }}:5500/health
docker logs piper --tail 30
```

**Fix**:

1. Check browser audio permissions
2. Verify Piper voice model is installed
3. Restart Piper: `docker compose restart piper`

---

## Poor Transcription Quality

**Symptom**: Whisper transcribes words incorrectly.

**Fix**:

1. Reduce background noise
2. Speak clearly and at normal pace
3. Use a better microphone
4. Try a larger Whisper model (e.g., `medium` instead of `base`)

---

## Audio Latency

**Symptom**: Long delay between speaking and transcription.

**Fix**:

1. Use a smaller Whisper model for faster processing
2. Check CPU/GPU load during transcription
3. Reduce audio chunk size for faster streaming

---

## Browser Microphone Issues

**Symptom**: "Microphone not found" or permission denied.

**Fix**:

1. Check browser settings → Site Settings → Microphone
2. Ensure the page is served over HTTPS (or localhost)
3. Try a different browser
4. Check OS audio input settings


