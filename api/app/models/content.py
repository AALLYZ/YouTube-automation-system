from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ScriptStatus, TopicStatus, VisualType
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("channel_id", "fingerprint", name="uq_topics_channel_id_fingerprint"),
        Index("ix_topics_channel_status", "channel_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL", use_alter=True, name="fk_topics_job_id_jobs")
    )

    title: Mapped[str] = mapped_column(String(300))
    hook: Mapped[str] = mapped_column(Text, default="")
    angle: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(300), default="")

    estimated_interest: Mapped[float] = mapped_column(Float, default=0)
    uniqueness_score: Mapped[float] = mapped_column(Float, default=0)
    difficulty: Mapped[float] = mapped_column(Float, default=0)
    search_potential: Mapped[float] = mapped_column(Float, default=0)
    retention_potential: Mapped[float] = mapped_column(Float, default=0)
    competition: Mapped[float] = mapped_column(Float, default=0)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    evergreen: Mapped[bool] = mapped_column(default=True)

    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[TopicStatus] = mapped_column(enum_col(TopicStatus), default=TopicStatus.GENERATED)
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text)


class Research(Base, TimestampMixin):
    __tablename__ = "research"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(40), default="stub")
    summary: Mapped[str] = mapped_column(Text, default="")
    facts: Mapped[list] = mapped_column(JSONB, default=list)
    opinions: Mapped[list] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list)
    sources: Mapped[list] = mapped_column(JSONB, default=list)


class Script(Base, TimestampMixin):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    status: Mapped[ScriptStatus] = mapped_column(enum_col(ScriptStatus), default=ScriptStatus.DRAFT)
    target_duration_sec: Mapped[int] = mapped_column(Integer, default=480)
    tone: Mapped[str] = mapped_column(String(120), default="")
    style: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(40), default="English")
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    qa_score: Mapped[Optional[float]] = mapped_column(Float)


class ScriptVersion(Base, TimestampMixin):
    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("script_id", "version", name="uq_script_versions_script_id_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    body_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    est_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    qa_result: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(String(20), default="ai")  # ai | revision | human


class VideoScene(Base, TimestampMixin):
    __tablename__ = "video_scenes"
    __table_args__ = (Index("ix_video_scenes_job_scene", "job_id", "scene_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    scene_index: Mapped[int] = mapped_column(Integer)
    narration: Mapped[str] = mapped_column(Text, default="")
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    visual_type: Mapped[VisualType] = mapped_column(enum_col(VisualType), default=VisualType.IMAGE)
    planned_duration_sec: Mapped[float] = mapped_column(Float, default=6)
    actual_duration_sec: Mapped[Optional[float]] = mapped_column(Float)
    transition: Mapped[str] = mapped_column(String(40), default="fade")
    caption_text: Mapped[str] = mapped_column(Text, default="")
