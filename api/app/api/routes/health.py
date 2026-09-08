from __future__ import annotations

import redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.base import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = False
    db_err = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_err = str(exc)

    redis_ok = False
    redis_err = None
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        redis_ok = True
    except Exception as exc:  # noqa: BLE001
        redis_err = str(exc)

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "env": settings.app_env,
        "checks": {
            "database": {"ok": db_ok, "error": db_err},
            "redis": {"ok": redis_ok, "error": redis_err},
        },
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
    }
