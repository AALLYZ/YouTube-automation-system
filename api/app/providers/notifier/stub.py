"""Offline notifier: records every message on the class so tests can assert on it."""
from __future__ import annotations

import uuid

from app.providers.base import NotifierProvider, NotifyResult


class StubNotifier(NotifierProvider):
    name = "stub"

    sent: list[dict] = []

    def send(self, *, recipient: str, body: str) -> NotifyResult:
        mid = f"stub-{uuid.uuid4().hex[:12]}"
        StubNotifier.sent.append({"message_id": mid, "recipient": recipient, "body": body})
        return NotifyResult(message_id=mid, status="sent")

    @classmethod
    def reset(cls) -> None:
        cls.sent.clear()
