from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.enums import UserRole
from app.core.errors import AppError, AuthError, ErrorCode
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(str(user.id), {"role": user.role.value}))


@router.get("/config")
def auth_config(db: Session = Depends(get_db)) -> dict:
    """Public — lets the login page show/hide the Register tab."""
    has_users = db.execute(select(func.count(User.id))).scalar_one() > 0
    return {"registration_enabled": settings.auth_allow_registration or not has_users}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account disabled")
    return _token_for(user)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    count = db.execute(select(func.count(User.id))).scalar_one()
    if count > 0 and not settings.auth_allow_registration:
        raise AppError("Registration is disabled", code=ErrorCode.AUTH)

    email = payload.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise AppError("An account with that email already exists", code=ErrorCode.VALIDATION)

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN if count == 0 else UserRole.EDITOR,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("registered user %s (role=%s)", email, user.role.value)
    return _token_for(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()

    generic = "If that email is registered, a password reset link has been issued."
    if not user or not user.is_active:
        return ForgotPasswordResponse(message=generic)

    token = create_reset_token(user.id, user.password_hash)
    reset_url = f"{settings.public_host.rstrip('/')}/reset-password?token={token}"
    # No email transport is wired — the operator retrieves the token from logs
    # (or, outside production, from this response).
    log.warning("PASSWORD RESET for %s — link valid 30 min:\n%s", user.email, reset_url)
    return ForgotPasswordResponse(
        message=generic,
        reset_token=None if settings.is_production else token,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        user_id, pv = decode_reset_token(payload.token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Reset link has expired; request a new one") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise AuthError("Invalid reset link") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise AuthError("Invalid reset link")
    if pv != password_fingerprint(user.password_hash):
        raise AuthError("This reset link has already been used")

    user.password_hash = hash_password(payload.password)
    db.commit()
    log.info("password reset completed for %s", user.email)
    return MessageResponse(message="Password updated. You can now sign in.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
