"""Twilio WhatsApp notifier."""
from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.providers.base import NotifierProvider, NotifyResult

log = get_logger("notify.twilio")


def _wa(addr: str) -> str:
    addr = (addr or "").strip()
    return addr if addr.startswith("whatsapp:") else f"whatsapp:{addr}"


class TwilioWhatsApp(NotifierProvider):
    name = "twilio"

    def __init__(self) -> None:
        missing = [
            n
            for n, v in (
                ("TWILIO_ACCOUNT_SID", settings.twilio_account_sid),
                ("TWILIO_AUTH_TOKEN", settings.twilio_auth_token),
                ("TWILIO_WHATSAPP_FROM", settings.twilio_whatsapp_from),
            )
            if not v
        ]
        if missing:
            raise AppError(f"{', '.join(missing)} not set", code=ErrorCode.CONFIG)
        from twilio.rest import Client

        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._from = _wa(settings.twilio_whatsapp_from)

    def send(self, *, recipient: str, body: str) -> NotifyResult:
        if not recipient:
            raise AppError("No WhatsApp recipient configured", code=ErrorCode.CONFIG)
        kwargs = {"from_": self._from, "to": _wa(recipient), "body": body}
        if settings.twilio_status_callback:
            kwargs["status_callback"] = settings.twilio_status_callback
        try:
            msg = self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            code = ErrorCode.PROVIDER_RATE_LIMIT if "429" in str(exc) else ErrorCode.PROVIDER_UNAVAILABLE
            raise AppError(f"Twilio send failed: {exc}", code=code) from exc
        return NotifyResult(message_id=msg.sid, status=msg.status or "queued")
