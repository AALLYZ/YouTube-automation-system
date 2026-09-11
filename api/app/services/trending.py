"""Turn currently-trending YouTube videos into original, channel-specific topics.

The trending videos are used only as a signal of what subjects are getting
attention right now. The AI is explicitly instructed not to copy, paraphrase
closely, or reuse titles/wording/structure from them — every generated topic
(and the script written from it later, by the normal RESEARCH/SCRIPT stages)
is original content, so there is no copyright exposure in what ends up on the
channel.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import TopicStatus
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Topic
from app.providers.base import TrendingVideo, Usage
from app.providers.registry import get_ai, get_youtube
from app.services.ai_helpers import ai_json, record_usage
from app.services.topics import DEFAULT_WEIGHTS, fingerprint, score_topic
from app.services.youtube_oauth import credential_dict

log = get_logger("trending")

_SYSTEM = (
    "You are a YouTube strategist. You will be shown a list of videos that are "
    "CURRENTLY TRENDING, for inspiration only. Do not copy, paraphrase closely, "
    "or reuse any wording, jokes, structure, or description text from them — "
    "treat them only as a signal of what subjects are getting attention right "
    "now. For each idea, invent a genuinely original title, hook, and angle "
    "tailored to the target channel described below; it must not resemble any "
    "trending video's title or framing. Return JSON: {\"topics\": [{title, hook, "
    "angle, audience, estimated_interest, uniqueness_score, difficulty, "
    "search_potential, retention_potential, competition, evergreen}]}. Numeric "
    "fields are 0-100. Avoid clickbait that misrepresents content, and never "
    "claim or imply any connection to the trending videos or their creators."
)


def fetch_trending_videos(
    db: Session,
    channel: Channel,
    *,
    region_code: str = "US",
    category_id: str | None = None,
    max_results: int = 10,
    job_id: int | None = None,
) -> list[TrendingVideo]:
    """Pull the current trending chart from the YouTube provider (real or stub)."""
    youtube = get_youtube()
    credential = credential_dict(db, channel) if youtube.name != "stub" else None
    videos, units = youtube.list_trending(
        region_code=region_code,
        category_id=category_id,
        max_results=max_results,
        credential=credential,
    )
    if units:
        record_usage(
            db,
            Usage(provider="youtube", operation="videos.list", units=units),
            job_id=job_id,
            stage="TOPIC",
        )
    log.info("fetched %d trending videos for channel %s (region=%s)", len(videos), channel.slug, region_code)
    return videos


def generate_topics_from_trending(
    db: Session,
    channel: Channel,
    *,
    videos: list[TrendingVideo],
    count: int = 6,
    job_id: int | None = None,
) -> list[Topic]:
    """AI-rewrite trending subjects into original topic ideas for this channel."""
    if not videos:
        return []

    settings_row = channel.settings
    weights = {**DEFAULT_WEIGHTS, **((settings_row.scoring_weights if settings_row else {}) or {})}

    used = db.execute(select(Topic.title).where(Topic.channel_id == channel.id)).scalars().all()
    existing_fp = set(
        db.execute(select(Topic.fingerprint).where(Topic.channel_id == channel.id)).scalars().all()
    )

    trending_list = "\n".join(
        f"{i + 1}. \"{v.title}\" ({v.channel_title}, {v.view_count:,} views)"
        for i, v in enumerate(videos)
    )
    prompt = (
        f"Channel: {channel.name}\n"
        f"Niche: {channel.niche}\n"
        f"Target audience: {channel.audience}\n"
        f"Language: {channel.language}\n"
        f"Tone: {channel.tone}\n"
        f"Content style: {channel.content_style}\n\n"
        f"Currently trending on YouTube (inspiration only — do not copy):\n{trending_list}\n\n"
        f"Generate {count} original topic ideas for this channel. Each should be "
        f"inspired by the general subjects above but wholly distinct in title, "
        f"wording, and angle from every trending video listed.\n"
        f"Topics already used (do NOT repeat or lightly reword): {used[:40]}\n"
    )

    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="topics", temperature=0.9)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="TOPIC")

    source_ref = {
        "trending_videos": [
            {
                "video_id": v.video_id,
                "title": v.title,
                "channel_title": v.channel_title,
                "url": v.url,
            }
            for v in videos
        ]
    }

    created: list[Topic] = []
    batch_fp: set[str] = set()
    for raw in data.get("topics", []):
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        fp = fingerprint(title)
        if fp in existing_fp or fp in batch_fp:
            log.info("skipping duplicate trending-derived topic: %s", title)
            continue
        batch_fp.add(fp)
        topic = Topic(
            channel_id=channel.id,
            job_id=job_id,
            title=title[:300],
            hook=str(raw.get("hook", ""))[:2000],
            angle=str(raw.get("angle", ""))[:2000],
            audience=str(raw.get("audience", channel.audience))[:300],
            estimated_interest=float(raw.get("estimated_interest", 0) or 0),
            uniqueness_score=float(raw.get("uniqueness_score", 0) or 0),
            difficulty=float(raw.get("difficulty", 0) or 0),
            search_potential=float(raw.get("search_potential", 0) or 0),
            retention_potential=float(raw.get("retention_potential", 0) or 0),
            competition=float(raw.get("competition", 0) or 0),
            evergreen=bool(raw.get("evergreen", True)),
            fingerprint=fp,
            status=TopicStatus.GENERATED,
            source="youtube_trending",
            source_ref=source_ref,
        )
        topic.total_score = score_topic(raw, weights)
        db.add(topic)
        created.append(topic)

    db.flush()
    created.sort(key=lambda t: t.total_score, reverse=True)
    log.info(
        "generated %d topics from %d trending videos for channel %s",
        len(created), len(videos), channel.slug,
    )
    return created
