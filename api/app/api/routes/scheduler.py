from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.errors import NotFoundError
from app.models.channel import Channel
from app.models.ops import SchedulerRun
from app.models.user import User
from app.scheduler.scheduler import tick_all, tick_channel

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
def scheduler_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    recent = db.execute(
        select(SchedulerRun).order_by(SchedulerRun.id.desc()).limit(20)
    ).scalars().all()
    return {
        "enabled": settings.scheduler_enabled,
        "jobs_async": settings.jobs_async,
        "recent_runs": [
            {
                "channel_id": r.channel_id,
                "run_date": r.run_date.isoformat(),
                "jobs_created": r.jobs_created,
                "status": r.status,
            }
            for r in recent
        ],
    }


@router.post("/run")
def run_scheduler(
    channel_id: int | None = Query(None),
    force: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if channel_id is not None:
        channel = db.get(Channel, channel_id)
        if not channel:
            raise NotFoundError("Channel not found")
        return {"results": [tick_channel(db, channel, force=force)]}
    return {"results": tick_all(db, force=force)}


@router.get("/runs")
def list_runs(
    channel_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(SchedulerRun).order_by(SchedulerRun.id.desc()).limit(100)
    if channel_id is not None:
        q = q.where(SchedulerRun.channel_id == channel_id)
    rows = db.execute(q).scalars().all()
    return [
        {
            "id": r.id,
            "channel_id": r.channel_id,
            "run_date": r.run_date.isoformat(),
            "lock_key": r.lock_key,
            "jobs_created": r.jobs_created,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
