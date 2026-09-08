"""Artifact retention: delete media for terminal jobs older than N days.

DB rows (jobs, steps, usage, metadata) are kept for history/analytics — only the
heavy storage artifacts are removed. `jobs.artifacts_pruned_at` makes it idempotent.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobStatus
from app.core.logging import get_logger
from app.models.job import Job
from app.providers.registry import get_storage
from app.services.events import record_event

log = get_logger("retention")

_TERMINAL = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
_PREFIXES = ("voiceovers", "visuals", "subtitles", "videos", "thumbnails")


def _cutoff(days: int) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)


def prune_artifacts(
    db: Session, *, days: Optional[int] = None, dry_run: bool = False, limit: int = 500
) -> dict:
    days = settings.artifact_retention_days if days is None else days
    cutoff = _cutoff(days)
    storage = get_storage()

    jobs = db.execute(
        select(Job)
        .where(
            Job.status.in_(_TERMINAL),
            Job.artifacts_pruned_at.is_(None),
            or_(Job.finished_at < cutoff, Job.finished_at.is_(None)),
            Job.created_at < cutoff,
        )
        .order_by(Job.id)
        .limit(limit)
    ).scalars().all()

    removed_files = 0
    pruned: list[str] = []
    for job in jobs:
        if dry_run:
            pruned.append(job.public_id)
            continue
        for prefix in _PREFIXES:
            try:
                removed_files += storage.delete_prefix(f"{prefix}/{job.id}")
            except NotImplementedError:
                log.warning("storage %s has no delete_prefix; skipping retention", storage.name)
                return {"days": days, "error": "storage backend does not support deletion"}
        job.artifacts_pruned_at = dt.datetime.now(dt.timezone.utc)
        pruned.append(job.public_id)
        record_event(db, level="INFO", event="retention.pruned", job_id=job.id,
                     message=f"artifacts removed (>{days}d old)")

    if not dry_run:
        db.commit()

    log.info("retention: %s %d job(s), %d file(s)", "would prune" if dry_run else "pruned",
             len(pruned), removed_files)
    return {
        "days": days,
        "cutoff": cutoff.isoformat(),
        "dry_run": dry_run,
        "jobs": pruned,
        "job_count": len(pruned),
        "files_removed": removed_files,
    }


def _main() -> None:
    import argparse

    from app.core.logging import configure_logging
    from app.db.base import SessionLocal

    configure_logging()
    ap = argparse.ArgumentParser(description="Prune old job artifacts")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        result = prune_artifacts(db, days=args.days, dry_run=args.dry_run)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    _main()
