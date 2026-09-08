from __future__ import annotations

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import engine
from app.models.user import User

router = APIRouter(tags=["health"])

_PROVIDERS = {
    "ai": settings.ai_provider,
    "research": settings.research_provider,
    "voice": settings.voice_provider,
    "image": settings.image_provider,
    "stock": settings.stock_provider,
    "youtube": settings.youtube_provider,
    "notifier": settings.notifier_provider,
    "storage": settings.storage_provider,
}


def _check_db() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _check_redis() -> dict:
    try:
        redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        return {"ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@router.get("/health")
def health() -> dict:
    checks = {"database": _check_db(), "redis": _check_redis()}
    status = "ok" if all(c["ok"] for c in checks.values()) else "degraded"
    return {
        "status": status,
        "env": settings.app_env,
        "checks": checks,
        "providers": dict(_PROVIDERS),
    }


@router.get("/health/deep")
def health_deep(_: User = Depends(get_current_user)) -> dict:
    from app.providers.health import deep_check

    checks = {"database": _check_db(), "redis": _check_redis(), "ffmpeg": _check_ffmpeg()}
    providers = deep_check()

    core_ok = all(c["ok"] for c in checks.values())
    providers_ok = all(p["ok"] for p in providers.values())
    return {
        "status": "ok" if (core_ok and providers_ok) else "degraded",
        "env": settings.app_env,
        "checks": checks,
        "providers": providers,
    }


def _check_ffmpeg() -> dict:
    try:
        from app.utils.ffmpeg import ffmpeg_exe, ffprobe_exe

        return {"ok": True, "error": None, "ffmpeg": ffmpeg_exe(), "ffprobe": ffprobe_exe()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
