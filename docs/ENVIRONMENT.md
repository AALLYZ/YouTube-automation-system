# ENVIRONMENT VARIABLES

All config is env-driven (`pydantic-settings`). `.env` for local, real secret
manager in production. Provider **keys** may instead be stored encrypted in the
DB via the Setup Wizard — `.env` only needs `APP_SECRET_KEY` + whatever you want
to bootstrap.

## Core

| Var | Required | Example / default | Notes |
|---|---|---|---|
| `APP_ENV` | yes | `development` | `development` \| `production` |
| `APP_SECRET_KEY` | yes | (32+ random bytes, base64) | JWT signing + Fernet key derivation. **Rotate = invalidates stored secrets & sessions** |
| `PUBLIC_HOST` | yes (prod) | `https://auto.example.com` | Used for OAuth redirect + webhook URLs |
| `PORT` | no | `3000` | API port |
| `DATABASE_URL` | yes | `postgresql+psycopg://user:pass@localhost:5432/ytauto` | |
| `REDIS_URL` | yes | `redis://localhost:6379/0` | |
| `CORS_ORIGINS` | no | `http://localhost:5173` | dashboard origin(s), comma-sep |
| `ADMIN_EMAIL` | yes | `you@example.com` | seeded on first boot |
| `ADMIN_PASSWORD` | yes (first boot) | (strong) | argon2-hashed then may be removed |
| `STORAGE_PROVIDER` | no | `local` | `local` \| `s3` |
| `STORAGE_LOCAL_ROOT` | no | `./storage` | |
| `LOG_LEVEL` | no | `INFO` | |

## Provider selection

| Var | Default | Options |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `gemini` \| `stub` |
| `RESEARCH_PROVIDER` | `stub` | `tavily` \| `brave` \| `serpapi` \| `stub` |
| `VOICE_PROVIDER` | `stub` | `elevenlabs` \| `openai` \| `local` \| `stub` |
| `IMAGE_PROVIDER` | `stub` | `openai` \| `stability` \| `replicate` \| `stub` |
| `VIDEO_CLIP_PROVIDER` | `stub` | `replicate` \| `stub` |
| `STOCK_PROVIDER` | `stub` | `pexels` \| `pixabay` \| `stub` |
| `YOUTUBE_PROVIDER` | `stub` | `google` \| `stub` |
| `NOTIFIER_PROVIDER` | `console` | `twilio` \| `meta_cloud` \| `console` \| `stub` |

## AI

| Var | Required when | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | `AI_PROVIDER=anthropic` | `sk-ant-...` |
| `MODEL` | no | `claude-sonnet-4-6` (verify current) |
| `OPENAI_API_KEY` | `AI_PROVIDER=openai` or OpenAI voice/image | `sk-...` |
| `GEMINI_API_KEY` | `AI_PROVIDER=gemini` | — |

## Research

| Var | Required when |
|---|---|
| `TAVILY_API_KEY` | `RESEARCH_PROVIDER=tavily` |
| `BRAVE_API_KEY` | `RESEARCH_PROVIDER=brave` |
| `SERPAPI_API_KEY` | `RESEARCH_PROVIDER=serpapi` |

## Voice

| Var | Required when |
|---|---|
| `ELEVENLABS_API_KEY` | `VOICE_PROVIDER=elevenlabs` |
| `ELEVENLABS_VOICE_ID` | optional default voice |
| `OPENAI_API_KEY` | `VOICE_PROVIDER=openai` |

## Visuals

| Var | Required when |
|---|---|
| `OPENAI_API_KEY` | `IMAGE_PROVIDER=openai` |
| `STABILITY_API_KEY` | `IMAGE_PROVIDER=stability` |
| `REPLICATE_API_TOKEN` | `IMAGE_PROVIDER=replicate` or `VIDEO_CLIP_PROVIDER=replicate` |
| `PEXELS_API_KEY` | `STOCK_PROVIDER=pexels` |
| `PIXABAY_API_KEY` | `STOCK_PROVIDER=pixabay` |

## YouTube (OAuth 2.0 Web client)

| Var | Required when | Notes |
|---|---|---|
| `GOOGLE_CLIENT_ID` | `YOUTUBE_PROVIDER=google` | from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | same | |
| `GOOGLE_OAUTH_REDIRECT` | same | `${PUBLIC_HOST}/api/youtube/oauth/callback` |
| `YOUTUBE_DEFAULT_PRIVACY` | no | `private` \| `unlisted` \| `public` |
| `YOUTUBE_DEFAULT_CATEGORY_ID` | no | `27` (Education) etc. |

Refresh token stored **encrypted in DB** (`youtube_uploads` channel credential row), not env.

## WhatsApp

### Twilio

| Var | Required when |
|---|---|
| `TWILIO_ACCOUNT_SID` | `NOTIFIER_PROVIDER=twilio` |
| `TWILIO_AUTH_TOKEN` | same |
| `TWILIO_WHATSAPP_FROM` | same | `whatsapp:+1415...` |
| `WHATSAPP_TO` | same | default recipient `whatsapp:+...` |
| `TWILIO_STATUS_CALLBACK` | no | `${PUBLIC_HOST}/api/webhooks/twilio` |

### Meta Cloud API

| Var | Required when |
|---|---|
| `META_WABA_TOKEN` | `NOTIFIER_PROVIDER=meta_cloud` |
| `META_PHONE_NUMBER_ID` | same |
| `META_VERIFY_TOKEN` | same (webhook verification) |

## Storage (S3)

| Var | Required when |
|---|---|
| `S3_BUCKET` / `S3_REGION` / `S3_ENDPOINT` | `STORAGE_PROVIDER=s3` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | same |

## Automation / limits

| Var | Default | Notes |
|---|---|---|
| `SCHEDULER_ENABLED` | `false` | master switch for automation |
| `MAX_CONCURRENT_JOBS` | `1` | RQ worker concurrency |
| `MAX_STAGE_RETRIES` | `3` | per step |
| `RETRY_BACKOFF_BASE_SEC` | `10` | `base * 2^attempt` + jitter |
| `DAILY_VIDEO_LIMIT` | `3` | scheduler hard cap |
| `ARTIFACT_RETENTION_DAYS` | `30` | prune media of completed jobs |
| `YT_DAILY_QUOTA_UNITS` | `10000` | refuse uploads past projected usage |

A machine-readable template ships as `.env.example` (Phase 2).
