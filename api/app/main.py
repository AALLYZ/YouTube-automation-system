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
    if settings.scheduler_enabled:
        from app.scheduler.scheduler import start_scheduler

        start_scheduler()
    try:
        yield
    finally:
        from app.scheduler.scheduler import stop_scheduler

        stop_scheduler()


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

    from app.api.routes import (
        auth,
        channels,
        health,
        jobs,
        logs,
        notifications,
        overview,
        scheduler,
        scripts,
        storage,
        topics,
        webhooks,
        youtube,
    )

    for r in (
        health, auth, channels, topics, scripts, jobs, storage, youtube,
        notifications, webhooks, scheduler, overview, logs,
    ):
        app.include_router(r.router, prefix="/api")

    from app.web import mount_dashboard

    mount_dashboard(app)
    return app


app = create_app()
