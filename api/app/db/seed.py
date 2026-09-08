"""Idempotent bootstrap: seed admin user + a default channel."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import UserRole
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models.channel import Channel, ChannelSettings
from app.models.user import User

log = get_logger("seed")


def seed(db: Session | None = None) -> None:
    close = db is None
    db = db or SessionLocal()
    try:
        _seed_admin(db)
        _seed_default_channel(db)
        db.commit()
    finally:
        if close:
            db.close()


def _seed_admin(db: Session) -> None:
    existing = db.execute(
        select(User).where(User.email == settings.admin_email.lower())
    ).scalar_one_or_none()
    if existing:
        return
    if not settings.admin_password:
        log.warning("ADMIN_PASSWORD not set; skipping admin seed")
        return
    db.add(
        User(
            email=settings.admin_email.lower(),
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN,
        )
    )
    log.info("Seeded admin user %s", settings.admin_email)


def _seed_default_channel(db: Session) -> None:
    if db.execute(select(Channel).limit(1)).scalar_one_or_none():
        return
    ch = Channel(
        name="My First Channel",
        slug="my-first-channel",
        niche="general",
        audience="general audience",
        language="English",
        tone="informative",
        content_style="explainer",
    )
    ch.settings = ChannelSettings()
    db.add(ch)
    log.info("Seeded default channel")


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging()
    seed()
