"""APScheduler automation: one daily tick per channel that creates + starts jobs.

Dedup is a unique `scheduler_runs(channel_id, run_date)` row — a second tick on
the same day is a no-op even across processes.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobStatus
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.channel import Channel
from app.models.job import Job
from app.models.ops import SchedulerRun
from app.workflows import controller

log = get_logger("scheduler")

_scheduler = None  # APScheduler instance when running


def _jobs_today(db: Session, channel_id: int, day: dt.date) -> int:
    start = dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return int(
        db.execute(
            select(func.count(Job.id)).where(
                Job.channel_id == channel_id,
                Job.created_at >= start,
                Job.created_at < end,
                Job.status != JobStatus.CANCELLED,
            )
        ).scalar_one()
    )


def tick_channel(db: Session, channel: Channel, *, day: Optional[dt.date] = None, force: bool = False) -> dict:
    """Create up to the channel's daily limit of jobs for `day`. Idempotent per day."""
    day = day or dt.datetime.now(dt.timezone.utc).date()
    s = channel.settings
    if not force and not (s and s.automation_enabled and channel.is_active):
        return {"channel_id": channel.id, "skipped": "automation disabled"}

    lock_key = f"sched:{channel.id}:{day.isoformat()}"
    run = SchedulerRun(channel_id=channel.id, run_date=day, lock_key=lock_key)
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"channel_id": channel.id, "skipped": "already ran today"}

    limit = (s.daily_video_limit if s else settings.daily_video_limit) or 0
    existing = _jobs_today(db, channel.id, day)
    to_create = max(0, limit - existing)

    created: list[str] = []
    mode = s.approval_mode if s else None
    for _ in range(to_create):
        job = controller.create(db, channel=channel, mode=mode, test_run=False)
        created.append(job.public_id)
        db.commit()
        try:
            controller.start(db, job)
        except Exception as exc:  # noqa: BLE001 - one bad job must not abort the tick
            log.warning("scheduler could not start %s: %s", job.public_id, exc)

    run = db.get(SchedulerRun, run.id)
    run.jobs_created = len(created)
    run.status = "ok"
    db.commit()
    log.info("scheduler tick channel %s: created %d job(s)", channel.id, len(created))
    return {"channel_id": channel.id, "created": created, "already_had": existing, "limit": limit}


def tick_all(db: Session, *, force: bool = False) -> list[dict]:
    channels = db.execute(select(Channel)).scalars().all()
    return [tick_channel(db, ch, force=force) for ch in channels]


def _scheduled_tick(channel_id: int) -> None:
    db = SessionLocal()
    try:
        ch = db.get(Channel, channel_id)
        if ch:
            tick_channel(db, ch)
    except Exception:  # noqa: BLE001
        log.exception("scheduled tick failed for channel %s", channel_id)
    finally:
        db.close()


def _scheduled_retention() -> None:
    from app.services.retention import prune_artifacts

    db = SessionLocal()
    try:
        prune_artifacts(db)
    except Exception:  # noqa: BLE001
        log.exception("scheduled retention run failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None or not settings.scheduler_enabled:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _scheduler = BackgroundScheduler(timezone="UTC")
    db = SessionLocal()
    try:
        channels = db.execute(select(Channel).where(Channel.is_active.is_(True))).scalars().all()
        for ch in channels:
            if not (ch.settings and ch.settings.automation_enabled):
                continue
            hh, mm = (ch.settings.publish_time or "10:00").split(":")
            _scheduler.add_job(
                _scheduled_tick,
                CronTrigger(hour=int(hh), minute=int(mm)),
                args=[ch.id],
                id=f"tick-channel-{ch.id}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
    finally:
        db.close()

    _scheduler.add_job(
        _scheduled_retention,
        CronTrigger(hour=3, minute=30),
        id="artifact-retention",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    log.info("APScheduler started with %d job(s)", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
