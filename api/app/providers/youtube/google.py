"""Google YouTube Data API v3 provider: resumable upload, thumbnail, playlist.

Per-channel OAuth credentials are passed in at call time as a plain dict
(built + refreshed by ``services.youtube_oauth``); this class only needs the
app's client id/secret so the google client can refresh an expired token.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.pricing import YT_QUOTA_UNITS
from app.providers.base import UploadResult, YouTubeProvider

log = get_logger("youtube.google")

_UPLOAD_SCOPES = "https://www.googleapis.com/auth/youtube.upload"


class GoogleYouTube(YouTubeProvider):
    name = "google"

    def __init__(self) -> None:
        if not (settings.google_client_id and settings.google_client_secret):
            raise AppError(
                "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set", code=ErrorCode.CONFIG
            )

    # -- helpers -------------------------------------------------------------
    def _client(self, credential: Optional[dict[str, Any]]):
        if not credential or not credential.get("refresh_token"):
            raise AppError(
                "This channel is not connected to YouTube; run the OAuth flow first",
                code=ErrorCode.CONFIG,
            )
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=credential.get("token"),
            refresh_token=credential["refresh_token"],
            token_uri=credential.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=credential.get("scopes"),
        )
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    @staticmethod
    def _wrap(exc: Exception) -> AppError:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", 0)
            if status in (403, 429):
                return AppError(f"YouTube quota/permission error: {exc}", code=ErrorCode.QUOTA_EXCEEDED)
            if status >= 500:
                return AppError(f"YouTube server error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE)
            return AppError(f"YouTube rejected the request: {exc}", code=ErrorCode.UPLOAD_FAILED)
        return AppError(f"YouTube upload failed: {exc}", code=ErrorCode.UPLOAD_FAILED)

    # -- interface --------------------------------------------------------
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
        from googleapiclient.http import MediaFileUpload

        youtube = self._client(credential)
        status_body: dict[str, Any] = {
            "privacyStatus": "private" if publish_at else privacy_status,
            "selfDeclaredMadeForKids": False,
        }
        if publish_at:
            status_body["publishAt"] = publish_at

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": str(category_id or "27"),
            },
            "status": status_body,
        }
        media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
        try:
            request = youtube.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = None
            while response is None:
                _progress, response = request.next_chunk()
            video_id = response["id"]
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc

        published = privacy_status == "public" and not publish_at
        return UploadResult(
            video_id=video_id,
            url=f"https://youtu.be/{video_id}",
            status=("scheduled" if publish_at else ("published" if published else "uploaded")),
            quota_units=YT_QUOTA_UNITS["videos.insert"],
        )

    def set_thumbnail(
        self, *, video_id: str, image_path: str, credential: Optional[dict[str, Any]] = None
    ) -> int:
        from googleapiclient.http import MediaFileUpload

        youtube = self._client(credential)
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(image_path)
            ).execute()
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc
        return YT_QUOTA_UNITS["thumbnails.set"]

    def add_to_playlist(
        self, *, video_id: str, playlist_id: str, credential: Optional[dict[str, Any]] = None
    ) -> int:
        youtube = self._client(credential)
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc
        return YT_QUOTA_UNITS["playlistItems.insert"]
