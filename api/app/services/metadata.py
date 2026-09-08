"""Metadata stage: scored titles, description (+ chapters), tags, hashtags, category."""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import PrivacyStatus
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Script, ScriptVersion, Topic, VideoScene
from app.models.media import VideoProject
from app.models.youtube import YoutubeUpload
from app.providers.registry import get_ai
from app.services.ai_helpers import ai_json, record_usage

log = get_logger("metadata")

_SYSTEM = (
    "You are a YouTube growth strategist. Given a video's topic and narration, "
    "produce publish metadata as JSON: {titles:[{title, reason, score}], description, "
    "tags:[str], hashtags:[str], category_id, chapter_titles:[str]}. Titles: 5 options, "
    "<=100 chars, no clickbait lies, score 0-100 for expected CTR. description: 2-4 "
    "short paragraphs, first 150 chars must hook. tags: 8-15 lowercase search phrases. "
    "hashtags: 2-3, each starting with #. chapter_titles: one short label per scene, in order."
)

_MIN_CHAPTER_GAP_SEC = 10.0
_YT_CATEGORIES = {"1", "2", "10", "15", "17", "19", "20", "22", "23", "24", "25", "26", "27", "28"}


def _clean_tags(raw: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in raw or []:
        t = re.sub(r"\s+", " ", str(t)).strip().lower()[:60]
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= 15:
            break
    return out


def _clean_hashtags(raw: Any) -> list[str]:
    out: list[str] = []
    for h in raw or []:
        h = str(h).strip()
        if not h:
            continue
        h = "#" + re.sub(r"[^0-9A-Za-z]", "", h.lstrip("#"))
        if len(h) > 1 and h not in out:
            out.append(h)
        if len(out) >= 3:
            break
    return out


def _scene_durations(db: Session, script_id: int) -> list[tuple[str, float]]:
    scenes = list(
        db.execute(
            select(VideoScene)
            .where(VideoScene.script_id == script_id)
            .order_by(VideoScene.scene_index)
        ).scalars()
    )
    return [
        (sc.caption_text or sc.narration or f"Part {i + 1}",
         float(sc.actual_duration_sec or sc.planned_duration_sec or 0.0))
        for i, sc in enumerate(scenes)
    ]


def _build_chapters(durations: list[tuple[str, float]], titles: list[str]) -> list[dict]:
    """YouTube chapters: >=3, first at 0:00, each >= 10s apart."""
    if len(durations) < 3 or any(d <= 0 for _, d in durations):
        return []
    chapters: list[dict] = []
    cursor = 0.0
    for i, (_default, dur) in enumerate(durations):
        title = (titles[i] if i < len(titles) else _default) or f"Part {i + 1}"
        title = re.sub(r"\s+", " ", str(title)).strip()[:80]
        if chapters and cursor - chapters[-1]["start"] < _MIN_CHAPTER_GAP_SEC:
            cursor += dur
            continue
        chapters.append({"start": round(cursor, 1), "title": title})
        cursor += dur
    if len(chapters) < 3 or chapters[0]["start"] != 0.0:
        return []
    return chapters


def _fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _compose_description(base: str, chapters: list[dict], hashtags: list[str]) -> str:
    parts = [base.strip()]
    if chapters:
        parts.append("Chapters:\n" + "\n".join(f"{_fmt_ts(c['start'])} {c['title']}" for c in chapters))
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n\n".join(p for p in parts if p)[:5000]


def _privacy(channel: Channel) -> PrivacyStatus:
    if channel.settings and channel.settings.privacy_default:
        return channel.settings.privacy_default
    return PrivacyStatus(settings.youtube_default_privacy)


def run_metadata(
    db: Session,
    *,
    job_id: int,
    channel: Channel,
    script: Script,
    scheduled_publish_at: Optional[str] = None,
) -> YoutubeUpload:
    version = db.execute(
        select(ScriptVersion).where(
            ScriptVersion.script_id == script.id,
            ScriptVersion.version == script.current_version,
        )
    ).scalar_one()
    topic = db.get(Topic, script.topic_id)
    yt_cfg = (channel.settings.youtube_cfg or {}) if channel.settings else {}

    full_text = version.body_json.get("full_text", "")
    prompt = (
        f"Topic: {topic.title if topic else '(unknown)'}\n"
        f"Angle: {topic.angle if topic else ''}\n"
        f"Audience: {channel.audience or 'general'}\n"
        f"Language: {script.language}\nNiche: {channel.niche}\n\n"
        f"Narration (verbatim):\n{full_text[:6000]}\n"
    )

    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="youtube_metadata", temperature=0.6)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="METADATA")

    raw_titles = data.get("titles") or []
    title_options = []
    for t in raw_titles:
        if isinstance(t, str):
            t = {"title": t, "reason": "", "score": 50}
        title = re.sub(r"\s+", " ", str(t.get("title", ""))).strip()[:100]
        if not title:
            continue
        title_options.append(
            {"title": title, "reason": str(t.get("reason", ""))[:200],
             "score": max(0, min(100, int(float(t.get("score", 50) or 50))))}
        )
    title_options.sort(key=lambda x: x["score"], reverse=True)
    if not title_options:
        title_options = [{"title": (topic.title if topic else "Untitled")[:100], "reason": "fallback", "score": 50}]

    durations = _scene_durations(db, script.id)
    chapters = _build_chapters(durations, data.get("chapter_titles") or [])
    tags = _clean_tags(data.get("tags"))
    hashtags = _clean_hashtags(data.get("hashtags"))
    category_id = str(data.get("category_id") or yt_cfg.get("category_id") or settings.youtube_default_category_id)
    if category_id not in _YT_CATEGORIES:
        category_id = settings.youtube_default_category_id
    description = _compose_description(str(data.get("description", "")), chapters, hashtags)

    row = db.execute(select(YoutubeUpload).where(YoutubeUpload.job_id == job_id)).scalar_one_or_none()
    if not row:
        row = YoutubeUpload(job_id=job_id, channel_id=channel.id)
        db.add(row)
    row.channel_id = channel.id
    row.title = title_options[0]["title"]
    row.title_options = title_options
    row.description = description
    row.tags = tags
    row.hashtags = hashtags
    row.category_id = category_id
    row.chapters = chapters
    row.playlist_id = yt_cfg.get("playlist_id")
    row.privacy_status = _privacy(channel)
    if scheduled_publish_at:
        row.scheduled_publish_at = _parse_dt(scheduled_publish_at)
    db.flush()
    log.info(
        "metadata: '%s' (%d title options, %d tags, %d chapters) for job %s",
        row.title, len(title_options), len(tags), len(chapters), job_id,
    )
    return row


def _parse_dt(value: str):
    from dateutil import parser as _p

    return _p.isoparse(value)
