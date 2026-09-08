"""Structured event log -> `system_logs` table (surfaced on the dashboard Logs page)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.ops import SystemLog

log = get_logger("events")


def record_event(
    db: Session,
    *,
    level: str,
    event: str,
    message: str = "",
    job_id: Optional[int] = None,
    stage: Optional[str] = None,
    context: Optional[dict] = None,
) -> None:
    try:
        db.add(
            SystemLog(
                job_id=job_id,
                level=level.upper()[:10],
                stage=stage,
                event=event[:80],
                message=message[:4000],
                context=context,
            )
        )
        db.flush()
    except Exception as exc:  # noqa: BLE001 - logging must never break a request
        log.warning("failed to persist system log %s: %s", event, exc)
