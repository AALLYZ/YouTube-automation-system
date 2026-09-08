from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.enums import NotificationEvent
from app.core.errors import NotFoundError
from app.models.channel import Channel
from app.models.ops import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut, TestNotificationRequest
from app.services.notifications import send_test

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test", response_model=NotificationOut)
def test_notification(
    payload: TestNotificationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    channel = db.get(Channel, payload.channel_id)
    if not channel:
        raise NotFoundError("Channel not found")
    row = send_test(db, channel=channel, event=payload.event)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    channel_id: int | None = Query(None),
    job_id: int | None = Query(None),
    event: NotificationEvent | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Notification).order_by(Notification.id.desc()).limit(limit)
    if channel_id is not None:
        q = q.where(Notification.channel_id == channel_id)
    if job_id is not None:
        q = q.where(Notification.job_id == job_id)
    if event is not None:
        q = q.where(Notification.event == event)
    return db.execute(q).scalars().all()
