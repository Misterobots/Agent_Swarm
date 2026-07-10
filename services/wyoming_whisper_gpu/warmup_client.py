"""Sends one throwaway transcription to the local server to force the one-time CUDA
kernel compilation/caching cost (measured live: ~8s cold vs ~0.2-0.4s warm) to happen at
container startup instead of on the first real voice command. Audio content doesn't
matter for this purpose — CUDA kernel selection depends on tensor shapes, not on what's
actually said, so a synthesized tone (baked in at build time, see Dockerfile) works
exactly as well as real speech and needs no other service to be reachable at startup.
"""
import asyncio
import wave

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

WARMUP_WAV = "/app/warmup.wav"
HOST = "localhost"
PORT = 10300


async def main():
    with wave.open(WARMUP_WAV, "rb") as wav_file:
        rate = wav_file.getframerate()
        width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        audio_data = wav_file.readframes(wav_file.getnframes())

    async with AsyncTcpClient(HOST, PORT) as client:
        await client.write_event(Transcribe(language="en").event())
        await client.write_event(AudioStart(rate=rate, width=width, channels=channels).event())
        chunk_size = 4096
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await client.write_event(
                AudioChunk(rate=rate, width=width, channels=channels, audio=chunk).event()
            )
        await client.write_event(AudioStop().event())
        while True:
            event = await client.read_event()
            if event is None or Transcript.is_type(event.type):
                break


asyncio.run(main())
