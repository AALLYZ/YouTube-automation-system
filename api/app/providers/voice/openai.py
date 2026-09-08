from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import voice_cost
from app.providers.base import Usage, VoiceProvider, VoiceResult


class OpenAIVoice(VoiceProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise AppError("OPENAI_API_KEY is not set", code=ErrorCode.CONFIG)
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)

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
        voice_name = voice or "alloy"
        try:
            with self._client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice_name,
                input=text,
                speed=max(0.25, min(4.0, speed)),
                response_format="mp3",
            ) as response:
                response.stream_to_file(out_path)
        except Exception as exc:  # noqa: BLE001
            raise AppError(f"OpenAI TTS error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        # OpenAI TTS gives no timestamps; approximate proportionally.
        words = text.split() or ["."]
        duration = max(2.0, len(words) / (2.5 * max(0.5, speed)))
        per = duration / len(words)
        timestamps = [
            {"word": w, "start": round(i * per, 3), "end": round((i + 1) * per, 3)}
            for i, w in enumerate(words)
        ]
        return VoiceResult(
            audio_path=out_path,
            duration_sec=round(duration, 3),
            timestamps=timestamps,
            usage=Usage(
                provider="openai",
                model="tts-1",
                operation="tts",
                units=len(text),
                est_cost_usd=voice_cost("openai", len(text)),
            ),
        )
