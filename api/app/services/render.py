"""Render stage: deterministic FFmpeg assembly of the timeline into final_video.mp4."""
from __future__ import annotations

import json
import os
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import VideoStatus
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.media import VideoProject
from app.providers.registry import get_storage
from app.utils.ffmpeg import escape_filter_path, probe, run

log = get_logger("render")

_VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
_INTRO_OUTRO_DEFAULT_SEC = 0.0


def run_render(
    db: Session, *, job_id: int, burn_subtitles: bool = True, branding_text: str = ""
) -> VideoProject:
    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job_id)).scalar_one()
    storage = get_storage()

    with tempfile.TemporaryDirectory() as tmp:
        tl_local = os.path.join(tmp, "timeline.json")
        storage.get(vp.timeline_key, tl_local)
        timeline = json.loads(open(tl_local).read())

        width, height = (int(x) for x in timeline["resolution"].split("x"))
        fps = int(timeline["fps"])
        scenes = timeline["scenes"]
        if not scenes:
            raise AppError("Timeline has no scenes", code=ErrorCode.RENDER_FAILED)

        # fetch assets
        inputs: list[str] = []
        filters: list[str] = []
        for i, sc in enumerate(scenes):
            ext = os.path.splitext(sc["asset_key"])[1].lower()
            local = os.path.join(tmp, f"scene_{i}{ext or '.png'}")
            storage.get(sc["asset_key"], local)
            dur = float(sc["duration"])
            if ext in _VIDEO_EXT:
                inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", local]
            else:
                inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", local]
            filters.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p,"
                f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]"
            )

        n = len(scenes)
        voice_local = os.path.join(tmp, "voice" + os.path.splitext(timeline["audio"]["voice_key"])[1])
        storage.get(timeline["audio"]["voice_key"], voice_local)
        inputs += ["-i", voice_local]
        voice_idx = n

        music = timeline.get("music")
        music_idx = None
        if music and music.get("key") and storage.exists(music["key"]):
            music_local = os.path.join(tmp, "music" + os.path.splitext(music["key"])[1])
            storage.get(music["key"], music_local)
            inputs += ["-stream_loop", "-1", "-i", music_local]
            music_idx = n + 1

        concat_in = "".join(f"[v{i}]" for i in range(n))
        filters.append(f"{concat_in}concat=n={n}:v=1:a=0[vcat]")

        total = float(timeline["duration"])
        srt_local = None
        if burn_subtitles:
            srt_key = f"subtitles/{job_id}/captions.srt"
            if storage.exists(srt_key):
                srt_local = os.path.join(tmp, "captions.srt")
                storage.get(srt_key, srt_local)

        video_out_label = "[vcat]"
        if srt_local:
            style = "FontName=Helvetica,FontSize=20,Outline=2,Shadow=0,MarginV=40,Alignment=2"
            filters.append(
                f"[vcat]subtitles=filename='{escape_filter_path(srt_local)}':force_style='{style}'[vsub]"
            )
            video_out_label = "[vsub]"
        if branding_text:
            safe = branding_text.replace("'", "").replace(":", " ")[:60]
            src = video_out_label
            filters.append(
                f"{src}drawtext=text='{safe}':fontcolor=white@0.6:fontsize=18:x=w-tw-24:y=24[vbrand]"
            )
            video_out_label = "[vbrand]"

        # audio graph
        filters.append(f"[{voice_idx}:a]aresample=async=1:first_pts=0[voice]")
        if music_idx is not None:
            duck = max(0.02, min(0.6, (music.get("duck_pct", 15) / 100.0)))
            filters.append(f"[{music_idx}:a]volume={duck:.3f}[mus]")
            filters.append("[voice][mus]amix=inputs=2:duration=first:dropout_transition=0[aout]")
            audio_out_label = "[aout]"
        else:
            audio_out_label = "[voice]"

        out_path = os.path.join(tmp, "final_video.mp4")
        args = [
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", video_out_label,
            "-map", audio_out_label,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-t", f"{total:.3f}", "-shortest",
            out_path,
        ]

        try:
            run(args)
        except AppError as exc:
            if srt_local:
                log.warning("render failed with burned subtitles, retrying without: %s", exc.message[:200])
                return _render_without_subs(db, vp, timeline, tmp, inputs, width, height, fps, n,
                                            voice_idx, music_idx, music, branding_text, out_path, total, storage, job_id)
            raise

        info = probe(out_path)
        video_key = f"videos/{job_id}/final_video.mp4"
        storage.put(out_path, video_key)
        size = os.path.getsize(out_path)

    vp.video_key = video_key
    vp.duration_sec = info["duration_sec"]
    vp.size_bytes = size
    vp.ffprobe = info
    vp.status = VideoStatus.READY
    db.flush()
    log.info("render: %s (%.1fs, %d bytes) for job %s", video_key, info["duration_sec"], size, job_id)
    return vp


def _render_without_subs(db, vp, timeline, tmp, inputs, width, height, fps, n, voice_idx,
                         music_idx, music, branding_text, out_path, total, storage, job_id):
    filters = []
    for i, sc in enumerate(timeline["scenes"]):
        dur = float(sc["duration"])
        filters.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p,"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
    filters.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vcat]")
    filters.append(f"[{voice_idx}:a]aresample=async=1:first_pts=0[voice]")
    if music_idx is not None:
        duck = max(0.02, min(0.6, (music.get("duck_pct", 15) / 100.0)))
        filters.append(f"[{music_idx}:a]volume={duck:.3f}[mus]")
        filters.append("[voice][mus]amix=inputs=2:duration=first:dropout_transition=0[aout]")
        a_label = "[aout]"
    else:
        a_label = "[voice]"
    args = [
        *inputs, "-filter_complex", ";".join(filters),
        "-map", "[vcat]", "-map", a_label,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", "-shortest", out_path,
    ]
    run(args)
    info = probe(out_path)
    video_key = f"videos/{job_id}/final_video.mp4"
    storage.put(out_path, video_key)
    vp.video_key = video_key
    vp.duration_sec = info["duration_sec"]
    vp.size_bytes = os.path.getsize(out_path)
    vp.ffprobe = info
    vp.has_subtitles = False
    vp.status = VideoStatus.READY
    db.flush()
    return vp
