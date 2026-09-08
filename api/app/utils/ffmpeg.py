"""Thin wrapper around ffmpeg/ffprobe.

Resolution order:
1. FFMPEG_BINARY / FFPROBE_BINARY env vars
2. ffmpeg/ffprobe on PATH (e.g. apt-installed in Docker)
3. static-ffmpeg (downloads a static build on first use)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

log = get_logger("ffmpeg")


@lru_cache
def _binaries() -> tuple[str, str]:
    env_ff, env_fp = os.getenv("FFMPEG_BINARY"), os.getenv("FFPROBE_BINARY")
    if env_ff and env_fp:
        return env_ff, env_fp
    path_ff, path_fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if path_ff and path_fp:
        return path_ff, path_fp
    try:
        from static_ffmpeg import run as sf_run

        return sf_run.get_or_fetch_platform_executables_else_raise()
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            f"ffmpeg/ffprobe not available: {exc}. Install ffmpeg or set FFMPEG_BINARY/FFPROBE_BINARY.",
            code=ErrorCode.CONFIG,
        ) from exc


def ffmpeg_exe() -> str:
    return _binaries()[0]


def ffprobe_exe() -> str:
    return _binaries()[1]


def run(args: list[str], *, timeout: int = 900) -> str:
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", *args]
    log.info("ffmpeg %s", " ".join(str(a) for a in cmd[1:])[:500])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise AppError(
            f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1500:]}", code=ErrorCode.RENDER_FAILED
        )
    return proc.stderr


def probe(path: str) -> dict:
    proc = subprocess.run(
        [
            ffprobe_exe(), "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise AppError(f"ffprobe failed: {proc.stderr[-500:]}", code=ErrorCode.RENDER_FAILED)
    data = json.loads(proc.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    if not streams:
        raise AppError("ffprobe: file has no media streams", code=ErrorCode.RENDER_FAILED)
    return {
        "duration_sec": round(float(fmt.get("duration", 0) or 0), 3),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "streams": [
            {
                "type": s.get("codec_type"),
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "sample_rate": s.get("sample_rate"),
            }
            for s in streams
        ],
    }


def escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
