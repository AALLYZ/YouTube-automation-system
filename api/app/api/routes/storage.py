from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.models.user import User
from app.providers.registry import get_storage

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/{key:path}")
def get_object(key: str, _: User = Depends(get_current_user)) -> FileResponse:
    storage = get_storage()
    if not storage.exists(key):
        raise NotFoundError(f"Object not found: {key}")
    path = storage.open_path(key)
    return FileResponse(path, filename=os.path.basename(path))
