# SECURITY

Review of the ARCHITECTURE §8 checklist against the implementation.

| Control | Status | Where |
|---|---|---|
| All provider calls server-side; no keys in the frontend bundle | ✅ | Providers live in `api/app/providers/*`; the SPA only calls `/api/*` with a bearer token. `grep` the built bundle — no secrets. |
| Provider keys & YouTube OAuth tokens encrypted at rest | ✅ | `core/security.encrypt_secret` (Fernet, key = `sha256(APP_SECRET_KEY)`); `youtube_credentials.access_token_enc` / `refresh_token_enc`. `.env` holds only `APP_SECRET_KEY` + bootstrap keys. |
| JWT auth on every non-public route | ✅ | `api/app/api/deps.get_current_user` on all routers except `GET /api/health`, the OAuth `callback` (protected by a signed `state`), and the webhook receivers (protected by provider signature). |
| Admin seeded from env | ✅ | `db/seed.py` from `ADMIN_EMAIL` / `ADMIN_PASSWORD`; argon2 hash. `/api/admin/*` additionally requires `role == admin`. |
| Self-service registration | gated | `POST /api/auth/register` works only for the **first** user (→ admin) unless `AUTH_ALLOW_REGISTRATION=true` (then → editor). `GET /api/auth/config` tells the login page whether to show the tab. |
| Password reset | ✅ (no email transport) | `POST /api/auth/forgot-password` never enumerates users, always 200; issues a 30-min JWT bound to a fingerprint of the current password hash (⇒ single-use, auto-invalidated when the password changes). The link is logged (`WARNING`) and, outside production, returned in the response for a self-hosted operator. `POST /api/auth/reset-password` consumes it. Wiring an SMTP/email provider is the only follow-up. |
| Auth brute-force | ✅ | all `/api/auth/*` POSTs share the login rate-limit bucket. |
| Webhook endpoints verify signature / token | ✅ | `routes/webhooks.py`: Twilio `RequestValidator` when `TWILIO_AUTH_TOKEN` set; Meta `hub.verify_token` on GET. Unset ⇒ processed but logged `WARNING` as unverified (dev only). |
| Rate limiting on auth + write routes | ✅ | `core/ratelimit.RateLimitMiddleware` — fixed window per IP: `/api/auth/login` at `RATE_LIMIT_LOGIN_PER_MIN` (10), write routes (`/api/jobs`, `/api/channels`, `/api/scheduler/run`, `/api/notifications/test`) at `RATE_LIMIT_WRITE_PER_MIN` (60). `RATE_LIMIT_ENABLED=true` in prod. |
| Input validation on every route | ✅ | Pydantic request models throughout `api/app/schemas/`; `AppError` → structured JSON. |
| File handling: generated keys only, storage root jail | ✅ | `LocalStorage._abs` rejects any key escaping the root; every artifact key is `<kind>/<job_id>/<name>` built server-side. `GET /api/storage/{key}` is auth-gated and jailed. |
| CORS locked to the dashboard origin | ✅ | `CORSMiddleware(allow_origins=settings.cors_origin_list)`; set `CORS_ORIGINS` to the single `PUBLIC_HOST`. |
| Secret redaction in logs | ✅ | `core/logging.RedactingFilter` scrubs `sk-…`, `sk-ant-…`, Twilio SIDs, and `key/token/secret/password=…` patterns on every log record. Covered by `tests/test_security.py`. |
| Copyright / media licensing | ✅ | `visual_assets` / `music_tracks` store `license` + `rights_verified`; `timeline` refuses unverified assets unless `allow_unverified_media`. |
| Quota abuse (YouTube) | ✅ | `services/upload.check_quota` refuses an upload projected to cross `YT_DAILY_QUOTA_UNITS`. |
| Test mode never publishes / never pays | ✅ | `test_run` jobs force `StubYouTube` and route real WhatsApp providers to the console logger. |

## Hardening notes

- `.env.prod` must be `chmod 600`, owned by the deploy user, never committed
  (`.gitignore` covers `.env.prod`).
- Postgres and Redis expose **no** host ports in `docker-compose.prod.yml`;
  only `api` publishes `:8000`. Terminate TLS at a reverse proxy.
- The container runs as non-root (`uid 10001`) with `tini` as PID 1.
- Rotating `APP_SECRET_KEY` invalidates all existing JWTs and makes stored
  Fernet ciphertext undecryptable — YouTube channels must be reconnected.
  Do it during a maintenance window.
- Trust `X-Forwarded-For` only from your proxy; the limiter uses its first hop.

## Reporting

No public disclosure process — this is a self-hosted single-tenant tool.
File issues in the repo tracker.
