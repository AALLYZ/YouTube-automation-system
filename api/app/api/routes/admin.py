from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.enums import UserRole
from app.core.errors import AuthError
from app.models.user import User
from app.services.retention import prune_artifacts

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AuthError("Admin role required")
    return user


@router.get("/retention")
def retention_preview(
    days: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return prune_artifacts(db, days=days, dry_run=True)


@router.post("/retention")
def retention_run(
    days: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return prune_artifacts(db, days=days, dry_run=False)


@router.get("/config")
def runtime_config(_: User = Depends(_require_admin)) -> dict:
    """Non-secret runtime configuration snapshot for ops."""
    return {
        "app_env": settings.app_env,
        "public_host": settings.public_host,
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
            "max_concurrent_jobs": settings.max_concurrent_jobs,
            "max_stage_retries": settings.max_stage_retries,
            "daily_video_limit": settings.daily_video_limit,
        },
        "limits": {
            "yt_daily_quota_units": settings.yt_daily_quota_units,
            "artifact_retention_days": settings.artifact_retention_days,
            "rate_limit_enabled": settings.rate_limit_enabled,
        },
    }
