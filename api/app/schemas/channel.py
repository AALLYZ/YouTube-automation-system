from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import ApprovalMode, PrivacyStatus


class ChannelSettingsIn(BaseModel):
    approval_mode: Optional[ApprovalMode] = None
    automation_enabled: Optional[bool] = None
    daily_video_limit: Optional[int] = Field(None, ge=0, le=50)
    publish_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    privacy_default: Optional[PrivacyStatus] = None
    allow_unverified_media: Optional[bool] = None
    notify_events: Optional[list[str]] = None
    topic_ai: Optional[dict] = None
    script_ai: Optional[dict] = None
    research_cfg: Optional[dict] = None
    voice_cfg: Optional[dict] = None
    visual_cfg: Optional[dict] = None
    thumbnail_cfg: Optional[dict] = None
    youtube_cfg: Optional[dict] = None
    whatsapp_cfg: Optional[dict] = None
    scoring_weights: Optional[dict] = None


class ChannelSettingsOut(BaseModel):
    approval_mode: ApprovalMode
    automation_enabled: bool
    daily_video_limit: int
    publish_time: str
    privacy_default: PrivacyStatus
    allow_unverified_media: bool
    notify_events: list[str]
    topic_ai: dict
    script_ai: dict
    research_cfg: dict
    voice_cfg: dict
    visual_cfg: dict
    thumbnail_cfg: dict
    youtube_cfg: dict
    whatsapp_cfg: dict
    scoring_weights: dict

    class Config:
        from_attributes = True


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=120)
    niche: str = ""
    audience: str = ""
    language: str = "English"
    tone: str = ""
    content_style: str = ""
    video_length_min: int = Field(8, ge=1, le=180)
    posting_frequency: str = "daily"
    timezone: str = "UTC"


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    niche: Optional[str] = None
    audience: Optional[str] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    content_style: Optional[str] = None
    video_length_min: Optional[int] = Field(None, ge=1, le=180)
    posting_frequency: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class ChannelOut(BaseModel):
    id: int
    name: str
    slug: str
    niche: str
    audience: str
    language: str
    tone: str
    content_style: str
    video_length_min: int
    posting_frequency: str
    timezone: str
    is_active: bool
    settings: Optional[ChannelSettingsOut] = None

    class Config:
        from_attributes = True
