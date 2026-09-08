"""Inbound delivery-status webhooks (Twilio + Meta WhatsApp Cloud)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.services.notifications import apply_status_update

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger("webhooks")


@router.post("/twilio")
async def twilio_status(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()))
    if settings.twilio_auth_token:
        from twilio.request_validator import RequestValidator

        signature = request.headers.get("X-Twilio-Signature", "")
        url = settings.twilio_status_callback or str(request.url)
        valid = RequestValidator(settings.twilio_auth_token).validate(url, form, signature)
        if not valid:
            log.warning("rejected Twilio webhook: bad signature")
            return Response(status_code=403)
    else:
        log.warning("TWILIO_AUTH_TOKEN unset — skipping webhook signature check")

    apply_status_update(
        db,
        provider_message_id=form.get("MessageSid") or form.get("SmsSid") or "",
        raw_status=form.get("MessageStatus") or form.get("SmsStatus") or "",
        error=form.get("ErrorCode"),
    )
    db.commit()
    return Response(status_code=204)


@router.get("/meta")
def meta_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token")
        and params.get("hub.verify_token") == settings.meta_verify_token
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return Response(status_code=403)


@router.post("/meta")
async def meta_status(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    updated = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for st in (change.get("value", {}) or {}).get("statuses", []):
                err = None
                errors = st.get("errors") or []
                if errors:
                    err = f"{errors[0].get('code')}: {errors[0].get('title')}"
                if apply_status_update(
                    db, provider_message_id=st.get("id", ""), raw_status=st.get("status", ""), error=err
                ):
                    updated += 1
    db.commit()
    return {"updated": updated}
