from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.providers.base import StockMediaProvider, StockResult

_PHOTO = "https://api.pexels.com/v1/search"
_VIDEO = "https://api.pexels.com/videos/search"


class PexelsStock(StockMediaProvider):
    name = "pexels"

    def __init__(self) -> None:
        if not settings.pexels_api_key:
            raise AppError("PEXELS_API_KEY is not set", code=ErrorCode.CONFIG)
        self._headers = {"Authorization": settings.pexels_api_key}

    def search(self, query: str, *, kind: str = "photo", out_path: str = "") -> Optional[StockResult]:
        is_video = kind == "video"
        url = _VIDEO if is_video else _PHOTO
        try:
            resp = httpx.get(
                url, headers=self._headers, params={"query": query, "per_page": 1, "orientation": "landscape"}, timeout=30
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = ErrorCode.PROVIDER_RATE_LIMIT if exc.response.status_code == 429 else ErrorCode.PROVIDER_UNAVAILABLE
            raise AppError(f"Pexels error {exc.response.status_code}", code=code) from exc
        except httpx.HTTPError as exc:
            raise AppError(f"Pexels network error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        data = resp.json()
        items = data.get("videos" if is_video else "photos", [])
        if not items:
            return None
        item = items[0]

        if is_video:
            files = sorted(item["video_files"], key=lambda f: (f.get("width") or 0), reverse=True)
            media_url = files[0]["link"]
            w, h = files[0].get("width", 1920), files[0].get("height", 1080)
            author = item.get("user", {}).get("name", "Pexels")
        else:
            media_url = item["src"]["large2x"]
            w, h = item.get("width", 1920), item.get("height", 1080)
            author = item.get("photographer", "Pexels")

        if not out_path:
            return None
        with httpx.stream("GET", media_url, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)

        return StockResult(
            path=out_path,
            width=w,
            height=h,
            license="Pexels License (free, attribution appreciated)",
            attribution=f"{author} / Pexels — {item.get('url', '')}",
            is_video=is_video,
        )
