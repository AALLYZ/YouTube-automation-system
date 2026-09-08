"""Console notifier: logs the message instead of sending it (safe default)."""
from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.providers.base import NotifierProvider, NotifyResult

log = get_logger("notify.console")


class ConsoleNotifier(NotifierProvider):
    name = "console"

    def send(self, *, recipient: str, body: str) -> NotifyResult:
        log.info("NOTIFY -> %s\n%s", recipient or "(no recipient)", body)
        return NotifyResult(message_id=f"console-{uuid.uuid4().hex[:12]}", status="sent")
