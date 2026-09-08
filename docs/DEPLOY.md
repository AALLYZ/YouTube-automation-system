# DEPLOY

Production runbook for the YouTube Automation platform.

## Topology

```
        ┌── TLS reverse proxy (Caddy / nginx / Traefik)  ── PUBLIC_HOST
        │
   ┌────┴─────┐        ┌──────────┐        ┌──────────┐
   │   api    │◀──────▶│  redis   │◀──────▶│  worker  │
   │ (uvicorn)│        └──────────┘        │ (RQ)     │
   └────┬─────┘                            └────┬─────┘
        │            ┌──────────┐               │
        └───────────▶│ postgres │◀──────────────┘
                     └──────────┘
        api + worker share the `storage` volume (/data/storage)
```

One API process, one (or more) RQ workers, Postgres, Redis. `api/Dockerfile`
builds both the dashboard and the Python image; `worker` reuses the image with a
different command.

## First deploy

```bash
git clone <repo> && cd <repo>
cp .env.prod.example .env.prod
# fill in: APP_SECRET_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL/PASSWORD, PUBLIC_HOST,
# CORS_ORIGINS, provider keys. Generate the secret:
python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

docker compose -f docker-compose.prod.yml up -d --build
```

On boot the `api` container runs `alembic upgrade head` and seeds the admin user
+ a default channel (`RUN_MIGRATIONS=true`, `RUN_SEED=true` — the worker has
`RUN_MIGRATIONS=false`). Verify:

```bash
curl -s localhost:8000/api/health            # {"status":"ok"} once db+redis are up
# then, authenticated:
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"…"}' | jq -r .access_token)
curl -s localhost:8000/api/health/deep -H "authorization: Bearer $TOKEN" | jq .status
```

Put a TLS proxy in front so `PUBLIC_HOST` serves `https://…` → `api:8000`.
The proxy must forward `X-Forwarded-For` (used for rate limiting) and the real
`Host`. The dashboard is served by the same origin at `/`.

## Configure a channel to go live

1. Sign in at `PUBLIC_HOST` → **Settings**: create/adjust the channel, set
   `approval_mode`, `automation_enabled`, `daily_video_limit`, `publish_time`.
2. **YouTube**: create a Google OAuth *Web* client (YouTube Data API v3 on),
   authorized redirect `PUBLIC_HOST/api/youtube/oauth/callback`, app in Testing
   with the channel owner as a test user. Set `GOOGLE_CLIENT_ID/SECRET`,
   `YOUTUBE_PROVIDER=google`, then **Connect YouTube** on the dashboard.
3. **WhatsApp**: `NOTIFIER_PROVIDER=twilio` (+ SID/token/from) or `meta_cloud`;
   set the channel's `whatsapp_cfg.to` or `WHATSAPP_TO`. Point the Twilio
   messaging status callback at `PUBLIC_HOST/api/webhooks/twilio`.
4. Run one **test job** (Automation → Create & run, *test run* on): it renders
   and "uploads" via the stub, never touching the real account.
5. Flip the channel to real mode and let the scheduler (`SCHEDULER_ENABLED=true`)
   create the daily job at `publish_time` UTC.

## Operations

| Task | Command |
|---|---|
| Logs | `docker compose -f docker-compose.prod.yml logs -f api worker` |
| Redeploy | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| Migrations only | `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head` |
| Scale workers | `docker compose -f docker-compose.prod.yml up -d --scale worker=3` |
| Backup | `./scripts/backup.sh` (db `.sql.gz` + storage `.tgz` into `./backups/`) |
| Restore | see header of `scripts/backup.sh` |
| Prune old artifacts | `POST /api/admin/retention` or `docker … run --rm api python -m app.services.retention --days 30` (also runs nightly 03:30 UTC when the scheduler is on) |
| Rotate `APP_SECRET_KEY` | re-encrypts nothing automatically — YouTube creds must be reconnected; do it during a maintenance window |

## Health & monitoring

- `GET /api/health` — public, DB + Redis; use for the proxy / load-balancer probe.
- `GET /api/health/deep` — auth; DB + Redis + FFmpeg + every provider self-check.
- `GET /api/overview` — auth; jobs, cost, quota, failures at a glance.
- `GET /api/logs`, `GET /api/usage` — auth; pipeline events + per-call cost.
- Alert on: `overview.jobs.failed` rising, `youtube.quota_used_today` near
  `quota_daily_limit` (10 000; an upload ≈ 1650), `notifications.failed` > 0.

## Backups & retention

- **Schedule** `scripts/backup.sh` via host cron (e.g. daily 02:00). It keeps the
  14 most recent dumps locally; copy `./backups/` off-box (S3, restic, …).
- **Artifact retention**: media for terminal jobs older than
  `ARTIFACT_RETENTION_DAYS` (default 30) is deleted nightly; DB rows are kept.
  `jobs.artifacts_pruned_at` marks done work so it is idempotent.

## Security

See `docs/SECURITY.md` for the full checklist and where each control lives.
Minimum before exposing `PUBLIC_HOST`:

- Real `APP_SECRET_KEY` and `ADMIN_PASSWORD`; `.env.prod` is `chmod 600` and never committed.
- `CORS_ORIGINS` = the dashboard origin only.
- `RATE_LIMIT_ENABLED=true`.
- TLS at the proxy; Postgres/Redis have **no** published ports in the prod compose.
- Twilio/Meta webhook signature verification requires `TWILIO_AUTH_TOKEN` /
  `META_VERIFY_TOKEN` to be set (unset ⇒ requests are processed but logged as unverified).
