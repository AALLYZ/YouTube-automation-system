from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalMode, PrivacyStatus
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    niche: Mapped[str] = mapped_column(String(200), default="")
    audience: Mapped[str] = mapped_column(String(300), default="")
    language: Mapped[str] = mapped_column(String(40), default="English")
    tone: Mapped[str] = mapped_column(String(120), default="")
    content_style: Mapped[str] = mapped_column(String(120), default="")
    video_length_min: Mapped[int] = mapped_column(default=8)
    posting_frequency: Mapped[str] = mapped_column(String(40), default="daily")
    timezone: Mapped[str] = mapped_column(String(60), default="UTC")
    is_active: Mapped[bool] = mapped_column(default=True)

    settings: Mapped["ChannelSettings"] = relationship(
        back_populates="channel", uselist=False, cascade="all, delete-orphan"
    )
    youtube_credential: Mapped[Optional["YouTubeCredential"]] = relationship(
        back_populates="channel", uselist=False, cascade="all, delete-orphan"
    )


class ChannelSettings(Base, TimestampMixin):
    __tablename__ = "channel_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), unique=True
    )

    approval_mode: Mapped[ApprovalMode] = mapped_column(
        enum_col(ApprovalMode), default=ApprovalMode.APPROVAL_REQUIRED
    )
    automation_enabled: Mapped[bool] = mapped_column(default=False)
    daily_video_limit: Mapped[int] = mapped_column(default=1)
    publish_time: Mapped[str] = mapped_column(String(5), default="10:00")
    privacy_default: Mapped[PrivacyStatus] = mapped_column(
        enum_col(PrivacyStatus), default=PrivacyStatus.PRIVATE
    )
    allow_unverified_media: Mapped[bool] = mapped_column(default=False)
    notify_events: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)),
        default=lambda: ["job_started", "video_ready", "published", "error"],
    )

    # per-domain config blobs (see docs/ENVIRONMENT + AI SETTINGS PANEL)
    topic_ai: Mapped[dict] = mapped_column(JSONB, default=dict)
    script_ai: Mapped[dict] = mapped_column(JSONB, default=dict)
    research_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    voice_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    visual_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    thumbnail_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    youtube_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    whatsapp_cfg: Mapped[dict] = mapped_column(JSONB, default=dict)
    scoring_weights: Mapped[dict] = mapped_column(JSONB, default=dict)

    channel: Mapped[Channel] = relationship(back_populates="settings")


class YouTubeCredential(Base, TimestampMixin):
    __tablename__ = "youtube_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), unique=True
    )
    youtube_channel_id: Mapped[Optional[str]] = mapped_column(String(80))
    channel_title: Mapped[Optional[str]] = mapped_column(String(200))
    access_token_enc: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text)
    token_expiry: Mapped[Optional[dt.datetime]] = mapped_column()
    scopes: Mapped[Optional[str]] = mapped_column(Text)
    connected_at: Mapped[Optional[dt.datetime]] = mapped_column()

    channel: Mapped[Channel] = relationship(back_populates="youtube_credential")


ChannelSettings.__table_args__ = (
    UniqueConstraint("channel_id", name="uq_channel_settings_channel_id"),
)
