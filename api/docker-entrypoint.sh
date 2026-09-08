#!/bin/sh
set -e

# Wait for the database (best-effort; compose healthchecks already gate this).
if [ -n "$DATABASE_URL" ]; then
  echo "entrypoint: waiting for database…"
  for i in $(seq 1 30); do
    if python -c "
import sys, sqlalchemy as sa
from app.core.config import settings
try:
    sa.create_engine(settings.database_url).connect().close()
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      break
    fi
    sleep 2
  done
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "entrypoint: running migrations…"
  alembic upgrade head
fi

if [ "${RUN_SEED:-false}" = "true" ]; then
  echo "entrypoint: seeding admin + default channel…"
  python -m app.db.seed || true
fi

exec "$@"
