"""Environment-driven provider selection.

Phase 2 wires storage only. Later phases register AI / voice / image / stock /
youtube / notifier adapters here, keyed by the *_PROVIDER settings.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.providers.base import StorageProvider


@lru_cache
def get_storage() -> StorageProvider:
    if settings.storage_provider == "s3":
        from app.providers.storage.s3 import S3Storage  # noqa: not implemented until Phase 10

        return S3Storage()
    from app.providers.storage.local import LocalStorage

    return LocalStorage()
