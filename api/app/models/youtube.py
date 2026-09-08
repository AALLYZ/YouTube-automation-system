from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PrivacyStatus, UploadStatus
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class YoutubeUpload(Base, TimestampMixin):
    __tablename__ = "youtube_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    category_id: Mapped[str] = mapped_column(String(10), default="27")
    playlist_id: Mapped[Optional[str]] = mapped_column(String(80))
    chapters: Mapped[list] = mapped_column(JSONB, default=list)
    title_options: Mapped[list] = mapped_column(JSONB, default=list)

    privacy_status: Mapped[PrivacyStatus] = mapped_column(
        enum_col(PrivacyStatus), default=PrivacyStatus.PRIVATE
    )
    scheduled_publish_at: Mapped[Optional[dt.datetime]] = mapped_column()

    youtube_video_id: Mapped[Optional[str]] = mapped_column(String(40))
    youtube_url: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[UploadStatus] = mapped_column(enum_col(UploadStatus), default=UploadStatus.DRAFT)
    published_at: Mapped[Optional[dt.datetime]] = mapped_column()
    quota_units_used: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
