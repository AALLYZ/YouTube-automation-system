"""Topic generation, scoring, and de-duplication."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Topic
from app.core.enums import TopicStatus
from app.providers.registry import get_ai
from app.services.ai_helpers import ai_json, record_usage

log = get_logger("topics")

_STOP = {"the", "a", "an", "of", "in", "to", "and", "for", "is", "on", "how", "why", "what"}

DEFAULT_WEIGHTS: dict[str, float] = {
    "interest": 1.0,
    "uniqueness": 1.0,
    "search": 1.0,
    "retention": 1.0,
    "competition": 1.0,
    "difficulty": 0.5,
}

_SYSTEM = (
    "You are a YouTube strategist. Generate original, non-repetitive video topic "
    "ideas for a specific channel. Every topic must be distinct in angle. "
    "Return JSON: {\"topics\": [{title, hook, angle, audience, estimated_interest, "
    "uniqueness_score, difficulty, search_potential, retention_potential, "
    "competition, evergreen}]}. Numeric fields are 0-100. Avoid clickbait that "
    "misrepresents content."
)


def fingerprint(title: str) -> str:
    tokens = [t for t in re.findall(r"[a-z0-9]+", title.lower()) if t not in _STOP]
    return hashlib.sha256(" ".join(sorted(set(tokens))).encode()).hexdigest()[:32]


def score_topic(raw: dict[str, Any], weights: dict[str, float]) -> float:
    def g(k: str) -> float:
        try:
            return max(0.0, min(100.0, float(raw.get(k, 0) or 0)))
        except (TypeError, ValueError):
            return 0.0

    positive = (
        weights["interest"] * g("estimated_interest")
        + weights["uniqueness"] * g("uniqueness_score")
        + weights["search"] * g("search_potential")
        + weights["retention"] * g("retention_potential")
    )
    negative = weights["competition"] * g("competition") + weights["difficulty"] * g("difficulty")
    max_positive = (
        weights["interest"] + weights["uniqueness"] + weights["search"] + weights["retention"]
    ) * 100
    raw_score = positive - negative
    return round(max(0.0, min(100.0, raw_score / max_positive * 100)), 2)


def generate_topics(
    db: Session, channel: Channel, *, count: int = 8, job_id: int | None = None
) -> list[Topic]:
    settings_row = channel.settings
    cfg = (settings_row.topic_ai if settings_row else {}) or {}
    weights = {**DEFAULT_WEIGHTS, **((settings_row.scoring_weights if settings_row else {}) or {})}
    temperature = float(cfg.get("temperature", 0.9))
    n = int(cfg.get("topic_count", count))

    used = db.execute(
        select(Topic.title).where(Topic.channel_id == channel.id)
    ).scalars().all()
    existing_fp = set(
        db.execute(select(Topic.fingerprint).where(Topic.channel_id == channel.id)).scalars().all()
    )

    prompt = (
        f"Channel: {channel.name}\n"
        f"Niche: {channel.niche}\n"
        f"Target audience: {channel.audience}\n"
        f"Language: {channel.language}\n"
        f"Tone: {channel.tone}\n"
        f"Content style: {channel.content_style}\n"
        f"Typical video length: {channel.video_length_min} minutes\n"
        f"Generate {n} topic ideas.\n"
        f"Topics already used (do NOT repeat or lightly reword): {used[:40]}\n"
    )

    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="topics", temperature=temperature)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="TOPIC")

    created: list[Topic] = []
    batch_fp: set[str] = set()
    for raw in data.get("topics", []):
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        fp = fingerprint(title)
        if fp in existing_fp or fp in batch_fp:
            log.info("skipping duplicate topic: %s", title)
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
        )
        topic.total_score = score_topic(raw, weights)
        db.add(topic)
        created.append(topic)

    db.flush()
    created.sort(key=lambda t: t.total_score, reverse=True)
    log.info("generated %d topics for channel %s", len(created), channel.slug)
    return created


def pick_best_topic(db: Session, channel: Channel) -> Topic | None:
    """Highest-scored APPROVED topic, else highest-scored GENERATED topic."""
    for status in (TopicStatus.APPROVED, TopicStatus.GENERATED):
        row = db.execute(
            select(Topic)
            .where(Topic.channel_id == channel.id, Topic.status == status)
            .order_by(Topic.total_score.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row:
            return row
    return None
