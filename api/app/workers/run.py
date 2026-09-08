"""Entrypoint for an RQ worker process: `python -m app.workers.run`."""
from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.workers.queue import QUEUE_NAME, get_redis

log = get_logger("worker")


def main() -> None:
    configure_logging()
    from rq import Queue, Worker

    conn = get_redis()
    log.info("starting RQ worker on queue %r", QUEUE_NAME)
    Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn).work(with_scheduler=True)


if __name__ == "__main__":
    main()
