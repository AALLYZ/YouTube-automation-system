"""RQ queue wiring. Optional: the API runs the pipeline inline unless JOBS_ASYNC=true."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings

QUEUE_NAME = "pipeline"


@lru_cache
def get_redis():
    from redis import Redis

    return Redis.from_url(settings.redis_url)


@lru_cache
def get_queue():
    from rq import Queue

    return Queue(QUEUE_NAME, connection=get_redis(), default_timeout=3600)


def enqueue_pipeline(job_id: int):
    from app.workers.tasks import run_pipeline_task

    return get_queue().enqueue(run_pipeline_task, job_id, job_timeout=3600, result_ttl=86400)
