from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalMode, JobStatus, JobStepStatus, Stage
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_channel_status", "channel_id", "status"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    mode: Mapped[ApprovalMode] = mapped_column(enum_col(ApprovalMode), default=ApprovalMode.APPROVAL_REQUIRED)
    test_run: Mapped[bool] = mapped_column(default=False)
    status: Mapped[JobStatus] = mapped_column(enum_col(JobStatus), default=JobStatus.QUEUED)
    current_stage: Mapped[Stage] = mapped_column(enum_col(Stage), default=Stage.TOPIC)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)

    topic_id: Mapped[Optional[int]] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    preset_topic_id: Mapped[Optional[int]] = mapped_column(Integer)

    error_code: Mapped[Optional[str]] = mapped_column(String(40))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    total_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    total_duration_sec: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column()
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column()
    artifacts_pruned_at: Mapped[Optional[dt.datetime]] = mapped_column()

    steps: Mapped[list["JobStep"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStep.id"
    )


class JobStep(Base, TimestampMixin):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "stage", "attempt", name="uq_job_steps_job_id_stage_attempt"),
        Index("ix_job_steps_job_stage", "job_id", "stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    stage: Mapped[Stage] = mapped_column(enum_col(Stage))
    status: Mapped[JobStepStatus] = mapped_column(enum_col(JobStepStatus), default=JobStepStatus.PENDING)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    input: Mapped[Optional[dict]] = mapped_column(JSONB)
    output: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_code: Mapped[Optional[str]] = mapped_column(String(40))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(default=True)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column()
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column()
    duration_sec: Mapped[Optional[float]] = mapped_column(Float)

    job: Mapped[Job] = relationship(back_populates="steps")
