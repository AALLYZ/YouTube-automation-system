from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("Starting ytauto API in %s mode", settings.app_env)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="YouTube Automation API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    from app.api.routes import auth, channels, health, scripts, storage, topics

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(channels.router, prefix="/api")
    app.include_router(topics.router, prefix="/api")
    app.include_router(scripts.router, prefix="/api")
    app.include_router(storage.router, prefix="/api")

    @app.get("/")
    def root() -> dict:
        return {"service": "youtube-automation", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
