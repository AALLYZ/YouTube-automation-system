"""Structured error types for the pipeline and API."""
from __future__ import annotations

from typing import Any, Optional


class ErrorCode:
    # generic
    UNKNOWN = "UNKNOWN"
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    AUTH = "AUTH_ERROR"
    CONFIG = "CONFIG_ERROR"
    # providers
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_BAD_RESPONSE = "PROVIDER_BAD_RESPONSE"
    # pipeline
    MISSING_ASSET = "MISSING_ASSET"
    RENDER_FAILED = "RENDER_FAILED"
    QA_FAILED = "QA_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UPLOAD_FAILED = "UPLOAD_FAILED"


RETRYABLE_CODES = {
    ErrorCode.PROVIDER_RATE_LIMIT,
    ErrorCode.PROVIDER_UNAVAILABLE,
    ErrorCode.RENDER_FAILED,
    ErrorCode.UPLOAD_FAILED,
    ErrorCode.UNKNOWN,
}


class AppError(Exception):
    """Base application error."""

    http_status = 400

    def __init__(
        self,
        message: str,
        *,
        code: str = ErrorCode.UNKNOWN,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error_code": self.code, "message": self.message, "context": self.context}


class NotFoundError(AppError):
    http_status = 404

    def __init__(self, message: str = "Not found", **kw: Any) -> None:
        super().__init__(message, code=ErrorCode.NOT_FOUND, **kw)


class AuthError(AppError):
    http_status = 401

    def __init__(self, message: str = "Not authenticated", **kw: Any) -> None:
        super().__init__(message, code=ErrorCode.AUTH, **kw)


class StageError(AppError):
    """Raised inside a pipeline stage. `retryable` drives the retry policy."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        code: str = ErrorCode.UNKNOWN,
        retryable: Optional[bool] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code=code, context=context)
        self.stage = stage
        self.retryable = RETRYABLE_CODES.__contains__(code) if retryable is None else retryable

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update({"stage": self.stage, "retryable": self.retryable})
        return d
