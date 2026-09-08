"""Voice stage: synthesize narration, derive per-scene timing."""
from __future__ import annotations

import json
import os
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.content import Script, ScriptVersion, VideoScene
from app.models.media import Voiceover
from app.providers.registry import get_storage, get_voice
from app.services.ai_helpers import record_usage

log = get_logger("voice")


def _scene_segments(scenes: list[VideoScene], total: float) -> list[dict]:
    weights = [max(1, len((s.narration or "").split())) for s in scenes]
    wsum = sum(weights) or 1
    out, cursor = [], 0.0
    for i, (sc, w) in enumerate(zip(scenes, weights)):
        dur = total * w / wsum if i < len(scenes) - 1 else max(0.1, total - cursor)
        out.append(
            {"scene_index": sc.scene_index, "start": round(cursor, 3), "end": round(cursor + dur, 3), "duration": round(dur, 3)}
        )
        cursor += dur
    return out


def run_voice(
    db: Session, *, script: Script, job_id: int, voice_cfg: dict | None = None
) -> Voiceover:
    version = db.execute(
        select(ScriptVersion).where(
            ScriptVersion.script_id == script.id, ScriptVersion.version == script.current_version
        )
    ).scalar_one()
    scenes = list(
        db.execute(
            select(VideoScene).where(VideoScene.script_id == script.id).order_by(VideoScene.scene_index)
        ).scalars()
    )
    text = version.body_json.get("full_text") or " ".join(s.narration for s in scenes)

    voice_cfg = voice_cfg or {}
    provider = get_voice()
    storage = get_storage()

    with tempfile.TemporaryDirectory() as tmp:
        ext = "mp3" if provider.name in ("openai", "elevenlabs") else "wav"
        local = os.path.join(tmp, f"voiceover.{ext}")
        result = provider.synthesize(
            text=text,
            out_path=local,
            voice=voice_cfg.get("voice", ""),
            language=script.language,
            speed=float(voice_cfg.get("speed", 1.0)),
            emotion=voice_cfg.get("emotion", "neutral"),
        )
        audio_key = f"voiceovers/{job_id}/voiceover.{ext}"
        storage.put(local, audio_key)

        segments = _scene_segments(scenes, result.duration_sec)
        ts_local = os.path.join(tmp, "timestamps.json")
        with open(ts_local, "w") as fh:
            json.dump({"duration": result.duration_sec, "words": result.timestamps, "scenes": segments}, fh)
        ts_key = f"voiceovers/{job_id}/timestamps.json"
        storage.put(ts_local, ts_key)

    for sc, seg in zip(scenes, segments):
        sc.actual_duration_sec = seg["duration"]

    record_usage(db, result.usage, job_id=job_id, stage="VOICE")

    vo = Voiceover(
        job_id=job_id,
        script_version_id=version.id,
        provider=provider.name,
        voice=voice_cfg.get("voice", ""),
        language=script.language,
        speed=float(voice_cfg.get("speed", 1.0)),
        emotion=voice_cfg.get("emotion", "neutral"),
        duration_sec=result.duration_sec,
        audio_key=audio_key,
        timestamps_key=ts_key,
        est_cost_usd=result.usage.est_cost_usd,
    )
    db.add(vo)
    db.flush()
    log.info("voice: %.1fs via %s for job %s", result.duration_sec, provider.name, job_id)
    return vo
