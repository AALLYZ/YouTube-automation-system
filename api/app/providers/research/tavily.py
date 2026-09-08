from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import research_cost
from app.providers.base import ResearchProvider, Source, Usage

_ENDPOINT = "https://api.tavily.com/search"


class TavilyResearch(ResearchProvider):
    name = "tavily"

    def __init__(self) -> None:
        if not settings.tavily_api_key:
            raise AppError("TAVILY_API_KEY is not set", code=ErrorCode.CONFIG)
        self._key = settings.tavily_api_key

    def search(self, query: str, *, depth: str = "basic", max_sources: int = 5):
        payload = {
            "api_key": self._key,
            "query": query,
            "search_depth": "advanced" if depth in ("deep", "advanced") else "basic",
            "max_results": max_sources,
            "include_answer": True,
        }
        try:
            resp = httpx.post(_ENDPOINT, json=payload, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = (
                ErrorCode.PROVIDER_RATE_LIMIT
                if exc.response.status_code == 429
                else ErrorCode.PROVIDER_UNAVAILABLE
            )
            raise AppError(f"Tavily error: {exc}", code=code) from exc
        except httpx.HTTPError as exc:
            raise AppError(f"Tavily network error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        data = resp.json()
        sources = []
        for r in data.get("results", []):
            sources.append(
                Source(
                    source=r.get("url", "").split("/")[2] if r.get("url") else "tavily",
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    key_facts=[r.get("content", "")[:500]] if r.get("content") else [],
                    date=r.get("published_date"),
                    relevance=float(r.get("score", 0)),
                    confidence=float(r.get("score", 0)),
                )
            )
        usage = Usage(
            provider="tavily",
            operation="search",
            units=1,
            est_cost_usd=research_cost("tavily", 1),
        )
        return sources, usage
