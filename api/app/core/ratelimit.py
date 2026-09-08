"""Minimal in-process fixed-window rate limiter + ASGI middleware.

One API process (modular monolith) → in-memory counters are sufficient. Disabled
in tests via RATE_LIMIT_ENABLED=false.
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ratelimit")

# path prefix -> ("bucket name", per-minute limit)
_RULES: list[tuple[str, str]] = [
    ("/api/auth/login", "login"),
]
_WRITE_PREFIXES = ("/api/jobs", "/api/channels", "/api/scheduler/run", "/api/notifications/test")


class _Window:
    __slots__ = ("count", "reset_at")

    def __init__(self, reset_at: float) -> None:
        self.count = 0
        self.reset_at = reset_at


class FixedWindowLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Window] = {}

    def hit(self, key: tuple[str, str], limit: int, window: float = 60.0) -> tuple[bool, int]:
        now = time.monotonic()
        w = self._buckets.get(key)
        if w is None or now >= w.reset_at:
            w = _Window(now + window)
            self._buckets[key] = w
        w.count += 1
        remaining = max(0, limit - w.count)
        return w.count <= limit, remaining


_limiter = FixedWindowLimiter()


def _client_ip(scope: Scope) -> str:
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    fwd = headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def _rule_for(path: str, method: str) -> tuple[str, int] | None:
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    for prefix, bucket in _RULES:
        if path.startswith(prefix):
            return bucket, settings.rate_limit_login_per_min
    if any(path.startswith(p) for p in _WRITE_PREFIXES):
        return "write", settings.rate_limit_write_per_min
    return None


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        rule = _rule_for(scope.get("path", ""), scope.get("method", "GET"))
        if rule is None:
            await self.app(scope, receive, send)
            return

        bucket, limit = rule
        ip = _client_ip(scope)
        allowed, remaining = _limiter.hit((ip, bucket), limit)
        if not allowed:
            log.warning("rate limit hit: %s %s bucket=%s", ip, scope.get("path"), bucket)
            resp = JSONResponse(
                status_code=429,
                content={
                    "error_code": "RATE_LIMITED",
                    "message": f"Too many requests; limit {limit}/min for this action.",
                    "context": {"bucket": bucket},
                },
                headers={"Retry-After": "60"},
            )
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)
