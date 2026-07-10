"""Wyoming-protocol TTS bridge exposing Friday's cloned voice (voice_engine/Qwen3-TTS) to
Home Assistant as a first-class local TTS engine — the same voice the Pi hears, selectable
in an Assist pipeline exactly like Piper. Home Assistant's Wyoming integration only speaks
this TCP protocol (not the underlying voice_engine HTTP API directly), so this process just
translates: Describe -> Info (advertises one "friday" voice), Synthesize -> calls
voice_engine's existing /speak endpoint (the same one bmo_driver.py on the Pi calls) and
streams the resulting WAV back as AudioStart/AudioChunk/AudioStop events.

No synthesis logic lives here — voice_engine (and its BMO_REF_AUDIO clone reference) remains
the single source of truth for what Friday sounds like. This is a protocol adapter only.
"""
import asyncio
import io
import logging
import os
import wave

import httpx
from wyoming.audio import wav_to_chunks
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.tts import Synthesize

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("wyoming_friday_tts")

VOICE_ENGINE_URL = os.getenv("VOICE_ENGINE_URL", "http://voice-engine:8020").rstrip("/")
WYOMING_HOST = os.getenv("WYOMING_HOST", "0.0.0.0")
WYOMING_PORT = int(os.getenv("WYOMING_PORT", "10200"))
# Qwen3-TTS generation has been observed taking 10-20s for a short reply on real hardware —
# matches the timeout bmo_driver.py itself uses when calling voice_engine directly.
SYNTHESIZE_TIMEOUT = float(os.getenv("SYNTHESIZE_TIMEOUT", "90"))

_ATTRIBUTION = Attribution(name="Agent_Swarm", url="https://github.com/")

_INFO = Info(
    tts=[
        TtsProgram(
            name="friday",
            attribution=_ATTRIBUTION,
            installed=True,
            description="Friday's cloned voice (Qwen3-TTS, via voice_engine)",
            version=None,
            voices=[
                TtsVoice(
                    name="friday",
                    attribution=_ATTRIBUTION,
                    installed=True,
                    description="Friday — cloned voice, same one used on the Pi",
                    version=None,
                    languages=["en"],
                )
            ],
        )
    ],
)


class FridayTtsHandler(AsyncEventHandler):
    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(_INFO.event())
            return True

        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)
            text = synthesize.text
            _LOGGER.info("Synthesizing (%d chars): %r", len(text), text[:200])
            try:
                async with httpx.AsyncClient(timeout=SYNTHESIZE_TIMEOUT) as client:
                    resp = await client.post(f"{VOICE_ENGINE_URL}/speak", params={"text": text})
                    resp.raise_for_status()
                    wav_bytes = resp.content
            except Exception as e:  # noqa: BLE001
                # No audio events sent on failure — Assist will just get silence rather
                # than the connection dying, matching this project's fail-soft convention.
                _LOGGER.error("voice_engine call failed: %s: %s", type(e).__name__, e)
                return True

            with io.BytesIO(wav_bytes) as wav_io:
                wav_file: wave.Wave_read = wave.open(wav_io, "rb")
                with wav_file:
                    for chunk_event in wav_to_chunks(
                        wav_file, samples_per_chunk=1024, start_event=True, stop_event=True
                    ):
                        await self.write_event(chunk_event.event())
            _LOGGER.info("Sent %d bytes of audio", len(wav_bytes))
            return True

        return True


async def main() -> None:
    server = AsyncServer.from_uri(f"tcp://{WYOMING_HOST}:{WYOMING_PORT}")
    _LOGGER.info(
        "Wyoming Friday TTS bridge ready on %s:%s -> %s/speak",
        WYOMING_HOST, WYOMING_PORT, VOICE_ENGINE_URL,
    )
    await server.run(FridayTtsHandler)


if __name__ == "__main__":
    asyncio.run(main())
