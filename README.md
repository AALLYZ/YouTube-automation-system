# YouTube Automation System

End-to-end pipeline that turns a channel/niche config into published YouTube
videos: topic → research → script → QA → voice → visuals → subtitles → render →
thumbnail → metadata → QA → (approval) → upload → WhatsApp notify.

See [`docs/`](docs/) for architecture, data flow, API requirements, environment,
the phased implementation plan, and current status.

## Stack

FastAPI (modular monolith) · SQLAlchemy 2 + Alembic · PostgreSQL · Redis + RQ ·
APScheduler · FFmpeg (via `imageio-ffmpeg`) · React/Vite dashboard.
Every external capability sits behind a provider interface with a `stub`
implementation, so the whole pipeline runs offline with zero API keys.

## Local development

Prereqs: Docker, and `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
# 1. infra (Postgres on :5433, Redis on :6380 to avoid clashes)
docker compose up -d

# 2. api
cd api
cp ../.env.example .env      # then edit; a generated .env may already exist
make install
make migrate
make seed
make run                     # http://localhost:8090  (docs at /docs)

# 3. tests
make test
```

## Status

Phase 2 (Foundation) complete. Next: Phase 3 (AI pipeline — topic, research,
script, QA). Track progress in [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).
