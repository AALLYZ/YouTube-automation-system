from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.models.channel import Channel
from app.models.user import User
from app.schemas.youtube import DisconnectOut, OAuthStartOut, YouTubeStatusOut
from app.services import youtube_oauth
from app.services.upload import quota_used_today

router = APIRouter(prefix="/youtube", tags=["youtube"])


def _channel(db: Session, channel_id: int) -> Channel:
    ch = db.get(Channel, channel_id)
    if not ch:
        raise NotFoundError("Channel not found")
    return ch


@router.get("/status", response_model=YouTubeStatusOut)
def youtube_status(
    channel_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ch = _channel(db, channel_id)
    data = youtube_oauth.connection_status(db, ch)
    data["quota_used_today"] = quota_used_today(db)
    data["quota_daily_limit"] = settings.yt_daily_quota_units
    return data


@router.get("/oauth/start", response_model=OAuthStartOut)
def oauth_start(
    channel_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _channel(db, channel_id)
    url, state = youtube_oauth.build_authorization_url(channel_id)
    return OAuthStartOut(authorization_url=url, state=state)


@router.get("/oauth/callback", response_class=HTMLResponse)
def oauth_callback(
    state: str = Query(default=""),
    code: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Google redirects the browser here. No bearer token — CSRF is the signed state."""
    if error:
        return HTMLResponse(_page(f"Authorization failed: {error}", ok=False), status_code=400)
    if not state or not code:
        return HTMLResponse(_page("Missing state or code", ok=False), status_code=400)
    try:
        cred = youtube_oauth.complete_oauth(db, state=state, code=code)
        db.commit()
    except AppError as exc:
        db.rollback()
        return HTMLResponse(_page(exc.message, ok=False), status_code=exc.http_status)
    title = cred.channel_title or cred.youtube_channel_id or "your channel"
    return HTMLResponse(_page(f"Connected to {title}. You can close this tab."))


@router.post("/disconnect", response_model=DisconnectOut)
def oauth_disconnect(
    channel_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ch = _channel(db, channel_id)
    done = youtube_oauth.disconnect(db, ch)
    db.commit()
    return DisconnectOut(channel_id=channel_id, disconnected=done)


def _page(message: str, *, ok: bool = True) -> str:
    color = "#16a34a" if ok else "#dc2626"
    label = "YouTube connected" if ok else "Connection error"
    return (
        f"<!doctype html><meta charset=utf-8><title>{label}</title>"
        f"<div style=\"font:16px/1.5 system-ui;max-width:32rem;margin:15vh auto;padding:0 1rem\">"
        f"<h1 style=\"color:{color};font-size:1.25rem\">{label}</h1><p>{message}</p></div>"
    )
