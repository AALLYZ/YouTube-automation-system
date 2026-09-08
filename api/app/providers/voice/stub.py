"""Offline voice provider: emits a real WAV (near-silence) sized to the text."""
from __future__ import annotations

import math
import struct
import wave

from app.providers.base import VoiceProvider, VoiceResult, Usage

SAMPLE_RATE = 22050
WORDS_PER_SECOND = 2.5


def _word_count(text: str) -> int:
    return max(1, len(text.split()))


class StubVoice(VoiceProvider):
    name = "stub"

    def synthesize(
        self,
        *,
        text: str,
        out_path: str,
        voice: str = "",
        language: str = "English",
        speed: float = 1.0,
        emotion: str = "neutral",
    ) -> VoiceResult:
        words = _word_count(text)
        duration = max(2.0, words / (WORDS_PER_SECOND * max(0.5, speed)))
        n_samples = int(duration * SAMPLE_RATE)

        # very quiet 120 Hz hum so downstream tools always see a valid audio stream
        amp = 60
        with wave.open(out_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            frames = bytearray()
            for i in range(n_samples):
                v = int(amp * math.sin(2 * math.pi * 120 * (i / SAMPLE_RATE)))
                frames += struct.pack("<h", v)
            wf.writeframes(bytes(frames))

        # even word-level timestamps
        per = duration / words
        toks = text.split()
        timestamps = [
            {"word": w, "start": round(i * per, 3), "end": round((i + 1) * per, 3)}
            for i, w in enumerate(toks)
        ]
        return VoiceResult(
            audio_path=out_path,
            duration_sec=round(duration, 3),
            timestamps=timestamps,
            usage=Usage(provider="stub", operation="tts", units=len(text), est_cost_usd=0.0),
        )
