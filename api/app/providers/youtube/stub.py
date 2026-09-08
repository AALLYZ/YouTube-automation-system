"""Offline YouTube provider: fakes an upload so the publish stage runs with no OAuth."""
from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

from app.core.logging import get_logger
from app.core.pricing import YT_QUOTA_UNITS
from app.providers.base import UploadResult, YouTubeProvider

log = get_logger("youtube.stub")


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
