"""Subtitle stage: build SRT + VTT from per-scene timing."""
from __future__ import annotations

import json
import os
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.content import VideoScene
from app.models.media import Voiceover
from app.providers.registry import get_storage

log = get_logger("subtitles")

MAX_WORDS_PER_CUE = 8


def _fmt(t: float, sep: str) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _cues(scenes: list[VideoScene], segments: list[dict]) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    seg_by_idx = {s["scene_index"]: s for s in segments}
    for sc in scenes:
        seg = seg_by_idx.get(sc.scene_index)
        if not seg:
            continue
        words = (sc.caption_text or sc.narration or "").split()
        if not words:
            continue
        chunks = [words[i : i + MAX_WORDS_PER_CUE] for i in range(0, len(words), MAX_WORDS_PER_CUE)]
        span = max(0.1, seg["end"] - seg["start"])
        per = span / len(chunks)
        for i, chunk in enumerate(chunks):
            start = seg["start"] + i * per
            cues.append((start, start + per, " ".join(chunk)))
    return cues


def run_subtitles(db: Session, *, job_id: int, script_id: int) -> dict:
    vo = db.execute(select(Voiceover).where(Voiceover.job_id == job_id)).scalar_one()
    storage = get_storage()
    with tempfile.TemporaryDirectory() as tmp:
        ts_local = os.path.join(tmp, "ts.json")
        storage.get(vo.timestamps_key, ts_local)
        with open(ts_local) as fh:
            segments = json.load(fh).get("scenes", [])

    scenes = list(
        db.execute(
            select(VideoScene).where(VideoScene.script_id == script_id).order_by(VideoScene.scene_index)
        ).scalars()
    )
    cues = _cues(scenes, segments)

    srt_lines, vtt_lines = [], ["WEBVTT", ""]
    for i, (start, end, text) in enumerate(cues, 1):
        srt_lines += [str(i), f"{_fmt(start, ',')} --> {_fmt(end, ',')}", text, ""]
        vtt_lines += [f"{_fmt(start, '.')} --> {_fmt(end, '.')}", text, ""]

    srt_key = f"subtitles/{job_id}/captions.srt"
    vtt_key = f"subtitles/{job_id}/captions.vtt"
    with tempfile.TemporaryDirectory() as tmp:
        p_srt = os.path.join(tmp, "c.srt")
        p_vtt = os.path.join(tmp, "c.vtt")
        with open(p_srt, "w") as fh:
            fh.write("\n".join(srt_lines))
        with open(p_vtt, "w") as fh:
            fh.write("\n".join(vtt_lines))
        storage.put(p_srt, srt_key)
        storage.put(p_vtt, vtt_key)

    log.info("subtitles: %d cues for job %s", len(cues), job_id)
    return {"srt_key": srt_key, "vtt_key": vtt_key, "cues": len(cues)}
