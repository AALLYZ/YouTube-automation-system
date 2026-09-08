"""Research stage: collect sources, then summarise into fact/opinion/assumption buckets."""
from __future__ import annotations

import dataclasses

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.content import Research, Topic
from app.providers.registry import get_ai, get_research
from app.services.ai_helpers import ai_json, record_usage

log = get_logger("research")

_SYSTEM = (
    "You are a research assistant for a video script. Given a topic and raw "
    "sources, produce JSON: {summary, facts:[{claim, confidence}], opinions:[str], "
    "assumptions:[str]}. Only list a fact if a source supports it; otherwise put it "
    "under opinions or assumptions. confidence is 0-1."
)


def run_research(
    db: Session,
    *,
    topic: Topic,
    job_id: int,
    depth: str = "basic",
    max_sources: int = 5,
    enabled: bool = True,
) -> Research:
    provider = get_research()
    sources_dto = []
    if enabled:
        sources_dto, usage = provider.search(topic.title, depth=depth, max_sources=max_sources)
        record_usage(db, usage, job_id=job_id, stage="RESEARCH")

    sources = [dataclasses.asdict(s) for s in sources_dto]

    if not sources:
        research = Research(
            topic_id=topic.id,
            job_id=job_id,
            provider=provider.name,
            summary="No research performed; script will rely on general knowledge and be marked accordingly.",
            facts=[],
            opinions=[],
            assumptions=["No external sources were consulted for this video."],
            sources=[],
        )
        db.add(research)
        db.flush()
        return research

    ai = get_ai()
    prompt = f"Topic: {topic.title}\n\nSources:\n" + "\n".join(
        f"- {s['title']} ({s['url']}): {' '.join(s['key_facts'])}" for s in sources
    )
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="research_summary", temperature=0.3)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="RESEARCH")

    research = Research(
        topic_id=topic.id,
        job_id=job_id,
        provider=provider.name,
        summary=str(data.get("summary", ""))[:5000],
        facts=data.get("facts", []),
        opinions=data.get("opinions", []),
        assumptions=data.get("assumptions", []),
        sources=sources,
    )
    db.add(research)
    db.flush()
    log.info("research done for topic %s: %d sources", topic.id, len(sources))
    return research
