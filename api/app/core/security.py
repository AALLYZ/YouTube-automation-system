"""Auth (JWT + argon2) and secret encryption (Fernet) helpers."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
from typing import Any, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import settings

_ph = PasswordHasher()
_JWT_ALG = "HS256"
_ACCESS_TTL = dt.timedelta(hours=12)
_RESET_TTL = dt.timedelta(minutes=30)


# ---------------- Passwords ----------------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# ---------------- JWT ----------------
def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + _ACCESS_TTL,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.app_secret_key, algorithm=_JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.app_secret_key, algorithms=[_JWT_ALG])


# ---------------- Password-reset tokens ----------------
def password_fingerprint(password_hash: str) -> str:
    """Short digest of the current hash — ties a reset token to one password."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:12]


def create_reset_token(user_id: int, password_hash: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "pwd_reset",
            "pv": password_fingerprint(password_hash),
            "iat": now,
            "exp": now + _RESET_TTL,
        },
        settings.app_secret_key,
        algorithm=_JWT_ALG,
    )


def decode_reset_token(token: str) -> tuple[int, str]:
    """Return (user_id, password_fingerprint); raises jwt errors / ValueError."""
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[_JWT_ALG])
    if payload.get("type") != "pwd_reset":
        raise ValueError("not a reset token")
    return int(payload["sub"]), str(payload.get("pv", ""))


# ---------------- Secret encryption ----------------
def _fernet() -> Fernet:
    # Derive a stable 32-byte urlsafe key from APP_SECRET_KEY.
    digest = hashlib.sha256(settings.app_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
