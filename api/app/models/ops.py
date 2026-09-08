from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import NotificationEvent, NotificationStatus
from app.db.base import Base, TimestampMixin
from app.models._common import enum_col


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("job_id", "event", name="uq_notifications_job_id_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    event: Mapped[NotificationEvent] = mapped_column(enum_col(NotificationEvent))
    provider: Mapped[str] = mapped_column(String(40), default="console")
    recipient: Mapped[str] = mapped_column(String(120), default="")
    template: Mapped[str] = mapped_column(String(60), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[NotificationStatus] = mapped_column(
        enum_col(NotificationStatus), default=NotificationStatus.QUEUED
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(120))
    error: Mapped[Optional[str]] = mapped_column(Text)
    delivered_at: Mapped[Optional[dt.datetime]] = mapped_column()


class ApiUsage(Base, TimestampMixin):
    __tablename__ = "api_usage"
    __table_args__ = (
        Index("ix_api_usage_job", "job_id"),
        Index("ix_api_usage_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    stage: Mapped[Optional[str]] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[Optional[str]] = mapped_column(String(80))
    operation: Mapped[str] = mapped_column(String(60), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    units: Mapped[int] = mapped_column(Integer, default=0)
    seconds: Mapped[float] = mapped_column(Float, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)


class SystemLog(Base, TimestampMixin):
    __tablename__ = "system_logs"
    __table_args__ = (
        Index("ix_system_logs_job_created", "job_id", "created_at"),
        Index("ix_system_logs_level_created", "level", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    stage: Mapped[Optional[str]] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(80), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[Optional[dict]] = mapped_column(JSONB)


class SchedulerRun(Base, TimestampMixin):
    __tablename__ = "scheduler_runs"
    __table_args__ = (
        UniqueConstraint("channel_id", "run_date", name="uq_scheduler_runs_channel_id_run_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    run_date: Mapped[dt.date] = mapped_column(Date)
    lock_key: Mapped[str] = mapped_column(String(120), unique=True)
    jobs_created: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
