from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.job import Job
from app.models.ops import ApiUsage, SystemLog
from app.models.user import User

router = APIRouter(tags=["logs"])


@router.get("/logs")
def list_logs(
    level: str | None = Query(None),
    job_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(SystemLog).order_by(SystemLog.id.desc()).limit(limit)
    if level:
        q = q.where(SystemLog.level == level.upper())
    if job_id is not None:
        q = q.where(SystemLog.job_id == job_id)
    rows = db.execute(q).scalars().all()
    return [
        {
            "id": r.id,
            "level": r.level,
            "event": r.event,
            "stage": r.stage,
            "message": r.message,
            "job_id": r.job_id,
            "context": r.context,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/usage")
def list_usage(
    job_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(ApiUsage, Job.public_id).join(Job, Job.id == ApiUsage.job_id, isouter=True)
    q = q.order_by(ApiUsage.id.desc()).limit(limit)
    if job_id is not None:
        q = q.where(ApiUsage.job_id == job_id)
    out = []
    for u, public_id in db.execute(q).all():
        out.append(
            {
                "id": u.id,
                "job": public_id,
                "stage": u.stage,
                "provider": u.provider,
                "model": u.model,
                "operation": u.operation,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "units": u.units,
                "est_cost_usd": round(u.est_cost_usd or 0, 6),
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
        )
    return out
