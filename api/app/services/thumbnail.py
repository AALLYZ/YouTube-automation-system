"""Thumbnail stage: concepts -> images -> deterministic score -> select best."""
from __future__ import annotations

import os
import tempfile

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.content import Script, Topic
from app.models.media import Thumbnail, VideoProject
from app.providers.registry import get_ai, get_image, get_storage
from app.services.ai_helpers import ai_json, record_usage

log = get_logger("thumbnail")

_SYSTEM = (
    "You are a YouTube thumbnail art director. Given the video topic, propose "
    "distinct thumbnail concepts as JSON: {concepts:[{concept, text, composition, "
    "target_emotion, image_prompt}]}. text: <=4 words, punchy, readable at small size "
    "(may be empty). composition: where the subject/text sit, lighting, contrast. "
    "target_emotion: one word. image_prompt: a vivid prompt for an image generator."
)

_THUMB_W, _THUMB_H = 1280, 720
_STRONG_EMOTIONS = {"curiosity", "surprise", "shock", "intrigue", "urgency", "awe", "fear", "excitement"}


def _score(concept: dict) -> float:
    text = str(concept.get("text", "")).strip()
    words = len(text.split())
    comp = str(concept.get("composition", "")).lower()
    emotion = str(concept.get("target_emotion", "")).strip().lower()

    score = 55.0
    if 1 <= words <= 4:
        score += 18
    elif words == 0:
        score += 4
    else:
        score -= 8
    if text and text == text.upper():
        score += 4
    if emotion in _STRONG_EMOTIONS:
        score += 12
    for kw, pts in (("contrast", 6), ("negative space", 5), ("rim light", 3), ("close-up", 4), ("rule of thirds", 3)):
        if kw in comp:
            score += pts
    if len(str(concept.get("image_prompt", ""))) > 40:
        score += 3
    return round(max(0.0, min(100.0, score)), 1)


def run_thumbnail(
    db: Session, *, job_id: int, channel: Channel, script: Script, max_concepts: int = 3
) -> list[Thumbnail]:
    cfg = (channel.settings.thumbnail_cfg or {}) if channel.settings else {}
    max_concepts = int(cfg.get("concepts", max_concepts))
    style = cfg.get("style", "")
    topic = db.get(Topic, script.topic_id)

    prompt = (
        f"Topic: {topic.title if topic else '(unknown)'}\n"
        f"Angle: {topic.angle if topic else ''}\n"
        f"Niche: {channel.niche}\nAudience: {channel.audience or 'general'}\n"
        f"Propose {max_concepts} concepts."
    )
    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="thumbnail_concepts", temperature=0.7)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="THUMBNAIL")

    concepts = (data.get("concepts") or [])[:max_concepts]
    if not concepts:
        concepts = [{
            "concept": f"Bold graphic about {topic.title if topic else 'the topic'}",
            "text": "", "composition": "high contrast, subject centered",
            "target_emotion": "curiosity", "image_prompt": (topic.title if topic else "video thumbnail"),
        }]

    image = get_image()
    storage = get_storage()
    rows: list[Thumbnail] = []

    db.execute(delete(Thumbnail).where(Thumbnail.job_id == job_id))
    with tempfile.TemporaryDirectory() as tmp:
        for i, c in enumerate(concepts):
            img_prompt = str(c.get("image_prompt") or c.get("concept") or "thumbnail")
            local = os.path.join(tmp, f"thumb_{i}.png")
            res = image.generate(
                prompt=img_prompt, out_path=local, width=_THUMB_W, height=_THUMB_H, style=style
            )
            record_usage(db, res.usage, job_id=job_id, stage="THUMBNAIL")
            key = f"thumbnails/{job_id}/thumb_{i}.png"
            storage.put(res.path, key)
            rows.append(
                Thumbnail(
                    job_id=job_id,
                    concept=str(c.get("concept", ""))[:2000],
                    text=str(c.get("text", ""))[:120],
                    composition=str(c.get("composition", ""))[:2000],
                    target_emotion=str(c.get("target_emotion", ""))[:60],
                    image_prompt=img_prompt[:2000],
                    file_key=key,
                    score=_score(c),
                    provider=image.name,
                    est_cost_usd=res.usage.est_cost_usd,
                )
            )

    db.add_all(rows)
    db.flush()

    best = max(rows, key=lambda r: r.score)
    best.selected = True
    db.flush()

    vp = db.execute(select(VideoProject).where(VideoProject.job_id == job_id)).scalar_one_or_none()
    if vp:
        vp.thumbnail_id = best.id
        db.flush()

    log.info(
        "thumbnail: %d concepts for job %s; selected #%d (score %.1f)",
        len(rows), job_id, rows.index(best), best.score,
    )
    return rows
