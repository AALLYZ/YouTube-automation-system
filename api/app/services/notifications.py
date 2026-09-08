"""Notification templates, delivery, dedup, and inbound status updates."""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import NotificationEvent, NotificationStatus
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.job import Job
from app.models.ops import Notification
from app.providers.registry import get_notifier

log = get_logger("notifications")

# ---------------- templates ----------------
def _money(v: Any) -> str:
    try:
        return f"${float(v):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _tpl_job_started(c: dict) -> str:
    return (
        f"🎬 *New video started*\n"
        f"Channel: {c.get('channel_name', '?')}\n"
        f"Topic: {c.get('topic', 'TBD')}\n"
        f"Job: {c.get('job_public_id', '?')}"
    )


def _tpl_video_ready(c: dict) -> str:
    return (
        f"✅ *Video rendered*\n"
        f"{c.get('title') or c.get('topic', 'Your video')}\n"
        f"Length: {c.get('duration_min', '?')} min · Cost: {_money(c.get('cost_usd'))}\n"
        f"Job: {c.get('job_public_id', '?')}"
        + (f"\nReview: {c['review_url']}" if c.get("review_url") else "")
    )


def _tpl_published(c: dict) -> str:
    line = f"🚀 *Published to YouTube*\n{c.get('title', 'Your video')}"
    if c.get("youtube_url"):
        line += f"\n{c['youtube_url']}"
    if c.get("scheduled_publish_at"):
        line += f"\nScheduled: {c['scheduled_publish_at']}"
    return line + f"\nJob: {c.get('job_public_id', '?')}"


def _tpl_error(c: dict) -> str:
    return (
        f"⚠️ *Pipeline error*\n"
        f"Job: {c.get('job_public_id', '?')} · Stage: {c.get('stage', '?')}\n"
        f"{c.get('error_code', 'UNKNOWN')}: {c.get('error_message', '')}"[:900]
    )


TEMPLATES = {
    NotificationEvent.JOB_STARTED: ("job_started", _tpl_job_started),
    NotificationEvent.VIDEO_READY: ("video_ready", _tpl_video_ready),
    NotificationEvent.PUBLISHED: ("published", _tpl_published),
    NotificationEvent.ERROR: ("error", _tpl_error),
}

_SAMPLE = {
    "channel_name": "Demo Channel",
    "topic": "The history of the paperclip",
    "title": "The Surprising History of the Paperclip",
    "job_public_id": "job_2026_00042",
    "duration_min": 8,
    "cost_usd": 0.42,
    "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
    "stage": "RENDER",
    "error_code": "RENDER_FAILED",
    "error_message": "ffmpeg exited 1",
}


def render_template(event: NotificationEvent, context: dict) -> tuple[str, str]:
    name, fn = TEMPLATES[event]
    return name, fn(context or {})


# ---------------- delivery ----------------
_LIVE_STATUSES = {NotificationStatus.SENT, NotificationStatus.DELIVERED, NotificationStatus.READ}


def _recipient(channel: Channel) -> Optional[str]:
    cfg = (channel.settings.whatsapp_cfg or {}) if channel.settings else {}
    return cfg.get("to") or cfg.get("recipient") or settings.whatsapp_to


_REAL_WA = {"twilio", "meta_cloud"}


def _delivery_provider(test_mode: bool):
    """In test mode, real WhatsApp providers are swapped for the console logger."""
    if test_mode and settings.notifier_provider in _REAL_WA:
        from app.providers.notifier.console import ConsoleNotifier

        return ConsoleNotifier()
    return get_notifier()


def _event_enabled(channel: Channel, event: NotificationEvent) -> bool:
    if not channel.settings:
        return True
    return event.value in (channel.settings.notify_events or [])


