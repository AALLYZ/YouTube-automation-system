from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.enums import Stage, TopicStatus
from app.core.errors import AppError, NotFoundError
from app.models.content import Research, Script, ScriptVersion, Topic, VideoScene
from app.models.job import Job
from app.models.ops import ApiUsage
from app.models.user import User
from app.schemas.script import (
    DraftScriptRequest,
    DraftScriptResponse,
    SceneOut,
    ScriptOut,
    ScriptVersionOut,
)
from app.services.jobs import create_job, finish_step, start_step
from app.services.research import run_research
from app.services.script import generate_script
from app.services.script_qa import run_script_qa

router = APIRouter(tags=["scripts"])


@router.post("/channels/{channel_id}/scripts:draft", response_model=DraftScriptResponse)
def draft_script(
    channel_id: int,
    payload: DraftScriptRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.channel import Channel

    channel = db.get(Channel, channel_id)
    if not channel:
        raise NotFoundError("Channel not found")
    topic = db.get(Topic, payload.topic_id)
    if not topic or topic.channel_id != channel_id:
        raise NotFoundError("Topic not found for this channel")

    target = payload.target_duration_sec or channel.video_length_min * 60
    tone = payload.tone or channel.tone or "informative"
    style = payload.style or channel.content_style or "explainer"

    try:
        job = create_job(db, channel=channel, test_run=payload.test_run, topic_id=topic.id)
        topic.job_id = job.id
        topic.status = TopicStatus.USED

        step = start_step(db, job, Stage.RESEARCH)
        research: Research | None = run_research(
            db, topic=topic, job_id=job.id, enabled=payload.research_enabled
        )
        finish_step(db, step, output={"sources": len(research.sources)})

        step = start_step(db, job, Stage.SCRIPT)
        script, _version = generate_script(
            db,
            topic=topic,
            job_id=job.id,
            research=research,
            target_duration_sec=target,
            tone=tone,
            style=style,
            language=channel.language,
        )
        finish_step(db, step, output={"version": script.current_version})

        step = start_step(db, job, Stage.SCRIPT_QA)
        qa = run_script_qa(db, script=script, job_id=job.id, research=research)
        finish_step(db, step, output=qa)

        job.current_stage = Stage.SCRIPT_QA
        job.total_cost_usd = db.execute(
            select(func.coalesce(func.sum(ApiUsage.est_cost_usd), 0.0)).where(ApiUsage.job_id == job.id)
        ).scalar_one()
        db.commit()
    except AppError:
        db.rollback()
        raise

    return DraftScriptResponse(
        job_public_id=job.public_id,
        script=_script_out(db, script.id),
        qa=qa,
    )


@router.get("/scripts/{script_id}", response_model=ScriptOut)
def get_script(script_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _script_out(db, script_id)


def _script_out(db: Session, script_id: int) -> ScriptOut:
    script = db.get(Script, script_id)
    if not script:
        raise NotFoundError("Script not found")
    versions = (
        db.execute(
            select(ScriptVersion)
            .where(ScriptVersion.script_id == script_id)
            .order_by(ScriptVersion.version)
        )
        .scalars()
        .all()
    )
    scenes = (
        db.execute(
            select(VideoScene)
            .where(VideoScene.script_id == script_id)
            .order_by(VideoScene.scene_index)
        )
        .scalars()
        .all()
    )
    out = ScriptOut.model_validate(script)
    out.versions = [ScriptVersionOut.model_validate(v) for v in versions]
    out.scenes = [SceneOut.model_validate(s) for s in scenes]
    return out
