# ---- stage 1: build the dashboard ----
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- stage 2: api + worker runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_DIST=/app/web/dist \
    STORAGE_LOCAL_ROOT=/data/storage

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg postgresql-client tini \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app
COPY api/pyproject.toml ./
COPY api/app ./app
COPY api/alembic ./alembic
COPY api/alembic.ini ./
RUN uv pip install --system -e .

COPY --from=web /web/dist ./web/dist
COPY api/docker-entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint && mkdir -p /data/storage

RUN useradd -m -u 10001 app && chown -R app:app /app /data
USER app

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