def notify(
    db: Session,
    *,
    event: NotificationEvent,
    channel: Channel,
    job: Optional[Job] = None,
    context: Optional[dict] = None,
    force: bool = False,
) -> Optional[Notification]:
    """Render + deliver one notification. Returns None when skipped by preference.

    Dedup: at most one non-failed row per (job_id, event).
    """
    if not force and not _event_enabled(channel, event):
        log.info("notify skipped (%s disabled for channel %s)", event.value, channel.id)
        return None

    context = {"channel_name": channel.name, **(context or {})}
    if job is not None:
        context.setdefault("job_public_id", job.public_id)

    existing = None
    if job is not None:
        existing = db.execute(
            select(Notification).where(
                Notification.job_id == job.id, Notification.event == event
            )
        ).scalar_one_or_none()
        if existing and existing.status in _LIVE_STATUSES:
            log.info("notify deduped (%s already sent for job %s)", event.value, job.public_id)
            return existing

    template, body = render_template(event, context)
    recipient = _recipient(channel)

    # test-mode jobs never touch a paid/real WhatsApp channel
    test_mode = bool(job is not None and job.test_run)
    provider = _delivery_provider(test_mode)

    row = existing or Notification(job_id=job.id if job else None, channel_id=channel.id, event=event)
    row.provider = f"{provider.name} (test)" if test_mode and provider.name != settings.notifier_provider else provider.name
    row.recipient = recipient or ""
    row.template = template
    row.body = body
    row.status = NotificationStatus.QUEUED
    row.error = None
    row.provider_message_id = None
    if not existing:
        db.add(row)
    db.flush()

    if not recipient:
        row.status = NotificationStatus.FAILED
        row.error = "no WhatsApp recipient configured (channel whatsapp_cfg.to / WHATSAPP_TO)"
        db.flush()
        log.warning("notify %s for channel %s has no recipient", event.value, channel.id)
        return row

    try:
        result = provider.send(recipient=recipient, body=body)
        row.provider_message_id = result.message_id
        row.status = _map_status(result.status, default=NotificationStatus.SENT)
    except Exception as exc:  # noqa: BLE001 - delivery failure must not break the pipeline
        row.status = NotificationStatus.FAILED
        row.error = str(exc)[:900]
        log.warning("notify %s delivery failed: %s", event.value, exc)
    db.flush()
    return row


def safe_notify(db: Session, **kwargs: Any) -> Optional[Notification]:
    """notify() that never raises — for use inside pipeline stages."""
    try:
        return notify(db, **kwargs)
    except Exception as exc:  # noqa: BLE001
        log.warning("safe_notify swallowed error: %s", exc)
        return None


def send_test(db: Session, *, channel: Channel, event: NotificationEvent) -> Notification:
    row = notify(db, event=event, channel=channel, job=None, context=dict(_SAMPLE), force=True)
    assert row is not None  # force=True always produces a row
    return row


# ---------------- inbound status ----------------
_TWILIO_STATUS = {
    "queued": NotificationStatus.QUEUED,
    "sending": NotificationStatus.SENT,
    "sent": NotificationStatus.SENT,
    "delivered": NotificationStatus.DELIVERED,
    "read": NotificationStatus.READ,
    "undelivered": NotificationStatus.FAILED,
    "failed": NotificationStatus.FAILED,
}
_META_STATUS = {
    "sent": NotificationStatus.SENT,
    "delivered": NotificationStatus.DELIVERED,
    "read": NotificationStatus.READ,
    "failed": NotificationStatus.FAILED,
}


def _map_status(raw: str, *, default: NotificationStatus) -> NotificationStatus:
    return _TWILIO_STATUS.get((raw or "").lower()) or _META_STATUS.get((raw or "").lower()) or default


def apply_status_update(
    db: Session, *, provider_message_id: str, raw_status: str, error: Optional[str] = None
) -> Optional[Notification]:
    if not provider_message_id:
        return None
    row = db.execute(
        select(Notification).where(Notification.provider_message_id == provider_message_id)
    ).scalar_one_or_none()
    if not row:
        log.info("status update for unknown message %s", provider_message_id)
        return None
    new_status = _map_status(raw_status, default=row.status)
    # never regress read -> delivered -> sent
    order = [
        NotificationStatus.QUEUED, NotificationStatus.SENT,
        NotificationStatus.DELIVERED, NotificationStatus.READ,
    ]
    if new_status == NotificationStatus.FAILED or new_status not in order or row.status not in order or \
            order.index(new_status) >= order.index(row.status):
        row.status = new_status
    if new_status in (NotificationStatus.DELIVERED, NotificationStatus.READ):
        row.delivered_at = row.delivered_at or dt.datetime.now(dt.timezone.utc)
    if error:
        row.error = error[:900]
    db.flush()
    log.info("notification %s -> %s", provider_message_id, row.status.value)
    return row
