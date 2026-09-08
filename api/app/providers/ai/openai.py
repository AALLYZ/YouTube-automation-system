from __future__ import annotations

import time
from typing import Optional

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import llm_cost
from app.providers.base import AIProvider, AIResult, Usage


class OpenAIAI(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise AppError("OPENAI_API_KEY is not set", code=ErrorCode.CONFIG)
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.model if settings.model.startswith("gpt") else "gpt-4o-mini"

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        task: str = "",
    ) -> AIResult:
        model = model or self._model
        kwargs: dict = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        started = time.time()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            code = ErrorCode.PROVIDER_RATE_LIMIT if "rate" in str(exc).lower() else ErrorCode.PROVIDER_UNAVAILABLE
            raise AppError(f"OpenAI error: {exc}", code=code) from exc

        text = resp.choices[0].message.content or ""
        u = resp.usage
        usage = Usage(
            provider="openai",
            model=model,
            operation=task or "complete",
            input_tokens=getattr(u, "prompt_tokens", 0),
            output_tokens=getattr(u, "completion_tokens", 0),
            seconds=round(time.time() - started, 3),
            est_cost_usd=llm_cost(model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0)),
        )
        return AIResult(text=text.strip(), usage=usage)
