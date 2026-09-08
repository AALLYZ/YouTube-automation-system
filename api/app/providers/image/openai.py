from __future__ import annotations

import base64

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import image_cost
from app.providers.base import ImageProvider, ImageResult, Usage


def _closest_size(width: int, height: int) -> str:
    if width == height:
        return "1024x1024"
    return "1792x1024" if width > height else "1024x1792"


class OpenAIImage(ImageProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise AppError("OPENAI_API_KEY is not set", code=ErrorCode.CONFIG)
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(
        self, *, prompt: str, out_path: str, width: int = 1920, height: int = 1080, style: str = ""
    ) -> ImageResult:
        full_prompt = f"{prompt}. Style: {style}" if style else prompt
        try:
            resp = self._client.images.generate(
                model="gpt-image-1",
                prompt=full_prompt,
                size=_closest_size(width, height),
                n=1,
            )
        except Exception as exc:  # noqa: BLE001
            code = ErrorCode.PROVIDER_RATE_LIMIT if "rate" in str(exc).lower() else ErrorCode.PROVIDER_UNAVAILABLE
            raise AppError(f"OpenAI image error: {exc}", code=code) from exc

        b64 = resp.data[0].b64_json
        raw = base64.b64decode(b64)
        with open(out_path, "wb") as fh:
            fh.write(raw)

        # normalise to requested dimensions
        try:
            from PIL import Image

            im = Image.open(out_path).convert("RGB").resize((width, height))
            im.save(out_path)
        except Exception:  # noqa: BLE001
            pass

        return ImageResult(
            path=out_path,
            width=width,
            height=height,
            license="openai-generated",
            attribution="",
            usage=Usage(
                provider="openai",
                model="gpt-image-1",
                operation="image",
                units=1,
                est_cost_usd=image_cost("openai", 1),
            ),
        )
