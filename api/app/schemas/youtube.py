from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel

from app.core.enums import PrivacyStatus, UploadStatus


class OAuthStartOut(BaseModel):
    authorization_url: str
    state: str


class YouTubeStatusOut(BaseModel):
    channel_id: int
    provider: str
    configured: bool
    connected: bool
    youtube_channel_id: Optional[str] = None
    youtube_channel_title: Optional[str] = None
    connected_at: Optional[str] = None
    scopes: list[str] = []
    token_expires_at: Optional[str] = None
    quota_used_today: int = 0
    quota_daily_limit: int = 0


class DisconnectOut(BaseModel):
    channel_id: int
    disconnected: bool


class UploadOut(BaseModel):
    job_id: int
    channel_id: int
    title: str
    description: str
    tags: list[str]
    hashtags: list[str]
    category_id: str
    playlist_id: Optional[str]
    chapters: list[Any]
    title_options: list[Any]
    privacy_status: PrivacyStatus
    scheduled_publish_at: Optional[dt.datetime]
    youtube_video_id: Optional[str]
    youtube_url: Optional[str]
    status: UploadStatus
    published_at: Optional[dt.datetime]
    quota_units_used: int
    error: Optional[str]

    class Config:
        from_attributes = True
