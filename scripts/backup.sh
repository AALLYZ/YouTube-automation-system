#!/usr/bin/env bash
# Back up the production database + storage artifacts.
#
#   ./scripts/backup.sh [OUT_DIR]
#
# Produces, under OUT_DIR (default ./backups):
#   ytauto-<UTC timestamp>.sql.gz       (pg_dump of the ytauto db)
#   ytauto-<UTC timestamp>.storage.tgz  (the storage volume contents)
#
# Restore:
#   gunzip -c backups/ytauto-<ts>.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U ytauto ytauto
#   docker run --rm -v ytauto_storage:/data -v "$PWD/backups":/b alpine \
#     sh -c 'cd /data && tar xzf /b/ytauto-<ts>.storage.tgz'
set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
OUT_DIR="${1:-./backups}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"

echo "==> pg_dump"
$COMPOSE exec -T db pg_dump -U ytauto --clean --if-exists ytauto | gzip > "$OUT_DIR/ytauto-$TS.sql.gz"

echo "==> storage archive"
STORAGE_VOL="$($COMPOSE config --volumes | grep -E '(^|_)storage$' | head -1 || echo storage)"
PROJECT="$(basename "$PWD" | tr '[:upper:] ' '[:lower:]-')"
docker run --rm \
  -v "${PROJECT}_${STORAGE_VOL}:/data:ro" \
  -v "$(cd "$OUT_DIR" && pwd):/backup" \
  alpine sh -c "cd /data && tar czf /backup/ytauto-$TS.storage.tgz ."

echo "==> retention: keep the 14 most recent of each kind"
ls -1t "$OUT_DIR"/ytauto-*.sql.gz      2>/dev/null | tail -n +15 | xargs -r rm --
ls -1t "$OUT_DIR"/ytauto-*.storage.tgz 2>/dev/null | tail -n +15 | xargs -r rm --

echo "done: $OUT_DIR/ytauto-$TS.*"
