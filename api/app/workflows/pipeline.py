"""The pipeline: ordered stages, resume-from-stage, per-stage retry/backoff.

Stage handlers call the pure stage *services* (which write artifacts + rows but
do not manage `job_steps`); this module owns the step lifecycle, retries, the
approval gate, progress, cost roll-up, and start/finish notifications.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobStatus, NotificationEvent, Stage
from app.core.errors import RETRYABLE_CODES, AppError, StageError
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Research, Script, Topic
from app.models.job import Job, JobStep
from app.models.ops import ApiUsage
from app.services.events import record_event
from app.services.final_qa import run_final_qa
from app.services.jobs import fail_step, finish_step, start_step
from app.services.media import _script_for_job
from app.services.metadata import run_metadata
from app.services.notifications import safe_notify
from app.services.render import run_render
from app.services.research import run_research
from app.services.script import generate_script
from app.services.script_qa import run_script_qa
from app.services.subtitles import run_subtitles
from app.services.thumbnail import run_thumbnail
from app.services.timeline import run_timeline
from app.services.topics import generate_topics, pick_best_topic
from app.services.upload import run_upload
from app.services.visuals import run_visuals
from app.services.voice import run_voice

log = get_logger("pipeline")


class _Paused(Exception):
    """Raised by the approval gate to stop the run without failing the job."""


STAGE_ORDER: list[Stage] = [
    Stage.TOPIC,
    Stage.RESEARCH,
    Stage.SCRIPT,
    Stage.SCRIPT_QA,
    Stage.VOICE,
    Stage.VISUALS,
    Stage.SUBTITLES,
    Stage.TIMELINE,
    Stage.RENDER,
    Stage.THUMBNAIL,
    Stage.METADATA,
    Stage.FINAL_QA,
    Stage.APPROVAL_GATE,
    Stage.UPLOAD,
    Stage.NOTIFY,
    Stage.COMPLETE,
]


# ---------------- per-stage context ----------------
def _cfg(channel: Channel) -> dict:
    s = channel.settings
    visual = (s.visual_cfg if s else {}) or {}
    return {
        "aspect": visual.get("aspect_ratio", "16:9"),
        "voice_cfg": (s.voice_cfg if s else {}) or {},
        "visual_cfg": visual,
        "research_cfg": (s.research_cfg if s else {}) or {},
        "allow_unverified": bool(s and s.allow_unverified_media),
    }


# ---------------- stage handlers ----------------
def _stage_topic(db: Session, job: Job, channel: Channel) -> dict:
    topic = db.get(Topic, job.topic_id) if job.topic_id else None
    if topic is None:
        topic = pick_best_topic(db, channel)
    if topic is None:
        generated = generate_topics(db, channel, count=6, job_id=job.id)
        topic = generated[0] if generated else None
    if topic is None:
        raise StageError("No topic available and generation produced none", stage="TOPIC", code="VALIDATION")
    from app.core.enums import TopicStatus

    job.topic_id = topic.id
    topic.job_id = job.id
    topic.status = TopicStatus.USED
    db.flush()
    return {"topic_id": topic.id, "title": topic.title}


def _stage_research(db: Session, job: Job, channel: Channel) -> dict:
    topic = db.get(Topic, job.topic_id)
    enabled = bool(_cfg(channel)["research_cfg"].get("enabled", True))
    research = run_research(db, topic=topic, job_id=job.id, enabled=enabled)
    return {"sources": len(research.sources), "enabled": enabled}


def _stage_script(db: Session, job: Job, channel: Channel) -> dict:
    topic = db.get(Topic, job.topic_id)
    research = db.execute(
        select(Research).where(Research.job_id == job.id).order_by(Research.id.desc())
    ).scalars().first()
    target = channel.video_length_min * 60
    script, version = generate_script(
        db,
        topic=topic,
        job_id=job.id,
        research=research,
        target_duration_sec=target,
        tone=channel.tone or "informative",
        style=channel.content_style or "explainer",
        language=channel.language,
    )
    return {"version": version.version, "words": version.word_count}


def _stage_script_qa(db: Session, job: Job, channel: Channel) -> dict:
    script = _script_for_job(db, job)
    research = db.execute(
        select(Research).where(Research.job_id == job.id).order_by(Research.id.desc())
    ).scalars().first()
    result = run_script_qa(db, script=script, job_id=job.id, research=research)
    if not result.get("passed"):
        raise StageError(
            f"Script failed QA (score {result.get('score')})",
            stage="SCRIPT_QA",
            code="QA_FAILED",
            context={"issues": result.get("issues", [])},
        )
    return result


def _stage_voice(db: Session, job: Job, channel: Channel) -> dict:
    vo = run_voice(db, script=_script_for_job(db, job), job_id=job.id, voice_cfg=_cfg(channel)["voice_cfg"])
    return {"duration_sec": vo.duration_sec, "provider": vo.provider}


def _stage_visuals(db: Session, job: Job, channel: Channel) -> dict:
    c = _cfg(channel)
    assets = run_visuals(
        db, job_id=job.id, script_id=_script_for_job(db, job).id, aspect=c["aspect"], visual_cfg=c["visual_cfg"]
    )
    return {"assets": len(assets), "unverified": sum(1 for a in assets if not a.rights_verified)}


def _stage_subtitles(db: Session, job: Job, channel: Channel) -> dict:
    return run_subtitles(db, job_id=job.id, script_id=_script_for_job(db, job).id)


def _stage_timeline(db: Session, job: Job, channel: Channel) -> dict:
    c = _cfg(channel)
    vp = run_timeline(
        db,
        job_id=job.id,
        script_id=_script_for_job(db, job).id,
        aspect=c["aspect"],
        allow_unverified_media=c["allow_unverified"],
        music_cfg=c["visual_cfg"],
    )
    return {"duration_sec": vp.duration_sec, "resolution": vp.resolution}


def _stage_render(db: Session, job: Job, channel: Channel) -> dict:
    vcfg = _cfg(channel)["visual_cfg"]
    vp = run_render(
        db,
        job_id=job.id,
        burn_subtitles=bool(vcfg.get("burn_subtitles", True)),
        branding_text=vcfg.get("branding_text", ""),
    )
    out = {"video_key": vp.video_key, "duration_sec": vp.duration_sec, "size_bytes": vp.size_bytes}
    _notify(db, job, channel, NotificationEvent.VIDEO_READY, {
        "duration_min": round((vp.duration_sec or 0) / 60, 1),
        "cost_usd": _job_cost(db, job.id),
    })
    return out


def _stage_thumbnail(db: Session, job: Job, channel: Channel) -> dict:
    rows = run_thumbnail(db, job_id=job.id, channel=channel, script=_script_for_job(db, job))
    best = next((r for r in rows if r.selected), None)
    return {"concepts": len(rows), "selected_score": best.score if best else None}


def _stage_metadata(db: Session, job: Job, channel: Channel) -> dict:
    row = run_metadata(db, job_id=job.id, channel=channel, script=_script_for_job(db, job))
    return {"title": row.title, "tags": len(row.tags or []), "chapters": len(row.chapters or [])}


def _stage_final_qa(db: Session, job: Job, channel: Channel) -> dict:
    return run_final_qa(db, job_id=job.id, script=_script_for_job(db, job))


def _stage_approval_gate(db: Session, job: Job, channel: Channel) -> dict:
    # only reached when not AUTO and not yet approved -> pause (handled in _run_stage_once)
    return {"gate": "auto"}


def _stage_upload(db: Session, job: Job, channel: Channel) -> dict:
    return run_upload(db, job=job, channel=channel)


def _stage_notify(db: Session, job: Job, channel: Channel) -> dict:
    from app.models.youtube import YoutubeUpload

    row = db.execute(select(YoutubeUpload).where(YoutubeUpload.job_id == job.id)).scalar_one_or_none()
    ctx = {}
    if row:
        ctx = {
            "title": row.title,
            "youtube_url": row.youtube_url,
            "scheduled_publish_at": row.scheduled_publish_at.isoformat() if row.scheduled_publish_at else None,
        }
    n = _notify(db, job, channel, NotificationEvent.PUBLISHED, ctx)
    return {"notified": n is not None}


def _stage_complete(db: Session, job: Job, channel: Channel) -> dict:
    import datetime as dt

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    job.finished_at = dt.datetime.now(dt.timezone.utc)
    db.flush()
    return {"status": "completed"}


HANDLERS: dict[Stage, Callable[[Session, Job, Channel], dict]] = {
    Stage.TOPIC: _stage_topic,
    Stage.RESEARCH: _stage_research,
    Stage.SCRIPT: _stage_script,
    Stage.SCRIPT_QA: _stage_script_qa,
    Stage.VOICE: _stage_voice,
    Stage.VISUALS: _stage_visuals,
    Stage.SUBTITLES: _stage_subtitles,
    Stage.TIMELINE: _stage_timeline,
    Stage.RENDER: _stage_render,
    Stage.THUMBNAIL: _stage_thumbnail,
    Stage.METADATA: _stage_metadata,
    Stage.FINAL_QA: _stage_final_qa,
    Stage.APPROVAL_GATE: _stage_approval_gate,
    Stage.UPLOAD: _stage_upload,
    Stage.NOTIFY: _stage_notify,
    Stage.COMPLETE: _stage_complete,
}


# ---------------- helpers ----------------
def _job_cost(db: Session, job_id: int) -> float:
    return float(
        db.execute(
            select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0)).where(ApiUsage.job_id == job_id)
        ).scalar_one()
    )


def _notify(db, job, channel, event, context):
    ctx = dict(context or {})
    if job.topic_id:
        topic = db.get(Topic, job.topic_id)
        if topic:
            ctx.setdefault("topic", topic.title)
    return safe_notify(db, event=event, channel=channel, job=job, context=ctx)


def _attempt_count(db: Session, job_id: int, stage: Stage) -> int:
    return int(
        db.execute(
            select(func.count(JobStep.id)).where(JobStep.job_id == job_id, JobStep.stage == stage)
        ).scalar_one()
    )


def _completed_stages(job: Job) -> set[Stage]:
    return {s.stage for s in job.steps if s.status == "SUCCEEDED"}


def _run_stage_once(db: Session, job: Job, channel: Channel, stage: Stage, attempt: int) -> dict:
    from app.core.enums import ApprovalMode

    if stage == Stage.APPROVAL_GATE and job.mode != ApprovalMode.AUTO:
        job.status = JobStatus.WAITING_APPROVAL
        job.current_stage = Stage.APPROVAL_GATE
        db.commit()
        raise _Paused()

    step = start_step(db, job, stage, attempt=attempt, max_attempts=settings.max_stage_retries)
    try:
        out = HANDLERS[stage](db, job, channel)
    except AppError as exc:
        retryable = getattr(exc, "retryable", exc.code in RETRYABLE_CODES)
        fail_step(db, step, code=exc.code, message=exc.message, retryable=retryable)
        db.commit()
        raise
    out = out if isinstance(out, dict) else {"result": out}
    finish_step(db, step, output=out)
    db.commit()
    return out


# ---------------- entrypoint ----------------
def run_pipeline(
    db: Session, job_id: int, *, sleep: Optional[Callable[[float], None]] = None
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise AppError(f"Job {job_id} not found", code="NOT_FOUND")
    channel = db.get(Channel, job.channel_id)

    if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
        return job

    base = 0.0 if settings.app_env == "test" else float(settings.retry_backoff_base_sec)
    sleep_fn = sleep or time.sleep

    _notify(db, job, channel, NotificationEvent.JOB_STARTED, {"job_public_id": job.public_id})
    job.status = JobStatus.RUNNING
    db.commit()

    completed = _completed_stages(job)
    total = len(STAGE_ORDER)

    for idx, stage in enumerate(STAGE_ORDER):
        if stage in completed:
            continue

        counter = {"n": _attempt_count(db, job.id, stage)}

        def _once() -> dict:
            counter["n"] += 1
            return _run_stage_once(db, job, channel, stage, counter["n"])

        try:
            from app.workflows.retry import run_with_retry

            run_with_retry(
                _once, max_attempts=settings.max_stage_retries, base_sec=base, sleep=sleep_fn
            )
        except _Paused:
            record_event(db, level="INFO", event="job.waiting_approval", job_id=job.id,
                         stage=Stage.APPROVAL_GATE.value, message="Awaiting approval before upload")
            db.commit()
            log.info("pipeline paused for approval: job %s", job.public_id)
            return job
        except AppError as exc:
            job.status = JobStatus.FAILED
            job.error_code = exc.code
            job.error_message = exc.message
            job.current_stage = stage
            _notify(db, job, channel, NotificationEvent.ERROR, {
                "stage": stage.value, "error_code": exc.code, "error_message": exc.message,
            })
            record_event(db, level="ERROR", event=f"stage.{stage.value.lower()}.failed", job_id=job.id,
                         stage=stage.value, message=f"{exc.code}: {exc.message}",
                         context=getattr(exc, "context", None))
            db.commit()
            log.warning("pipeline failed at %s for job %s: %s", stage.value, job.public_id, exc.message)
            return job

        completed.add(stage)
        job.current_stage = stage
        job.progress_pct = int((idx + 1) / total * 100)
        job.total_cost_usd = _job_cost(db, job.id)
        record_event(db, level="INFO", event=f"stage.{stage.value.lower()}", job_id=job.id, stage=stage.value)
        db.commit()

    record_event(db, level="INFO", event="job.completed", job_id=job.id,
                 message=f"{job.total_cost_usd:.4f} USD")
    log.info("pipeline complete: job %s (%.4f USD)", job.public_id, job.total_cost_usd)
    return job
