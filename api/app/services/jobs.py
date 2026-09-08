"""Job lifecycle helpers (shared by dev endpoints now, the controller in Phase 7)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ApprovalMode, JobStatus, Stage
from app.models.channel import Channel
from app.models.job import Job, JobStep


def new_public_id(db: Session) -> str:
    year = dt.date.today().year
    count = db.execute(
        select(func.count(Job.id)).where(func.extract("year", Job.created_at) == year)
    ).scalar_one()
    return f"job_{year}_{count + 1:05d}"


def create_job(
    db: Session,
    *,
    channel: Channel,
    mode: ApprovalMode | None = None,
    test_run: bool = False,
    topic_id: int | None = None,
) -> Job:
    job = Job(
        public_id=new_public_id(db),
        channel_id=channel.id,
        mode=mode or (channel.settings.approval_mode if channel.settings else ApprovalMode.APPROVAL_REQUIRED),
        test_run=test_run,
        status=JobStatus.QUEUED,
        current_stage=Stage.TOPIC,
        topic_id=topic_id,
    )
    db.add(job)
    db.flush()
    return job


def start_step(db: Session, job: Job, stage: Stage, *, attempt: int = 1, max_attempts: int = 3) -> JobStep:
    step = JobStep(
        job_id=job.id,
        stage=stage,
        status="RUNNING",
        attempt=attempt,
        max_attempts=max_attempts,
        started_at=dt.datetime.now(dt.timezone.utc),
    )
    job.current_stage = stage
    job.status = JobStatus.RUNNING
    if job.started_at is None:
        job.started_at = dt.datetime.now(dt.timezone.utc)
    db.add(step)
    db.flush()
    return step


def finish_step(db: Session, step: JobStep, *, output: dict | None = None) -> None:
    step.status = "SUCCEEDED"
    step.output = output
    step.finished_at = dt.datetime.now(dt.timezone.utc)
    if step.started_at:
        step.duration_sec = (step.finished_at - step.started_at).total_seconds()
    db.flush()


def fail_step(db: Session, step: JobStep, *, code: str, message: str, retryable: bool) -> None:
    step.status = "FAILED"
    step.error_code = code
    step.error_message = message
    step.retryable = retryable
    step.finished_at = dt.datetime.now(dt.timezone.utc)
    if step.started_at:
        step.duration_sec = (step.finished_at - step.started_at).total_seconds()
    db.flush()
