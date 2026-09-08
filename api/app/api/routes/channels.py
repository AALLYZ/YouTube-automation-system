from __future__ import annotations

import re

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import AppError, NotFoundError
from app.models.channel import Channel, ChannelSettings
from app.models.user import User
from app.schemas.channel import (
    ChannelIn,
    ChannelOut,
    ChannelSettingsIn,
    ChannelSettingsOut,
    ChannelUpdate,
)

router = APIRouter(prefix="/channels", tags=["channels"])


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120] or "channel"


def _get(db: Session, channel_id: int) -> Channel:
    ch = db.get(Channel, channel_id)
    if not ch:
        raise NotFoundError("Channel not found")
    return ch


@router.get("", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(Channel).order_by(Channel.id)).scalars().all()


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(
    payload: ChannelIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    slug = _slugify(payload.slug or payload.name)
    if db.execute(select(Channel).where(Channel.slug == slug)).scalar_one_or_none():
        raise AppError(f"Channel slug '{slug}' already exists")
    ch = Channel(
        **payload.model_dump(exclude={"slug"}),
        slug=slug,
    )
    ch.settings = ChannelSettings()
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _get(db, channel_id)


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ch = _get(db, channel_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(ch, k, v)
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    ch = _get(db, channel_id)
    db.delete(ch)
    db.commit()


@router.get("/{channel_id}/settings", response_model=ChannelSettingsOut)
def get_settings(channel_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ch = _get(db, channel_id)
    if not ch.settings:
        ch.settings = ChannelSettings()
        db.commit()
        db.refresh(ch)
    return ch.settings


@router.put("/{channel_id}/settings", response_model=ChannelSettingsOut)
def update_settings(
    channel_id: int,
    payload: ChannelSettingsIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ch = _get(db, channel_id)
    if not ch.settings:
        ch.settings = ChannelSettings()
        db.flush()
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(ch.settings, k, v)
    db.commit()
    db.refresh(ch)
    return ch.settings
