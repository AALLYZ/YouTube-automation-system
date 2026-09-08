"""Environment-driven provider selection.

Each getter is cached; `reset_providers()` clears the cache (used in tests when
settings change).
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.providers.base import AIProvider, ResearchProvider, StorageProvider


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


def reset_providers() -> None:
    for fn in (get_storage, get_ai, get_research):
        fn.cache_clear()
