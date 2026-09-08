from __future__ import annotations

import os
import shutil

from app.core.config import settings
from app.providers.base import StorageProvider


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: str | None = None) -> None:
        self.root = os.path.abspath(root or settings.storage_local_root)
        os.makedirs(self.root, exist_ok=True)

    def _abs(self, key: str) -> str:
        key = key.lstrip("/")
        path = os.path.abspath(os.path.join(self.root, key))
        if not path.startswith(self.root + os.sep) and path != self.root:
            raise ValueError(f"key escapes storage root: {key}")
        return path

    def put(self, local_path: str, key: str) -> str:
        dst = self._abs(key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.abspath(local_path) != dst:
            shutil.copy2(local_path, dst)
        return key

    def get(self, key: str, local_path: str) -> str:
        src = self._abs(key)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        shutil.copy2(src, local_path)
        return local_path

    def open_path(self, key: str) -> str:
        return self._abs(key)

    def url(self, key: str) -> str:
        return f"{settings.public_host.rstrip('/')}/api/storage/{key.lstrip('/')}"

    def exists(self, key: str) -> bool:
        return os.path.exists(self._abs(key))

    def delete(self, key: str) -> None:
        path = self._abs(key)
        if os.path.isfile(path):
            os.remove(path)

    def delete_prefix(self, prefix: str) -> int:
        root = self._abs(prefix)
        if not os.path.isdir(root):
            return 0
        count = sum(len(files) for _, _, files in os.walk(root))
        shutil.rmtree(root, ignore_errors=True)
        return count
