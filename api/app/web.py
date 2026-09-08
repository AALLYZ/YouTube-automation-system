"""Serve the built React dashboard (web/dist) as a single-page app.

No-op when the build is absent, so the API still runs without a frontend build.
"""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.core.logging import get_logger

log = get_logger("web")

DIST = pathlib.Path(__file__).resolve().parents[2] / "web" / "dist"


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unknown paths (client routing)."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.lstrip("/").startswith(("api/", "docs", "openapi")):
                return await super().get_response("index.html", scope)
            raise


def mount_dashboard(app: FastAPI) -> bool:
    index = DIST / "index.html"
    if not index.is_file():
        log.info("dashboard build not found at %s — serving API only", DIST)

        @app.get("/", include_in_schema=False)
        def _root() -> dict:
            return {
                "service": "youtube-automation",
                "docs": "/docs",
                "health": "/api/health",
                "dashboard": "not built (run `make web`)",
            }

        return False

    app.mount("/", SPAStaticFiles(directory=str(DIST), html=True), name="dashboard")
    log.info("dashboard mounted from %s", DIST)
    return True
