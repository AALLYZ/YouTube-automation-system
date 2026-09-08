from __future__ import annotations

import base64
import json

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import voice_cost
from app.providers.base import Usage, VoiceProvider, VoiceResult

_BASE = "https://api.elevenlabs.io/v1"
_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"


class ElevenLabsVoice(VoiceProvider):
    name = "elevenlabs"

    def __init__(self) -> None:
        if not settings.elevenlabs_api_key:
            raise AppError("ELEVENLABS_API_KEY is not set", code=ErrorCode.CONFIG)
        self._key = settings.elevenlabs_api_key
        self._default_voice = settings.elevenlabs_voice_id or _DEFAULT_VOICE

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
        voice_id = voice or self._default_voice
        url = f"{_BASE}/text-to-speech/{voice_id}/with-timestamps"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            resp = httpx.post(
                url,
                headers={"xi-api-key": self._key, "content-type": "application/json"},
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = (
                ErrorCode.PROVIDER_RATE_LIMIT
                if exc.response.status_code in (429, 401)
                else ErrorCode.PROVIDER_UNAVAILABLE
            )
            raise AppError(f"ElevenLabs error {exc.response.status_code}: {exc.response.text[:200]}", code=code) from exc
        except httpx.HTTPError as exc:
            raise AppError(f"ElevenLabs network error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        data = resp.json()
        audio_b64 = data.get("audio_base64") or data.get("audio")
        if not audio_b64:
            raise AppError("ElevenLabs returned no audio", code=ErrorCode.PROVIDER_BAD_RESPONSE)
        with open(out_path, "wb") as fh:
            fh.write(base64.b64decode(audio_b64))

        alignment = data.get("alignment") or {}
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        timestamps = _chars_to_words(chars, starts, ends)
        duration = (ends[-1] if ends else _estimate(text))

        return VoiceResult(
            audio_path=out_path,
            duration_sec=round(float(duration), 3),
            timestamps=timestamps,
            usage=Usage(
                provider="elevenlabs",
                operation="tts",
                units=len(text),
                est_cost_usd=voice_cost("elevenlabs", len(text)),
            ),
        )


def _estimate(text: str) -> float:
    return max(2.0, len(text.split()) / 2.5)


def _chars_to_words(chars, starts, ends):
    words, buf, w_start = [], "", None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if buf:
                words.append({"word": buf, "start": round(w_start, 3), "end": round(prev_e, 3)})
                buf, w_start = "", None
        else:
            if w_start is None:
                w_start = s
            buf += c
        prev_e = e
    if buf and w_start is not None:
        words.append({"word": buf, "start": round(w_start, 3), "end": round(prev_e, 3)})
    return words
