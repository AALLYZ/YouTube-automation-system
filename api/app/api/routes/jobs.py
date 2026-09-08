from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import AppError, NotFoundError
from app.models.channel import Channel
from app.models.job import Job
from app.models.media import VideoProject
from app.models.user import User
from app.models.youtube import YoutubeUpload
from app.providers.registry import get_storage
from app.schemas.job import JobOut
from app.schemas.youtube import UploadOut
from app.services.media import MEDIA_STAGES, run_media_pipeline, run_media_stage
from app.services.publish import PUBLISH_STAGES, run_publish_pipeline, run_publish_stage

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job(db: Session, public_id: str) -> Job:
    job = db.execute(select(Job).where(Job.public_id == public_id)).scalar_one_or_none()
    if not job:
        raise NotFoundError("Job not found")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(Job).order_by(Job.id.desc()).limit(100)).scalars().all()


@router.get("/{public_id}", response_model=JobOut)
def get_job(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _job(db, public_id)


@router.post("/{public_id}/media:run")
def run_media(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = _job(db, public_id)
    channel = db.get(Channel, job.channel_id)
    results = run_media_pipeline(db, job, channel)
    return {"job": public_id, "results": results}


@router.post("/{public_id}/publish:run")
def run_publish(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = _job(db, public_id)
    channel = db.get(Channel, job.channel_id)
    results = run_publish_pipeline(db, job, channel)
    return {"job": public_id, "results": results}


@router.post("/{public_id}/stages/{stage}:run")
def run_stage(
    public_id: str, stage: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    job = _job(db, public_id)
    channel = db.get(Channel, job.channel_id)
    if stage in MEDIA_STAGES:
        out = run_media_stage(db, job, channel, stage)
    elif stage in PUBLISH_STAGES:
        out = run_publish_stage(db, job, channel, stage)
    else:
        raise AppError(f"stage must be one of {MEDIA_STAGES + PUBLISH_STAGES}")
    return {"job": public_id, "stage": stage, "output": out}


@router.get("/{public_id}/upload", response_model=UploadOut)
def get_upload(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = _job(db, public_id)
    row = db.execute(
        select(YoutubeUpload).where(YoutubeUpload.job_id == job.id)
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("No upload metadata for this job yet")
    return row


@router.get("/{public_id}/timeline")
def get_timeline(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = _job(db, public_id)
    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job.id)).scalar_one_or_none()
    if not vp or not vp.timeline_key:
        raise NotFoundError("No timeline yet")
    storage = get_storage()
    import json

    return JSONResponse(json.loads(open(storage.open_path(vp.timeline_key)).read()))


@router.get("/{public_id}/video")
def get_video(public_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = _job(db, public_id)
    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job.id)).scalar_one_or_none()
    if not vp or not vp.video_key or not get_storage().exists(vp.video_key):
        raise NotFoundError("No rendered video yet")
    path = get_storage().open_path(vp.video_key)
    return FileResponse(path, media_type="video/mp4", filename=f"{public_id}.mp4")
