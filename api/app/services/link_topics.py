"""Turn the content of any pasted URL into original, channel-specific topics.

The page's own text is used only to tell the AI what it's about — the system
prompt explicitly forbids quoting or closely paraphrasing it. The generated
topics (and every script written from them later, by the normal
RESEARCH/SCRIPT stages) are original content; only a link/title/domain
reference is stored, never the scraped article text itself.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import TopicStatus
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Topic
from app.providers.registry import get_ai
from app.services.ai_helpers import ai_json, record_usage
from app.services.topics import DEFAULT_WEIGHTS, fingerprint, score_topic
from app.utils.webpage import fetch_page_text

log = get_logger("link_topics")

_SYSTEM = (
    "You are a YouTube strategist. You will be shown the extracted text of a "
    "web page, for inspiration only. Do not quote it, paraphrase it closely, "
    "or reuse its title, headings, structure, or phrasing — treat it only as a "
    "signal of what subject matter it covers. For each idea, invent a "
    "genuinely original title, hook, and angle tailored to the target channel "
    "described below; it must read nothing like the source page. Return JSON: "
    "{\"topics\": [{title, hook, angle, audience, estimated_interest, "
    "uniqueness_score, difficulty, search_potential, retention_potential, "
    "competition, evergreen}]}. Numeric fields are 0-100. Avoid clickbait that "
    "misrepresents content, and never claim or imply any connection to the "
    "source page or site."
)


def extract_page(url: str) -> dict:
    """Fetch + extract a page's title/text. Raises AppError on failure."""
    return fetch_page_text(url)


def generate_topics_from_page(
    db: Session,
    channel: Channel,
    *,
    page: dict,
    count: int = 6,
    job_id: int | None = None,
) -> list[Topic]:
    settings_row = channel.settings
    weights = {**DEFAULT_WEIGHTS, **((settings_row.scoring_weights if settings_row else {}) or {})}

    used = db.execute(select(Topic.title).where(Topic.channel_id == channel.id)).scalars().all()
    existing_fp = set(
        db.execute(select(Topic.fingerprint).where(Topic.channel_id == channel.id)).scalars().all()
    )

    prompt = (
        f"Channel: {channel.name}\n"
        f"Niche: {channel.niche}\n"
        f"Target audience: {channel.audience}\n"
        f"Language: {channel.language}\n"
        f"Tone: {channel.tone}\n"
        f"Content style: {channel.content_style}\n\n"
        f"Source page (inspiration only — do not quote or copy):\n"
        f"URL: {page['url']}\n"
        f"Page title: {page['title']}\n"
        f"Extracted text: {page['text'][:4000]}\n\n"
        f"Generate {count} original topic ideas for this channel, inspired by "
        f"the general subject of the page above but wholly distinct in title, "
        f"wording, and angle from it.\n"
        f"Topics already used (do NOT repeat or lightly reword): {used[:40]}\n"
    )

    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="topics", temperature=0.9)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="TOPIC")

    source_ref = {"url": page["url"], "title": page["title"], "domain": page["domain"]}

    created: list[Topic] = []
    batch_fp: set[str] = set()
    for raw in data.get("topics", []):
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        fp = fingerprint(title)
        if fp in existing_fp or fp in batch_fp:
            log.info("skipping duplicate link-derived topic: %s", title)
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
            source="web_link",
            source_ref=source_ref,
        )
        topic.total_score = score_topic(raw, weights)
        db.add(topic)
        created.append(topic)

    db.flush()
    created.sort(key=lambda t: t.total_score, reverse=True)
    log.info(
        "generated %d topics from %s for channel %s", len(created), page["url"], channel.slug
    )
    return created
