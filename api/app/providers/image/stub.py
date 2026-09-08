"""Offline image provider: renders a captioned gradient card with Pillow."""
from __future__ import annotations

import hashlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

from app.providers.base import ImageProvider, ImageResult, Usage


def _color(seed: int, shift: int = 0) -> tuple[int, int, int]:
    return (
        60 + (seed >> (shift + 0)) % 120,
        60 + (seed >> (shift + 8)) % 120,
        60 + (seed >> (shift + 16)) % 120,
    )


def _font(size: int):
    for name in ("Helvetica.ttc", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class StubImage(ImageProvider):
    name = "stub"

    def generate(
        self, *, prompt: str, out_path: str, width: int = 1920, height: int = 1080, style: str = ""
    ) -> ImageResult:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        top, bottom = _color(seed), _color(seed, 4)

        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / height
            draw.line(
                [(0, y), (width, y)],
                fill=tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3)),
            )

        wrapped = textwrap.fill(prompt[:180], width=max(20, width // 45))
        draw.multiline_text(
            (width * 0.08, height * 0.35),
            wrapped,
            font=_font(max(24, width // 28)),
            fill=(255, 255, 255),
            spacing=12,
        )
        draw.text((width * 0.08, height * 0.9), "stub visual", font=_font(max(16, width // 60)), fill=(230, 230, 230))
        img.save(out_path, "PNG")

        return ImageResult(
            path=out_path,
            width=width,
            height=height,
            license="generated-stub",
            attribution="",
            usage=Usage(provider="stub", operation="image", units=1, est_cost_usd=0.0),
        )
