from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.enums import TopicStatus
from app.core.errors import AppError, NotFoundError
from app.models.channel import Channel
from app.models.content import Topic
from app.models.user import User
from app.schemas.topic import GenerateTopicsRequest, TopicOut, TopicReject, TrendingTopicsRequest
from app.services.topics import generate_topics
from app.services.trending import fetch_trending_videos, generate_topics_from_trending

router = APIRouter(tags=["topics"])


def _channel(db: Session, channel_id: int) -> Channel:
    ch = db.get(Channel, channel_id)
    if not ch:
        raise NotFoundError("Channel not found")
    return ch


@router.post("/channels/{channel_id}/topics:generate", response_model=list[TopicOut])
def generate(
    channel_id: int,
    payload: GenerateTopicsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ch = _channel(db, channel_id)
    try:
        topics = generate_topics(db, ch, count=payload.count)
    except AppError:
        db.rollback()
        raise
    db.commit()
    for t in topics:
        db.refresh(t)
    return topics


@router.post("/channels/{channel_id}/topics:from_trending", response_model=list[TopicOut])
def generate_from_trending(
    channel_id: int,
    payload: TrendingTopicsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Pull current YouTube trending videos and rewrite them into original topics.

    The trending videos are used only as inspiration for subject matter — the
    generated topics (and every script produced from them later) are original,
    AI-written content with no copied titles, wording, or descriptions.
    """
    ch = _channel(db, channel_id)
    try:
        videos = fetch_trending_videos(
            db,
            ch,
            region_code=payload.region_code,
            category_id=payload.category_id,
            max_results=payload.max_results,
        )
        if not videos:
            raise AppError("No trending videos returned for that region/category")
        topics = generate_topics_from_trending(db, ch, videos=videos, count=payload.count)
    except AppError:
        db.rollback()
        raise
    db.commit()
    for t in topics:
        db.refresh(t)
    return topics


@router.get("/channels/{channel_id}/topics", response_model=list[TopicOut])
def list_topics(
    channel_id: int,
    status: TopicStatus | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _channel(db, channel_id)
    q = select(Topic).where(Topic.channel_id == channel_id)
    if status:
        q = q.where(Topic.status == status)
    q = q.order_by(Topic.total_score.desc())
    return db.execute(q).scalars().all()


def _topic(db: Session, topic_id: int) -> Topic:
    t = db.get(Topic, topic_id)
    if not t:
        raise NotFoundError("Topic not found")
    return t


@router.post("/topics/{topic_id}:approve", response_model=TopicOut)
def approve_topic(topic_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = _topic(db, topic_id)
    t.status = TopicStatus.APPROVED
    t.rejected_reason = None
    db.commit()
    db.refresh(t)
    return t


@router.post("/topics/{topic_id}:reject", response_model=TopicOut)
def reject_topic(
    topic_id: int,
    payload: TopicReject,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    t = _topic(db, topic_id)
    t.status = TopicStatus.REJECTED
    t.rejected_reason = payload.reason
    db.commit()
    db.refresh(t)
    return t
