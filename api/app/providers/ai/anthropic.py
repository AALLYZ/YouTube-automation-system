from __future__ import annotations

import time
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import llm_cost
from app.providers.base import AIProvider, AIResult, Usage


class AnthropicAI(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise AppError("ANTHROPIC_API_KEY is not set", code=ErrorCode.CONFIG)
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._default_model = settings.model
        self._rate_limit_errors = (
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        )

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
        model = model or self._default_model
        sys_prompt = system
        if json_mode:
            sys_prompt = (
                system
                + "\n\nRespond with a single valid JSON object and nothing else. "
                "No markdown fences, no prose."
            )

        started = time.time()
        try:
            msg = self._call(model, sys_prompt, prompt, temperature, max_tokens)
        except self._rate_limit_errors as exc:  # type: ignore[misc]
            raise AppError(
                f"Anthropic unavailable: {exc}", code=ErrorCode.PROVIDER_RATE_LIMIT
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                f"Anthropic error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE
            ) from exc

        text = "".join(block.text for block in msg.content if block.type == "text")
        in_tok = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        usage = Usage(
            provider="anthropic",
            model=model,
            operation=task or "complete",
            input_tokens=in_tok,
            output_tokens=out_tok,
            seconds=round(time.time() - started, 3),
            est_cost_usd=llm_cost(model, in_tok, out_tok),
        )
        return AIResult(text=text.strip(), usage=usage)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        reraise=True,
    )
    def _call(self, model, system, prompt, temperature, max_tokens):
        return self._client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
