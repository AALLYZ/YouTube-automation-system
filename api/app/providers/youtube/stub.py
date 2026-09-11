"""Offline YouTube provider: fakes an upload so the publish stage runs with no OAuth."""
from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

from app.core.logging import get_logger
from app.core.pricing import YT_QUOTA_UNITS
from app.providers.base import TrendingVideo, UploadResult, YouTubeProvider

log = get_logger("youtube.stub")

_TRENDING_SEED = [
    ("I Tried the World's Hardest Puzzle for 24 Hours", "Entertainment", "24", 4_820_000),
    ("This New Phone Changes Everything", "Tech Review Central", "28", 3_150_000),
    ("The Truth About Your Morning Routine", "Better Every Day", "26", 2_760_000),
    ("Building a House in the Middle of Nowhere - Part 1", "Off Grid Builds", "26", 5_930_000),
    ("Why Everyone Is Talking About This AI Tool", "Tech Review Central", "28", 6_410_000),
    ("Ranking Every Fast Food Burger So You Don't Have To", "Taste Test Tim", "24", 2_040_000),
    ("What Nobody Tells You About Moving Abroad", "Wander & Work", "19", 1_870_000),
    ("The Science Behind Why We Procrastinate", "Curious Mind", "27", 3_390_000),
    ("I Lived on $10 a Day for a Week", "Budget Life", "22", 4_120_000),
    ("This Simple Trick Fixed My Sleep Schedule", "Better Every Day", "26", 2_910_000),
]


class StubYouTube(YouTubeProvider):
    name = "stub"

    def upload(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
        privacy_status: str,
        publish_at: Optional[str] = None,
        credential: Optional[dict[str, Any]] = None,
    ) -> UploadResult:
        seed = hashlib.sha256(
            f"{title}|{os.path.getsize(video_path) if os.path.exists(video_path) else 0}".encode()
        ).hexdigest()[:11]
        video_id = f"stub{seed}"
        status = "scheduled" if publish_at else ("uploaded" if privacy_status == "private" else "published")
        log.info("stub upload: %s (%s, privacy=%s, publish_at=%s)", video_id, title[:60], privacy_status, publish_at)
        return UploadResult(
            video_id=video_id,
            url=f"https://youtu.be/{video_id}",
            status=status,
            quota_units=YT_QUOTA_UNITS["videos.insert"],
        )

    def set_thumbnail(
        self, *, video_id: str, image_path: str, credential: Optional[dict[str, Any]] = None
    ) -> int:
        log.info("stub set_thumbnail for %s from %s", video_id, os.path.basename(image_path))
        return YT_QUOTA_UNITS["thumbnails.set"]

    def add_to_playlist(
        self, *, video_id: str, playlist_id: str, credential: Optional[dict[str, Any]] = None
    ) -> int:
        log.info("stub add_to_playlist: %s -> %s", video_id, playlist_id)
        return YT_QUOTA_UNITS["playlistItems.insert"]

    def list_trending(
        self,
        *,
        region_code: str = "US",
        category_id: Optional[str] = None,
        max_results: int = 15,
        credential: Optional[dict[str, Any]] = None,
    ) -> tuple[list[TrendingVideo], int]:
        rows = _TRENDING_SEED
        if category_id:
            rows = [r for r in rows if r[2] == str(category_id)] or _TRENDING_SEED
        videos: list[TrendingVideo] = []
        for title, channel_title, cat, views in rows[: max(1, max_results)]:
            vid = f"stub{hashlib.sha256(f'{title}|{region_code}'.encode()).hexdigest()[:11]}"
            videos.append(
                TrendingVideo(
                    video_id=vid,
                    title=title,
                    description=f"({region_code} trending, stub data) A popular video about: {title}",
                    channel_title=channel_title,
                    tags=[w.lower() for w in title.split() if len(w) > 3][:5],
                    category_id=cat,
                    view_count=views,
                    published_at="2026-09-01T00:00:00Z",
                    url=f"https://youtu.be/{vid}",
                )
            )
        log.info("stub list_trending: %d videos (region=%s, category=%s)", len(videos), region_code, category_id)
        return videos, YT_QUOTA_UNITS["videos.list"]
