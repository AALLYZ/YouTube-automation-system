"""Media sub-pipeline orchestration (voice → visuals → subtitles → timeline → render)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import Stage
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Script
from app.models.job import Job
from app.models.ops import ApiUsage
from app.services.jobs import fail_step, finish_step, start_step
from app.services.render import run_render
from app.services.subtitles import run_subtitles
from app.services.timeline import run_timeline
from app.services.visuals import run_visuals
from app.services.voice import run_voice
from app.core.errors import AppError

log = get_logger("media")

MEDIA_STAGES = ("voice", "visuals", "subtitles", "timeline", "render")


def _script_for_job(db: Session, job: Job) -> Script:
    script = db.execute(
        select(Script).where(Script.job_id == job.id).order_by(Script.id.desc())
    ).scalars().first()
    if not script:
        raise AppError("Job has no script yet; run scripts:draft first", code="VALIDATION")
    return script


def run_media_stage(db: Session, job: Job, channel: Channel, stage: str) -> dict:
    settings_row = channel.settings
    aspect = (settings_row.visual_cfg or {}).get("aspect_ratio", "16:9") if settings_row else "16:9"
    script = _script_for_job(db, job)

    step_stage = {
        "voice": Stage.VOICE,
        "visuals": Stage.VISUALS,
        "subtitles": Stage.SUBTITLES,
        "timeline": Stage.TIMELINE,
        "render": Stage.RENDER,
    }[stage]
    step = start_step(db, job, step_stage)
    try:
        if stage == "voice":
            vo = run_voice(db, script=script, job_id=job.id,
                           voice_cfg=(settings_row.voice_cfg if settings_row else {}))
            out = {"duration_sec": vo.duration_sec, "provider": vo.provider}
        elif stage == "visuals":
            assets = run_visuals(db, job_id=job.id, script_id=script.id, aspect=aspect,
                                 visual_cfg=(settings_row.visual_cfg if settings_row else {}))
            out = {"assets": len(assets),
                   "unverified": sum(1 for a in assets if not a.rights_verified)}
        elif stage == "subtitles":
            out = run_subtitles(db, job_id=job.id, script_id=script.id)
        elif stage == "timeline":
            vp = run_timeline(
                db, job_id=job.id, script_id=script.id, aspect=aspect,
                allow_unverified_media=bool(settings_row and settings_row.allow_unverified_media),
                music_cfg=(settings_row.visual_cfg if settings_row else {}),
            )
            out = {"duration_sec": vp.duration_sec, "resolution": vp.resolution}
        elif stage == "render":
            vcfg = (settings_row.visual_cfg or {}) if settings_row else {}
            vp = run_render(db, job_id=job.id,
                            burn_subtitles=bool(vcfg.get("burn_subtitles", True)),
                            branding_text=vcfg.get("branding_text", ""))
            out = {"video_key": vp.video_key, "duration_sec": vp.duration_sec, "size_bytes": vp.size_bytes}
        else:  # pragma: no cover
            raise AppError(f"Unknown media stage {stage}", code="VALIDATION")
    except AppError as exc:
        from app.core.errors import RETRYABLE_CODES

        code = getattr(exc, "code", "UNKNOWN")
        fail_step(db, step, code=code, message=exc.message, retryable=code in RETRYABLE_CODES)
        job.status = "FAILED"
        job.error_code = code
        job.error_message = exc.message
        db.commit()
        raise

    finish_step(db, step, output=out)
    job.current_stage = step_stage
    job.total_cost_usd = db.execute(
        select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0)).where(ApiUsage.job_id == job.id)
    ).scalar_one()
    db.commit()
    log.info("media stage %s done for %s: %s", stage, job.public_id, out)
    return out


def run_media_pipeline(db: Session, job: Job, channel: Channel) -> dict:
    results = {}
    for stage in MEDIA_STAGES:
        results[stage] = run_media_stage(db, job, channel, stage)
    return results
