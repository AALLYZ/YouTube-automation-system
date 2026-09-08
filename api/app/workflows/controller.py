"""AutomationController: create jobs, start/resume runs, handle approval actions."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ApprovalMode, JobStatus, Stage
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.job import Job, JobStep
from app.services.jobs import create_job
from app.workflows.pipeline import run_pipeline

log = get_logger("controller")

_TERMINAL = {JobStatus.COMPLETED, JobStatus.CANCELLED}


def running_job_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(Job.id)).where(Job.status == JobStatus.RUNNING)
        ).scalar_one()
    )


def create(
    db: Session,
    *,
    channel: Channel,
    mode: Optional[ApprovalMode] = None,
    test_run: bool = False,
    topic_id: Optional[int] = None,
) -> Job:
    job = create_job(db, channel=channel, mode=mode, test_run=test_run, topic_id=topic_id)
    db.flush()
    log.info("created job %s (mode=%s, test=%s)", job.public_id, job.mode, test_run)
    return job


def start(db: Session, job: Job, *, async_: Optional[bool] = None) -> Job:
    """Run (or enqueue) the pipeline for a job. Inline unless async is requested."""
    if job.status in _TERMINAL:
        raise AppError(f"Job {job.public_id} is {job.status.value}", code=ErrorCode.VALIDATION)

    want_async = settings.jobs_async if async_ is None else async_
    if want_async:
        from app.workers.queue import enqueue_pipeline

        job.status = JobStatus.QUEUED
        db.commit()
        enqueue_pipeline(job.id)
        log.info("enqueued job %s", job.public_id)
        return job

    # inline execution is synchronous within the caller; the concurrency cap
    # only governs how many pipeline runs the async workers pick up at once.
    return run_pipeline(db, job.id)


def approve(db: Session, job: Job, *, by: str = "admin") -> Job:
    if job.status != JobStatus.WAITING_APPROVAL:
        raise AppError(f"Job {job.public_id} is not awaiting approval", code=ErrorCode.VALIDATION)
    attempt = (
        int(
            db.execute(
                select(func.count(JobStep.id)).where(
                    JobStep.job_id == job.id, JobStep.stage == Stage.APPROVAL_GATE
                )
            ).scalar_one()
        )
        + 1
    )
    now = dt.datetime.now(dt.timezone.utc)
    db.add(
        JobStep(
            job_id=job.id,
            stage=Stage.APPROVAL_GATE,
            status="SUCCEEDED",
            attempt=attempt,
            max_attempts=1,
            output={"approved_by": by},
            started_at=now,
            finished_at=now,
            duration_sec=0.0,
        )
    )
    job.status = JobStatus.QUEUED
    job.error_code = None
    job.error_message = None
    db.commit()
    log.info("job %s approved by %s", job.public_id, by)
    return run_pipeline(db, job.id)


def reject(db: Session, job: Job, *, reason: str = "") -> Job:
    if job.status not in (JobStatus.WAITING_APPROVAL, JobStatus.FAILED):
        raise AppError(f"Job {job.public_id} cannot be rejected from {job.status.value}", code=ErrorCode.VALIDATION)
    job.status = JobStatus.CANCELLED
    job.error_message = f"Rejected: {reason}" if reason else "Rejected"
    db.commit()
    log.info("job %s rejected", job.public_id)
    return job


def cancel(db: Session, job: Job) -> Job:
    if job.status in _TERMINAL:
        raise AppError(f"Job {job.public_id} is already {job.status.value}", code=ErrorCode.VALIDATION)
    job.status = JobStatus.CANCELLED
    db.commit()
    log.info("job %s cancelled", job.public_id)
    return job


def retry(db: Session, job: Job, *, async_: Optional[bool] = None) -> Job:
    if job.status != JobStatus.FAILED:
        raise AppError(f"Only FAILED jobs can be retried (job is {job.status.value})", code=ErrorCode.VALIDATION)
    job.status = JobStatus.QUEUED
    job.error_code = None
    job.error_message = None
    db.commit()
    log.info("retrying job %s from stage %s", job.public_id, job.current_stage.value)
    return start(db, job, async_=async_)
