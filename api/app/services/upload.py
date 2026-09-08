"""Upload stage: push the rendered video + thumbnail to YouTube, track quota."""
from __future__ import annotations

import datetime as dt
import os
import tempfile
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import UploadStatus, VideoStatus
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.pricing import YT_QUOTA_UNITS
from app.models.channel import Channel
from app.models.job import Job
from app.models.media import Thumbnail, VideoProject
from app.models.ops import ApiUsage
from app.models.youtube import YoutubeUpload
from app.providers.base import Usage
from app.providers.registry import get_storage, get_youtube
from app.services.ai_helpers import record_usage
from app.services import youtube_oauth

log = get_logger("upload")

_STATUS_MAP = {
    "published": UploadStatus.PUBLISHED,
    "scheduled": UploadStatus.SCHEDULED,
    "uploaded": UploadStatus.UPLOADED,
}


def quota_used_today(db: Session) -> int:
    start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.execute(
            select(func.coalesce(func.sum(ApiUsage.units), 0)).where(
                ApiUsage.provider == "youtube", ApiUsage.created_at >= start
            )
        ).scalar_one()
    )


def check_quota(db: Session, need: int) -> None:
    used = quota_used_today(db)
    if used + need > settings.yt_daily_quota_units:
        raise AppError(
            f"YouTube daily quota would be exceeded ({used} + {need} > {settings.yt_daily_quota_units})",
            code=ErrorCode.QUOTA_EXCEEDED,
        )


def _record_quota(db: Session, job_id: int, operation: str, units: int) -> None:
    record_usage(
        db,
        Usage(provider="youtube", model=None, operation=operation, units=units, est_cost_usd=0.0),
        job_id=job_id,
        stage="UPLOAD",
    )


def run_upload(db: Session, *, job: Job, channel: Channel) -> dict[str, Any]:
    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job.id)).scalar_one_or_none()
    if not vp or not vp.video_key or vp.status != VideoStatus.READY:
        raise AppError("No rendered video ready to upload", code=ErrorCode.MISSING_ASSET)

    row = db.execute(select(YoutubeUpload).where(YoutubeUpload.job_id == job.id)).scalar_one_or_none()
    if not row or not row.title:
        raise AppError("Run the metadata stage before upload", code=ErrorCode.VALIDATION)

    storage = get_storage()
    if not storage.exists(vp.video_key):
        raise AppError("Rendered video file is missing from storage", code=ErrorCode.MISSING_ASSET)

    thumb = db.execute(
        select(Thumbnail).where(Thumbnail.job_id == job.id, Thumbnail.selected.is_(True))
    ).scalar_one_or_none()

    # quota estimate up front
    need = YT_QUOTA_UNITS["videos.insert"]
    if thumb and thumb.file_key:
        need += YT_QUOTA_UNITS["thumbnails.set"]
    if row.playlist_id:
        need += YT_QUOTA_UNITS["playlistItems.insert"]
    check_quota(db, need)

    # test runs never touch a real account
    test_mode = job.test_run or settings.youtube_provider == "stub"
    if test_mode:
        from app.providers.youtube.stub import StubYouTube

        provider = StubYouTube()
        credential = None
    else:
        provider = get_youtube()
        credential = youtube_oauth.credential_dict(db, channel)
        if credential is None:
            raise AppError(
                "Channel is not connected to YouTube; connect it first",
                code=ErrorCode.CONFIG,
            )

    publish_at = None
    if row.scheduled_publish_at:
        dt_val = row.scheduled_publish_at
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=dt.timezone.utc)
        if dt_val > dt.datetime.now(dt.timezone.utc):
            publish_at = dt_val.isoformat().replace("+00:00", "Z")

    row.status = UploadStatus.UPLOADING
    db.flush()

    with tempfile.TemporaryDirectory() as tmp:
        local_video = os.path.join(tmp, "final_video.mp4")
        storage.get(vp.video_key, local_video)
        try:
            result = provider.upload(
                video_path=local_video,
                title=row.title,
                description=row.description or "",
                tags=list(row.tags or []),
                category_id=row.category_id or settings.youtube_default_category_id,
                privacy_status=row.privacy_status.value,
                publish_at=publish_at,
                credential=credential,
            )
        except AppError:
            row.status = UploadStatus.FAILED
            db.flush()
            raise
        _record_quota(db, job.id, "videos.insert", result.quota_units or YT_QUOTA_UNITS["videos.insert"])
        total_units = result.quota_units or YT_QUOTA_UNITS["videos.insert"]

        if thumb and thumb.file_key and storage.exists(thumb.file_key):
            local_thumb = os.path.join(tmp, "thumb.png")
            storage.get(thumb.file_key, local_thumb)
            try:
                units = provider.set_thumbnail(
                    video_id=result.video_id, image_path=local_thumb, credential=credential
                )
                _record_quota(db, job.id, "thumbnails.set", units)
                total_units += units
            except AppError as exc:  # thumbnail failure must not lose the upload
                log.warning("thumbnail upload failed for %s: %s", result.video_id, exc.message)

        if row.playlist_id:
            try:
                units = provider.add_to_playlist(
                    video_id=result.video_id, playlist_id=row.playlist_id, credential=credential
                )
                _record_quota(db, job.id, "playlistItems.insert", units)
                total_units += units
            except AppError as exc:
                log.warning("playlist insert failed for %s: %s", result.video_id, exc.message)

    row.youtube_video_id = result.video_id
    row.youtube_url = result.url
    row.status = _STATUS_MAP.get(result.status, UploadStatus.UPLOADED)
    row.quota_units_used = total_units
    row.error = None
    if row.status == UploadStatus.PUBLISHED:
        row.published_at = dt.datetime.now(dt.timezone.utc)
    db.flush()

    out = {
        "youtube_video_id": result.video_id,
        "youtube_url": result.url,
        "status": row.status.value,
        "privacy_status": row.privacy_status.value,
        "scheduled_publish_at": publish_at,
        "quota_units_used": total_units,
        "quota_used_today": quota_used_today(db),
        "test_mode": test_mode,
    }
    log.info("upload: job %s -> %s (%s)", job.public_id, result.video_id, row.status.value)
    return out
