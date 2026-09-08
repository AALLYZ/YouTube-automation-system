from __future__ import annotations

from collections.abc import Iterator

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import decode_token
from app.db.base import SessionLocal
from app.models.user import User


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc

    user = db.get(User, int(payload.get("sub", 0)))
    if not user or not user.is_active:
        raise AuthError("User not found or inactive")
    return user
