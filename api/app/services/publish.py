"""Publish sub-pipeline orchestration (thumbnail -> metadata -> upload)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import Stage
from app.core.errors import RETRYABLE_CODES
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.job import Job
from app.models.ops import ApiUsage
from app.services.jobs import fail_step, finish_step, start_step
from app.services.media import _script_for_job
from app.services.metadata import run_metadata
from app.services.thumbnail import run_thumbnail
from app.services.upload import run_upload
from app.core.errors import AppError

log = get_logger("publish")

PUBLISH_STAGES = ("thumbnail", "metadata", "upload")

_STAGE_ENUM = {
    "thumbnail": Stage.THUMBNAIL,
    "metadata": Stage.METADATA,
    "upload": Stage.UPLOAD,
}


def run_publish_stage(db: Session, job: Job, channel: Channel, stage: str) -> dict:
    if stage not in PUBLISH_STAGES:
        raise AppError(f"Unknown publish stage {stage}", code="VALIDATION")
    script = _script_for_job(db, job)
    step = start_step(db, job, _STAGE_ENUM[stage])
    try:
        if stage == "thumbnail":
            rows = run_thumbnail(db, job_id=job.id, channel=channel, script=script)
            selected = next((r for r in rows if r.selected), None)
            out = {
                "concepts": len(rows),
                "selected_score": selected.score if selected else None,
                "selected_key": selected.file_key if selected else None,
            }
        elif stage == "metadata":
            row = run_metadata(db, job_id=job.id, channel=channel, script=script)
            out = {
                "title": row.title,
                "title_options": len(row.title_options or []),
                "tags": len(row.tags or []),
                "chapters": len(row.chapters or []),
                "privacy_status": row.privacy_status.value,
            }
        else:  # upload
            out = run_upload(db, job=job, channel=channel)
    except AppError as exc:
        code = getattr(exc, "code", "UNKNOWN")
        fail_step(db, step, code=code, message=exc.message, retryable=code in RETRYABLE_CODES)
        job.status = "FAILED"
        job.error_code = code
        job.error_message = exc.message
        db.commit()
        raise

    finish_step(db, step, output=out)
    job.current_stage = _STAGE_ENUM[stage]
    job.total_cost_usd = db.execute(
        select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0)).where(ApiUsage.job_id == job.id)
    ).scalar_one()
    db.commit()
    log.info("publish stage %s done for %s: %s", stage, job.public_id, out)
    return out


def run_publish_pipeline(db: Session, job: Job, channel: Channel) -> dict:
    return {s: run_publish_stage(db, job, channel, s) for s in PUBLISH_STAGES}
