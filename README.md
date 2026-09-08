# YouTube Automation System

End-to-end pipeline that turns a channel/niche config into published YouTube
videos:

```
topic → research → script → script-QA → voice → visuals → subtitles → timeline
      → render → thumbnail → metadata → final-QA → approval → upload → notify
```

Every external capability (LLM, research, voice, images, stock media, YouTube,
WhatsApp, storage) sits behind a provider interface with a `stub`
implementation, so **the whole pipeline runs offline with zero API keys** and
produces a real MP4. Swap in real providers via environment variables.

See [`docs/`](docs/) — [ARCHITECTURE](docs/ARCHITECTURE.md),
[DATA_FLOW](docs/DATA_FLOW.md), [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md),
[DEPLOY](docs/DEPLOY.md), [SECURITY](docs/SECURITY.md),
[PROJECT_STATUS](docs/PROJECT_STATUS.md).

## Stack

FastAPI (modular monolith) · SQLAlchemy 2 + Alembic · PostgreSQL · Redis + RQ ·
APScheduler · FFmpeg (`static-ffmpeg`) · React + Vite + Tailwind dashboard.

## Local development

Prereqs: Docker, Node 20+, and `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
docker compose up -d                 # Postgres :5433, Redis :6380

cd api
cp ../.env.example .env               # edit as needed
make install && make migrate && make seed
make web                              # build the dashboard (optional)
make run                              # http://localhost:8090  (dashboard at /, API docs at /docs)
make test                             # 82 tests
make coverage                         # with the 70% gate
```

Async workers (optional): set `JOBS_ASYNC=true`, run `make worker`.
Dashboard dev server with hot reload: `make web-dev` (proxies `/api` → `:8090`).

## Production

```bash
cp .env.prod.example .env.prod        # fill in secrets (gitignored)
docker compose -f docker-compose.prod.yml up -d --build
```

api + worker + Postgres + Redis; the api container migrates + seeds on boot and
serves the dashboard at `/`. Full runbook in [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Status

**All 10 phases complete.** 82 tests, ~82% coverage, CI on push/PR.
Tagged `phase-1` … `phase-10`.
