"""Retry policy for pipeline stages: exponential backoff on retryable errors."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from app.core.errors import RETRYABLE_CODES, AppError
from app.core.logging import get_logger

log = get_logger("retry")

T = TypeVar("T")


def backoff_seconds(attempt: int, *, base: float, cap: float = 300.0) -> float:
    """1-indexed attempt -> delay before the *next* try."""
    return min(cap, base * (2 ** (attempt - 1)))


def run_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    base_sec: float,
    on_attempt: Callable[[int], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` up to ``max_attempts`` times, retrying only on retryable AppErrors."""
    attempt = 0
    while True:
        attempt += 1
        if on_attempt:
            on_attempt(attempt)
        try:
            return fn()
        except AppError as exc:
            retryable = getattr(exc, "retryable", exc.code in RETRYABLE_CODES)
            if not retryable or attempt >= max_attempts:
                raise
            delay = backoff_seconds(attempt, base=base_sec)
            log.warning(
                "attempt %d/%d failed (%s): %s — retrying in %.1fs",
                attempt, max_attempts, exc.code, exc.message, delay,
            )
            if delay > 0:
                sleep(delay)
