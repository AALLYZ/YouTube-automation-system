"""RQ task functions. Kept thin: open a session, run the pipeline, close."""
from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.db.base import SessionLocal
from app.workflows.pipeline import run_pipeline

log = get_logger("worker.task")


def run_pipeline_task(job_id: int) -> dict:
    configure_logging()
    db = SessionLocal()
    try:
        job = run_pipeline(db, job_id)
        return {"job_id": job_id, "status": job.status.value, "stage": job.current_stage.value}
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("pipeline task crashed for job %s", job_id)
        raise
    finally:
        db.close()
