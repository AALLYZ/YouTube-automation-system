from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.enums import JobStatus, UploadStatus, VideoStatus
from app.models.channel import Channel, ChannelSettings
from app.models.job import Job
from app.models.media import VideoProject
from app.models.ops import ApiUsage, Notification
from app.models.user import User
from app.models.youtube import YoutubeUpload

router = APIRouter(tags=["overview"])


def _utc_midnight() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    midnight = _utc_midnight()

    ch_total = db.execute(select(func.count(Channel.id))).scalar_one()
    ch_active = db.execute(select(func.count(Channel.id)).where(Channel.is_active.is_(True))).scalar_one()
    ch_auto = db.execute(
        select(func.count(ChannelSettings.id)).where(ChannelSettings.automation_enabled.is_(True))
    ).scalar_one()

    by_status = dict(
        db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    )
    by_status = {str(k): v for k, v in by_status.items()}

    recent = db.execute(select(Job).order_by(Job.id.desc()).limit(10)).scalars().all()
    recent_jobs = [
        {
            "public_id": j.public_id,
            "channel_id": j.channel_id,
            "status": str(j.status),
            "current_stage": str(j.current_stage),
            "progress_pct": j.progress_pct,
            "test_run": j.test_run,
            "total_cost_usd": round(j.total_cost_usd or 0, 4),
            "error_code": j.error_code,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in recent
    ]

    cost_today = db.execute(
        select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0)).where(ApiUsage.created_at >= midnight)
    ).scalar_one()
    cost_all = db.execute(
        select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0))
    ).scalar_one()
    quota_today = db.execute(
        select(func.coalesce(func.sum(ApiUsage.units), 0)).where(
            ApiUsage.provider == "youtube", ApiUsage.created_at >= midnight
        )
    ).scalar_one()

    uploads_total = db.execute(select(func.count(YoutubeUpload.id))).scalar_one()
    published = db.execute(
        select(func.count(YoutubeUpload.id)).where(
            YoutubeUpload.status.in_([UploadStatus.PUBLISHED, UploadStatus.UPLOADED, UploadStatus.SCHEDULED])
        )
    ).scalar_one()

    videos_ready = db.execute(
        select(func.count(VideoProject.id)).where(VideoProject.status == VideoStatus.READY)
    ).scalar_one()
    videos_rendering = db.execute(
        select(func.count(VideoProject.id)).where(VideoProject.status == VideoStatus.RENDERING)
    ).scalar_one()

    notif_total = db.execute(select(func.count(Notification.id))).scalar_one()
    notif_failed = db.execute(
        select(func.count(Notification.id)).where(Notification.status == "failed")
    ).scalar_one()

    return {
        "channels": {"total": ch_total, "active": ch_active, "automation": ch_auto},
        "jobs": {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "running": by_status.get(JobStatus.RUNNING, 0),
            "waiting_approval": by_status.get(JobStatus.WAITING_APPROVAL, 0),
            "failed": by_status.get(JobStatus.FAILED, 0),
        },
        "recent_jobs": recent_jobs,
        "cost": {"today_usd": round(cost_today, 4), "all_time_usd": round(cost_all, 4)},
        "youtube": {
            "quota_used_today": int(quota_today),
            "quota_daily_limit": settings.yt_daily_quota_units,
            "uploads_total": uploads_total,
            "published": published,
        },
        "videos": {"ready": videos_ready, "rendering": videos_rendering},
        "notifications": {"total": notif_total, "failed": notif_failed},
        "providers": {
            "ai": settings.ai_provider,
            "research": settings.research_provider,
            "voice": settings.voice_provider,
            "image": settings.image_provider,
            "stock": settings.stock_provider,
            "youtube": settings.youtube_provider,
            "notifier": settings.notifier_provider,
            "storage": settings.storage_provider,
        },
        "automation": {
            "scheduler_enabled": settings.scheduler_enabled,
            "jobs_async": settings.jobs_async,
        },
    }
