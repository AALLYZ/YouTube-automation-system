"""Meta WhatsApp Cloud API notifier."""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.providers.base import NotifierProvider, NotifyResult

log = get_logger("notify.meta")

_GRAPH = "https://graph.facebook.com/v21.0"


class MetaCloudWhatsApp(NotifierProvider):
    name = "meta_cloud"

    def __init__(self) -> None:
        missing = [
            n
            for n, v in (
                ("META_WABA_TOKEN", settings.meta_waba_token),
                ("META_PHONE_NUMBER_ID", settings.meta_phone_number_id),
            )
            if not v
        ]
        if missing:
            raise AppError(f"{', '.join(missing)} not set", code=ErrorCode.CONFIG)
        self._token = settings.meta_waba_token
        self._phone_id = settings.meta_phone_number_id

    def send(self, *, recipient: str, body: str) -> NotifyResult:
        if not recipient:
            raise AppError("No WhatsApp recipient configured", code=ErrorCode.CONFIG)
        to = recipient.replace("whatsapp:", "").lstrip("+").strip()
        try:
            resp = httpx.post(
                f"{_GRAPH}/{self._phone_id}/messages",
                headers={"Authorization": f"Bearer {self._token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": "text",
                    "text": {"preview_url": False, "body": body},
                },
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = (
                ErrorCode.PROVIDER_RATE_LIMIT
                if exc.response.status_code in (401, 429)
                else ErrorCode.PROVIDER_UNAVAILABLE
            )
            raise AppError(f"Meta Cloud error {exc.response.status_code}: {exc.response.text[:200]}", code=code) from exc
        except httpx.HTTPError as exc:
            raise AppError(f"Meta Cloud network error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        data = resp.json()
        try:
            mid = data["messages"][0]["id"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError("Meta Cloud returned no message id", code=ErrorCode.PROVIDER_BAD_RESPONSE) from exc
        return NotifyResult(message_id=mid, status="sent")
