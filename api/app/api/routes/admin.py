from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.enums import UserRole
from app.core.errors import AppError, AuthError, ErrorCode, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import AdminCreateUser, AdminUpdateUser, UserOut
from app.services.retention import prune_artifacts

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AuthError("Admin role required")
    return user


def _admin_count(db: Session) -> int:
    return db.execute(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    ).scalar_one()


# ---------------- user management ----------------
@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(_require_admin)):
    return db.execute(select(User).order_by(User.id)).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: AdminCreateUser, db: Session = Depends(get_db), _: User = Depends(_require_admin)
):
    email = payload.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise AppError("An account with that email already exists", code=ErrorCode.VALIDATION)
    user = User(email=email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUpdateUser,
    db: Session = Depends(get_db),
    me: User = Depends(_require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")

    losing_admin = user.role == UserRole.ADMIN and (
        (payload.role is not None and payload.role != UserRole.ADMIN)
        or payload.is_active is False
    )
    if losing_admin and _admin_count(db) <= 1:
        raise AppError("Cannot remove the last active admin", code=ErrorCode.VALIDATION)
    if user.id == me.id and payload.is_active is False:
        raise AppError("You cannot deactivate your own account", code=ErrorCode.VALIDATION)

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
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
