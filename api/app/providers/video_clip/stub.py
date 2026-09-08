"""Offline AI-video-clip provider: a short pan over a generated still (handled at
render time). Here we just produce the still and mark it as a clip source."""
from __future__ import annotations

from app.providers.base import ImageProvider, ImageResult, VideoClipProvider
from app.providers.image.stub import StubImage


class StubVideoClip(VideoClipProvider):
    name = "stub"

    def generate(self, *, prompt: str, out_path: str, duration_sec: float = 4.0) -> ImageResult:
        # produce a still; render.py applies a Ken Burns zoom for clip scenes
        res: ImageResult = StubImage().generate(prompt=f"clip: {prompt}", out_path=out_path)
        res.license = "generated-stub-clip"
        return res
