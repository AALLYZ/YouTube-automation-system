from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AspectRatio, AssetSource, MusicSource, VideoStatus
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class Voiceover(Base, TimestampMixin):
    __tablename__ = "voiceovers"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    script_version_id: Mapped[int] = mapped_column(ForeignKey("script_versions.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(40))
    voice: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(40), default="English")
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    emotion: Mapped[str] = mapped_column(String(40), default="neutral")
    duration_sec: Mapped[float] = mapped_column(Float, default=0)
    audio_key: Mapped[str] = mapped_column(String(400))
    timestamps_key: Mapped[Optional[str]] = mapped_column(String(400))
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)


class VisualAsset(Base, TimestampMixin):
    __tablename__ = "visual_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("video_scenes.id", ondelete="CASCADE"))
    asset_type: Mapped[str] = mapped_column(String(20), default="image")  # image | video
    source: Mapped[AssetSource] = mapped_column(enum_col(AssetSource), default=AssetSource.AI_IMAGE)
    prompt: Mapped[str] = mapped_column(Text, default="")
    file_key: Mapped[str] = mapped_column(String(400))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float)
    license: Mapped[str] = mapped_column(String(200), default="")
    attribution: Mapped[str] = mapped_column(String(400), default="")
    rights_verified: Mapped[bool] = mapped_column(default=False)
    provider: Mapped[str] = mapped_column(String(40), default="stub")
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)


class MusicTrack(Base, TimestampMixin):
    __tablename__ = "music_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source: Mapped[MusicSource] = mapped_column(enum_col(MusicSource), default=MusicSource.NONE)
    file_key: Mapped[Optional[str]] = mapped_column(String(400))
    license: Mapped[str] = mapped_column(String(200), default="")
    attribution: Mapped[str] = mapped_column(String(400), default="")
    duck_level_pct: Mapped[int] = mapped_column(Integer, default=15)


class Thumbnail(Base, TimestampMixin):
    __tablename__ = "thumbnails"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    concept: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(String(120), default="")
    composition: Mapped[str] = mapped_column(Text, default="")
    target_emotion: Mapped[str] = mapped_column(String(60), default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    file_key: Mapped[Optional[str]] = mapped_column(String(400))
    score: Mapped[float] = mapped_column(Float, default=0)
    selected: Mapped[bool] = mapped_column(default=False)
    provider: Mapped[str] = mapped_column(String(40), default="stub")
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)


class VideoProject(Base, TimestampMixin):
    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    aspect_ratio: Mapped[AspectRatio] = mapped_column(
        enum_col(AspectRatio), default=AspectRatio.WIDESCREEN
    )
    resolution: Mapped[str] = mapped_column(String(20), default="1920x1080")
    timeline_key: Mapped[Optional[str]] = mapped_column(String(400))
    video_key: Mapped[Optional[str]] = mapped_column(String(400))
    duration_sec: Mapped[float] = mapped_column(Float, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    has_subtitles: Mapped[bool] = mapped_column(default=False)
    music_track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("music_tracks.id", ondelete="SET NULL"))
    thumbnail_id: Mapped[Optional[int]] = mapped_column(ForeignKey("thumbnails.id", ondelete="SET NULL"))
    status: Mapped[VideoStatus] = mapped_column(enum_col(VideoStatus), default=VideoStatus.RENDERING)
    ffprobe: Mapped[Optional[dict]] = mapped_column(JSONB)
