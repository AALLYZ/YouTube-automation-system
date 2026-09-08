from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel

from app.core.enums import NotificationEvent, NotificationStatus


class TestNotificationRequest(BaseModel):
    channel_id: int
    event: NotificationEvent = NotificationEvent.VIDEO_READY


class NotificationOut(BaseModel):
    id: int
    job_id: Optional[int]
    channel_id: int
    event: NotificationEvent
    provider: str
    recipient: str
    template: str
    body: str
    status: NotificationStatus
    provider_message_id: Optional[str]
    error: Optional[str]
    created_at: dt.datetime
    delivered_at: Optional[dt.datetime]

    class Config:
        from_attributes = True
