"""Google OAuth 2.0 (web flow) for connecting a channel's YouTube account.

State is a short-lived signed token (HS256, via ``core.security``) carrying the
channel id, so the callback needs no server-side session store and is CSRF-safe.
Access / refresh tokens are stored Fernet-encrypted on ``youtube_credentials``.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import jwt

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.security import create_access_token, decrypt_secret, decode_token, encrypt_secret
from app.models.channel import Channel, YouTubeCredential

log = get_logger("youtube.oauth")

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_STATE_PURPOSE = "yt_oauth"


def _require_config() -> None:
    missing = [
        n
        for n, v in (
            ("GOOGLE_CLIENT_ID", settings.google_client_id),
            ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
        )
        if not v
    ]
    if missing:
        raise AppError(f"{', '.join(missing)} not configured", code=ErrorCode.CONFIG)


def _redirect_uri() -> str:
    return settings.google_oauth_redirect or (
        settings.public_host.rstrip("/") + "/api/youtube/oauth/callback"
    )


def _client_config() -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
            "redirect_uris": [_redirect_uri()],
        }
    }


def _flow(state: Optional[str] = None):
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        _client_config(), scopes=OAUTH_SCOPES, state=state, redirect_uri=_redirect_uri()
    )


# ---------------- state ----------------
def sign_state(channel_id: int) -> str:
    return create_access_token(
        f"{_STATE_PURPOSE}:{channel_id}",
        extra={"purpose": _STATE_PURPOSE, "channel_id": channel_id},
    )


def verify_state(state: str) -> int:
    try:
        payload = decode_token(state)
    except jwt.PyJWTError as exc:
        raise AppError("Invalid or expired OAuth state", code=ErrorCode.AUTH) from exc
    if payload.get("purpose") != _STATE_PURPOSE or "channel_id" not in payload:
        raise AppError("OAuth state is not valid for this flow", code=ErrorCode.AUTH)
    return int(payload["channel_id"])


# ---------------- flow ----------------
def build_authorization_url(channel_id: int) -> tuple[str, str]:
    _require_config()
    state = sign_state(channel_id)
    url, _ = _flow(state=state).authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return url, state


def complete_oauth(db, *, state: str, code: str) -> YouTubeCredential:
    _require_config()
    channel_id = verify_state(state)
    channel = db.get(Channel, channel_id)
    if not channel:
        raise AppError("Channel not found for this OAuth state", code=ErrorCode.NOT_FOUND)

    flow = _flow(state=state)
    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Token exchange failed: {exc}", code=ErrorCode.PROVIDER_BAD_RESPONSE) from exc

    creds = flow.credentials
    if not creds.refresh_token:
        raise AppError(
            "Google did not return a refresh token; revoke the app's access and reconnect",
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
        )

    yt_channel_id, yt_title = _fetch_channel_identity(creds)
    return _upsert_credential(db, channel_id, creds, yt_channel_id, yt_title)


def _fetch_channel_identity(creds) -> tuple[Optional[str], Optional[str]]:
    try:
        from googleapiclient.discovery import build

        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items") or []
        if items:
            return items[0]["id"], items[0]["snippet"].get("title")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not fetch YouTube channel identity: %s", exc)
    return None, None


def _upsert_credential(db, channel_id, creds, yt_channel_id, yt_title) -> YouTubeCredential:
    from sqlalchemy import select

    row = db.execute(
        select(YouTubeCredential).where(YouTubeCredential.channel_id == channel_id)
    ).scalar_one_or_none()
    if not row:
        row = YouTubeCredential(channel_id=channel_id)
        db.add(row)

    now = dt.datetime.now(dt.timezone.utc)
    row.youtube_channel_id = yt_channel_id
    row.channel_title = yt_title
    row.access_token_enc = encrypt_secret(creds.token) if creds.token else None
    row.refresh_token_enc = encrypt_secret(creds.refresh_token)
    row.token_expiry = _as_utc(creds.expiry)
    row.scopes = " ".join(creds.scopes or OAUTH_SCOPES)
    row.connected_at = now
    db.flush()
    log.info("connected channel %s to YouTube channel %s (%s)", channel_id, yt_channel_id, yt_title)
    return row


def _as_utc(value) -> Optional[dt.datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


# ---------------- credential use ----------------
def get_credential(db, channel: Channel) -> Optional[YouTubeCredential]:
    from sqlalchemy import select

    return db.execute(
        select(YouTubeCredential).where(YouTubeCredential.channel_id == channel.id)
    ).scalar_one_or_none()


def credential_dict(db, channel: Channel) -> Optional[dict[str, Any]]:
    """Return a provider-ready credential dict, refreshing the access token if stale."""
    row = get_credential(db, channel)
    if not row or not row.refresh_token_enc:
        return None

    refresh_token = decrypt_secret(row.refresh_token_enc)
    token = decrypt_secret(row.access_token_enc) if row.access_token_enc else None
    scopes = (row.scopes or " ".join(OAUTH_SCOPES)).split()

    expiry = _as_utc(row.token_expiry)
    stale = (not token) or (expiry is not None and expiry <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2))
    if stale and settings.google_client_id and settings.google_client_secret:
        token, expiry = _refresh(refresh_token, scopes)
        row.access_token_enc = encrypt_secret(token) if token else None
        row.token_expiry = expiry
        db.flush()

    return {
        "token": token,
        "refresh_token": refresh_token,
        "token_uri": _TOKEN_URI,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "scopes": scopes,
    }


def _refresh(refresh_token: str, scopes: list[str]) -> tuple[Optional[str], Optional[dt.datetime]]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=_TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=scopes,
        )
        creds.refresh(Request())
        return creds.token, _as_utc(creds.expiry)
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Failed to refresh YouTube token: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc


def disconnect(db, channel: Channel) -> bool:
    row = get_credential(db, channel)
    if not row:
        return False
    db.delete(row)
    db.flush()
    return True


def connection_status(db, channel: Channel) -> dict[str, Any]:
    row = get_credential(db, channel)
    return {
        "channel_id": channel.id,
        "provider": settings.youtube_provider,
        "configured": bool(settings.google_client_id and settings.google_client_secret),
        "connected": bool(row and row.refresh_token_enc),
        "youtube_channel_id": row.youtube_channel_id if row else None,
        "youtube_channel_title": row.channel_title if row else None,
        "connected_at": row.connected_at.isoformat() if row and row.connected_at else None,
        "scopes": (row.scopes.split() if row and row.scopes else []),
        "token_expires_at": (
            _as_utc(row.token_expiry).isoformat() if row and row.token_expiry else None
        ),
    }
