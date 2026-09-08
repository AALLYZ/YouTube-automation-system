"""Final QA stage: verify the assembled video + publish metadata before upload."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import VideoStatus
from app.core.errors import ErrorCode, StageError
from app.core.logging import get_logger
from app.models.content import Script
from app.models.media import Thumbnail, VideoProject
from app.models.youtube import YoutubeUpload

log = get_logger("final_qa")

_MIN_RATIO = 0.4
_MAX_RATIO = 2.5


def run_final_qa(db: Session, *, job_id: int, script: Script) -> dict:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job_id)).scalar_one_or_none()
    check("video_project_exists", vp is not None)
    if vp:
        check("video_status_ready", vp.status == VideoStatus.READY, str(vp.status))
        check("video_file_present", bool(vp.video_key))
        check("video_has_duration", (vp.duration_sec or 0) > 0, f"{vp.duration_sec}s")
        streams = {s.get("type") for s in (vp.ffprobe or {}).get("streams", [])}
        check("has_video_stream", "video" in streams)
        check("has_audio_stream", "audio" in streams)
        check("subtitles_burned_or_present", bool(vp.has_subtitles))
        target = script.target_duration_sec or 0
        if target and vp.duration_sec:
            ratio = vp.duration_sec / target
            check("duration_within_tolerance", _MIN_RATIO <= ratio <= _MAX_RATIO, f"ratio={ratio:.2f}")

    upload = db.execute(select(YoutubeUpload).where(YoutubeUpload.job_id == job_id)).scalar_one_or_none()
    check("metadata_exists", upload is not None)
    if upload:
        check("has_title", bool(upload.title and upload.title.strip()))
        check("title_len_ok", len(upload.title or "") <= 100, f"{len(upload.title or '')} chars")
        check("has_description", bool(upload.description and upload.description.strip()))
        check("has_tags", len(upload.tags or []) >= 1)

    thumb = db.execute(
        select(Thumbnail).where(Thumbnail.job_id == job_id, Thumbnail.selected.is_(True))
    ).scalar_one_or_none()
    check("thumbnail_selected", thumb is not None and bool(thumb.file_key))

    failed = [c["check"] for c in checks if not c["ok"]]
    score = round(100 * (len(checks) - len(failed)) / max(1, len(checks)), 1)
    result = {"passed": not failed, "score": score, "checks": checks, "issues": failed}

    if failed:
        raise StageError(
            f"Final QA failed: {', '.join(failed)}",
            stage="FINAL_QA",
            code=ErrorCode.QA_FAILED,
            context=result,
        )
    log.info("final QA passed for job %s (%d checks)", job_id, len(checks))
    return result
