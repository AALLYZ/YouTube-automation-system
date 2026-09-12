"""Timeline stage: deterministic timeline.json that makes the render reproducible."""
from __future__ import annotations

import json
import tempfile
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AspectRatio, VideoStatus
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.media import MusicTrack, VideoProject, VisualAsset, Voiceover
from app.models.content import VideoScene
from app.providers.registry import get_storage

log = get_logger("timeline")

FPS = 30
_RES = {
    "16:9": {"sd": "1280x720", "hd": "1920x1080", "4k": "3840x2160"},
    "9:16": {"sd": "720x1280", "hd": "1080x1920", "4k": "2160x3840"},
    "1:1": {"sd": "720x720", "hd": "1080x1080", "4k": "2160x2160"},
}
DEFAULT_QUALITY = "hd"
TIMELINE_VERSION = 1


def run_timeline(
    db: Session,
    *,
    job_id: int,
    script_id: int,
    aspect: str = "16:9",
    quality: str = DEFAULT_QUALITY,
    allow_unverified_media: bool = False,
    music_cfg: dict | None = None,
) -> VideoProject:
    music_cfg = music_cfg or {}
    quality = quality if quality in ("sd", "hd", "4k") else DEFAULT_QUALITY
    vo = db.execute(select(Voiceover).where(Voiceover.job_id == job_id)).scalar_one()
    scenes = list(
        db.execute(
            select(VideoScene).where(VideoScene.script_id == script_id).order_by(VideoScene.scene_index)
        ).scalars()
    )
    assets = {
        a.scene_id: a
        for a in db.execute(select(VisualAsset).where(VisualAsset.job_id == job_id)).scalars()
    }

    tl_scenes = []
    cursor = 0.0
    for sc in scenes:
        asset = assets.get(sc.id)
        if not asset:
            raise AppError(f"Scene {sc.scene_index} has no visual asset", code=ErrorCode.MISSING_ASSET)
        if not asset.rights_verified and not allow_unverified_media:
            raise AppError(
                f"Scene {sc.scene_index} asset rights not verified ({asset.license or 'unknown'})",
                code=ErrorCode.MISSING_ASSET,
            )
        dur = float(sc.actual_duration_sec or sc.planned_duration_sec or 5.0)
        tl_scenes.append(
            {
                "index": sc.scene_index,
                "start": round(cursor, 3),
                "end": round(cursor + dur, 3),
                "duration": round(dur, 3),
                "asset_key": asset.file_key,
                "asset_type": asset.asset_type,
                "source": asset.source.value,
                "transition": sc.transition or "cut",
                "caption": sc.caption_text or sc.narration,
                "motion": "kenburns" if asset.asset_type == "image" else "none",
            }
        )
        cursor += dur

    music = None
    track = db.execute(select(MusicTrack).where(MusicTrack.job_id == job_id)).scalar_one_or_none()
    if track and track.file_key:
        music = {"key": track.file_key, "duck_pct": track.duck_level_pct}
    elif music_cfg.get("music_key"):
        music = {"key": music_cfg["music_key"], "duck_pct": int(music_cfg.get("duck_pct", 15))}

    resolution = _RES.get(aspect, _RES["16:9"])[quality]
    timeline = {
        "timeline_version": TIMELINE_VERSION,
        "job_id": job_id,
        "aspect_ratio": aspect,
        "resolution": resolution,
        "quality": quality,
        "fps": FPS,
        "duration": round(cursor, 3),
        "audio": {"voice_key": vo.audio_key, "voice_duration": vo.duration_sec},
        "music": music,
        "scenes": tl_scenes,
    }

    storage = get_storage()
    timeline_key = f"videos/{job_id}/timeline.json"
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "timeline.json")
        with open(p, "w") as fh:
            json.dump(timeline, fh, indent=2)
        storage.put(p, timeline_key)

    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job_id)).scalar_one_or_none()
    if not vp:
        vp = VideoProject(job_id=job_id)
        db.add(vp)
    vp.aspect_ratio = AspectRatio(aspect)
    vp.resolution = resolution
    vp.timeline_key = timeline_key
    vp.duration_sec = round(cursor, 3)
    vp.has_subtitles = True
    vp.status = VideoStatus.RENDERING
    if music:
        mt = track or MusicTrack(job_id=job_id, file_key=music["key"], duck_level_pct=music["duck_pct"])
        db.add(mt)
        db.flush()
        vp.music_track_id = mt.id
    db.flush()
    log.info("timeline: %d scenes, %.1fs for job %s", len(tl_scenes), cursor, job_id)
    return vp
