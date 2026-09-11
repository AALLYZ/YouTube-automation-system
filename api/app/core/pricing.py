"""Provider pricing table + cost estimation.

Prices are USD and editable — keep them aligned with each provider's public
pricing page. Costs are ESTIMATES for dashboard reporting, not billing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPrice:
    input_per_mtok: float   # USD per 1M input tokens
    output_per_mtok: float  # USD per 1M output tokens


# --- LLM token pricing (verify against provider pages) ---
LLM_PRICING: dict[str, TokenPrice] = {
    # Verify against https://www.anthropic.com/pricing and OpenAI pricing pages.
    "claude-sonnet-4-5": TokenPrice(3.00, 15.00),
    "claude-sonnet-4-6": TokenPrice(3.00, 15.00),
    "claude-sonnet-5": TokenPrice(3.00, 15.00),
    "claude-opus-5": TokenPrice(15.00, 75.00),
    "claude-haiku-4-5": TokenPrice(0.80, 4.00),
    "claude-3-5-sonnet": TokenPrice(3.00, 15.00),
    "claude-3-5-haiku": TokenPrice(0.80, 4.00),
    "gpt-4o": TokenPrice(2.50, 10.00),
    "gpt-4o-mini": TokenPrice(0.15, 0.60),
    "stub": TokenPrice(0.0, 0.0),
}

# --- Voice: USD per 1000 characters ---
VOICE_PER_1K_CHARS: dict[str, float] = {
    "elevenlabs": 0.30,
    "openai": 0.015,
    "local": 0.0,
    "stub": 0.0,
}

# --- Image: USD per image ---
IMAGE_PER_IMAGE: dict[str, float] = {
    "openai": 0.04,
    "stability": 0.03,
    "replicate": 0.01,
    "stub": 0.0,
}

# --- Research: USD per search ---
RESEARCH_PER_SEARCH: dict[str, float] = {
    "tavily": 0.008,
    "brave": 0.003,
    "serpapi": 0.015,
    "stub": 0.0,
}

# --- YouTube Data API quota units per operation ---
YT_QUOTA_UNITS: dict[str, int] = {
    "videos.insert": 1600,
    "thumbnails.set": 50,
    "playlistItems.insert": 50,
    "videos.update": 50,
    "channels.list": 1,
    "videos.list": 1,
}


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = LLM_PRICING.get(model) or LLM_PRICING.get(model.split("-2")[0]) or LLM_PRICING["stub"]
    return round(
        input_tokens / 1_000_000 * p.input_per_mtok
        + output_tokens / 1_000_000 * p.output_per_mtok,
        6,
    )


def voice_cost(provider: str, chars: int) -> float:
    return round(chars / 1000 * VOICE_PER_1K_CHARS.get(provider, 0.0), 6)


def image_cost(provider: str, count: int) -> float:
    return round(count * IMAGE_PER_IMAGE.get(provider, 0.0), 6)


def research_cost(provider: str, searches: int) -> float:
    return round(searches * RESEARCH_PER_SEARCH.get(provider, 0.0), 6)
