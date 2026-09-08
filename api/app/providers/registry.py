"""Environment-driven provider selection.

Each getter is cached; `reset_providers()` clears the cache (used in tests when
settings change).
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.providers.base import (
    AIProvider,
    ImageProvider,
    NotifierProvider,
    ResearchProvider,
    StockMediaProvider,
    StorageProvider,
    VideoClipProvider,
    VoiceProvider,
    YouTubeProvider,
)


@lru_cache
def get_storage() -> StorageProvider:
    if settings.storage_provider == "s3":
        from app.providers.storage.s3 import S3Storage  # noqa

        return S3Storage()
    from app.providers.storage.local import LocalStorage

    return LocalStorage()


@lru_cache
def get_ai() -> AIProvider:
    p = settings.ai_provider
    if p == "anthropic":
        from app.providers.ai.anthropic import AnthropicAI

        return AnthropicAI()
    if p == "openai":
        from app.providers.ai.openai import OpenAIAI

        return OpenAIAI()
    if p == "stub":
        from app.providers.ai.stub import StubAI

        return StubAI()
    raise AppError(f"Unknown AI_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_research() -> ResearchProvider:
    p = settings.research_provider
    if p == "tavily":
        from app.providers.research.tavily import TavilyResearch

        return TavilyResearch()
    if p == "stub":
        from app.providers.research.stub import StubResearch

        return StubResearch()
    raise AppError(f"Unknown RESEARCH_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_voice() -> VoiceProvider:
    p = settings.voice_provider
    if p == "elevenlabs":
        from app.providers.voice.elevenlabs import ElevenLabsVoice

        return ElevenLabsVoice()
    if p == "openai":
        from app.providers.voice.openai import OpenAIVoice

        return OpenAIVoice()
    if p in ("local", "stub"):
        from app.providers.voice.stub import StubVoice

        return StubVoice()
    raise AppError(f"Unknown VOICE_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_image() -> ImageProvider:
    p = settings.image_provider
    if p == "openai":
        from app.providers.image.openai import OpenAIImage

        return OpenAIImage()
    if p == "stub":
        from app.providers.image.stub import StubImage

        return StubImage()
    raise AppError(f"Unknown IMAGE_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_stock() -> StockMediaProvider:
    p = settings.stock_provider
    if p == "pexels":
        from app.providers.stock.pexels import PexelsStock

        return PexelsStock()
    if p == "stub":
        from app.providers.stock.stub import StubStock

        return StubStock()
    raise AppError(f"Unknown STOCK_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_video_clip() -> VideoClipProvider:
    from app.providers.video_clip.stub import StubVideoClip

    return StubVideoClip()


@lru_cache
def get_youtube() -> YouTubeProvider:
    p = settings.youtube_provider
    if p == "google":
        from app.providers.youtube.google import GoogleYouTube

        return GoogleYouTube()
    if p == "stub":
        from app.providers.youtube.stub import StubYouTube

        return StubYouTube()
    raise AppError(f"Unknown YOUTUBE_PROVIDER: {p}", code=ErrorCode.CONFIG)


@lru_cache
def get_notifier() -> NotifierProvider:
    p = settings.notifier_provider
    if p == "twilio":
        from app.providers.notifier.twilio_wa import TwilioWhatsApp

        return TwilioWhatsApp()
    if p == "meta_cloud":
        from app.providers.notifier.meta_cloud import MetaCloudWhatsApp

        return MetaCloudWhatsApp()
    if p == "stub":
        from app.providers.notifier.stub import StubNotifier

        return StubNotifier()
    if p == "console":
        from app.providers.notifier.console import ConsoleNotifier

        return ConsoleNotifier()
    raise AppError(f"Unknown NOTIFIER_PROVIDER: {p}", code=ErrorCode.CONFIG)


def reset_providers() -> None:
    for fn in (
        get_storage, get_ai, get_research, get_voice, get_image, get_stock,
        get_video_clip, get_youtube, get_notifier,
    ):
        fn.cache_clear()
