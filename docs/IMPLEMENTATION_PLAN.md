# IMPLEMENTATION PLAN

## Folder structure

```
youtube-automation/
├── docs/                         # this folder
├── docker-compose.yml            # postgres + redis (+ api + worker in prod profile)
├── .env.example
├── api/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory, router mount, static dashboard
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings
│   │   │   ├── security.py       # jwt, argon2, Fernet crypto helpers
│   │   │   ├── logging.py        # structured logs + secret redaction
│   │   │   ├── pricing.py        # provider price table + cost calc
│   │   │   └── errors.py         # StageError, error codes, retryable flag
│   │   ├── db/
│   │   │   ├── base.py           # engine, Session, Base
│   │   │   └── seed.py           # admin user, default channel
│   │   ├── models/               # SQLAlchemy models (one file per group)
│   │   ├── schemas/              # Pydantic request/response + provider DTOs
│   │   ├── providers/
│   │   │   ├── base.py           # interfaces
│   │   │   ├── registry.py       # env → concrete instance
│   │   │   ├── ai/ research/ voice/ image/ video_clip/ stock/
│   │   │   ├── storage/ youtube/ notifier/
│   │   │   └── */stub.py         # a stub for every interface
│   │   ├── services/             # stage logic (no HTTP framework deps)
│   │   │   ├── topics.py research.py script.py script_qa.py voice.py
│   │   │   ├── visuals.py subtitles.py timeline.py render.py
│   │   │   ├── thumbnail.py metadata.py final_qa.py upload.py notify.py
│   │   ├── workflows/
│   │   │   ├── controller.py     # AutomationController (createJob, stage dispatch)
│   │   │   ├── pipeline.py       # stage order, run_pipeline(job_id) entrypoint
│   │   │   └── retry.py          # backoff policy
│   │   ├── workers/
│   │   │   ├── queue.py          # RQ connection, queues
│   │   │   └── tasks.py          # RQ job functions → call pipeline
│   │   ├── scheduler/
│   │   │   └── scheduler.py      # APScheduler jobs, dedup locks
│   │   ├── api/
│   │   │   ├── deps.py           # auth deps, db session dep
│   │   │   └── routes/           # auth, channels, settings, topics, scripts,
│   │   │                         # jobs, videos, youtube, notifications, logs,
│   │   │                         # setup, webhooks, health
│   │   └── utils/
│   └── tests/
└── web/                          # React + Vite + TS + Tailwind dashboard
    ├── package.json
    └── src/
        ├── pages/ (Overview, Automation, Topics, Scripts, Videos, YouTube,
        │           Notifications, Logs, Settings, Setup wizard)
        ├── components/
        └── lib/api.ts
```

## Database schema (PostgreSQL)

Enums: `job_status`, `job_step_status`, `stage`, `topic_status`, `script_status`,
`approval_mode`, `privacy_status`, `asset_source`, `notification_event`,
`notification_status`.

```
users
  id, email (uniq), password_hash, role, created_at

channels
  id, name, slug (uniq), niche, audience, language, tone, content_style,
  video_length_min, posting_frequency, timezone, is_active, created_at

channel_settings                       # 1:1 with channel, JSONB blobs per domain
  channel_id (uniq fk), approval_mode, automation_enabled,
  daily_video_limit, publish_time, privacy_default,
  topic_ai (jsonb), script_ai (jsonb), research_cfg (jsonb), voice_cfg (jsonb),
  visual_cfg (jsonb), thumbnail_cfg (jsonb), youtube_cfg (jsonb),
  whatsapp_cfg (jsonb), scoring_weights (jsonb),
  allow_unverified_media (bool), notify_events (text[])

youtube_credentials                    # per channel, encrypted
  id, channel_id (fk), youtube_channel_id, channel_title,
  access_token_enc, refresh_token_enc, token_expiry, scopes, connected_at

topics
  id, channel_id (fk), job_id (fk null), title, hook, angle, audience,
  estimated_interest, uniqueness_score, difficulty, evergreen (bool),
  search_potential, competition, total_score, status (topic_status),
  fingerprint (text, for dedup), rejected_reason, created_at
  idx(channel_id, status), uniq(channel_id, fingerprint)

research
  id, topic_id (fk), job_id (fk), summary, facts (jsonb), opinions (jsonb),
  assumptions (jsonb), sources (jsonb: [{source,url,title,key_facts,date,
  relevance,confidence}]), provider, created_at

scripts
  id, job_id (fk), topic_id (fk), status (script_status), target_duration_sec,
  tone, style, language, current_version, qa_score, created_at

script_versions
  id, script_id (fk), version, body_json (jsonb: {hook,intro,main,transitions,
  pattern_interrupts,cta,ending, full_text}), word_count, est_duration_sec,
  qa_result (jsonb), created_by (ai|revision|human), created_at

video_scenes
  id, script_id (fk), job_id (fk), scene_index, narration, visual_prompt,
  visual_type (image|ai_video|stock|upload), planned_duration_sec,
  actual_duration_sec, transition, caption_text
  idx(job_id, scene_index)

voiceovers
  id, job_id (fk), script_version_id (fk), provider, voice, language, speed,
  emotion, duration_sec, audio_key, timestamps_key, est_cost_usd, created_at

visual_assets
  id, job_id (fk), scene_id (fk), asset_type, source (asset_source), prompt,
  file_key, width, height, duration_sec, license, attribution,
  rights_verified (bool), provider, est_cost_usd, created_at

video_projects
  id, job_id (fk uniq), aspect_ratio, resolution, timeline_key, video_key,
  duration_sec, size_bytes, has_subtitles, music_track_id (fk null),
  thumbnail_id (fk null), status (rendering|ready|failed), ffprobe (jsonb),
  created_at

music_tracks
  id, job_id (fk), source (none|uploaded|licensed|generated), file_key,
  license, attribution, duck_level_pct, created_at

thumbnails
  id, job_id (fk), concept, text, composition, target_emotion, image_prompt,
  file_key, score, selected (bool), provider, est_cost_usd, created_at

youtube_uploads
  id, job_id (fk uniq), channel_id (fk), title, description, tags (text[]),
  hashtags (text[]), category_id, playlist_id, chapters (jsonb),
  title_options (jsonb: [{title,scores}]), privacy_status (privacy_status),
  scheduled_publish_at, youtube_video_id, youtube_url, status, published_at,
  quota_units_used, created_at

jobs
  id, public_id (uniq, e.g. job_2026_00124), channel_id (fk), mode
  (approval_mode), test_run (bool), status (job_status), current_stage (stage),
  progress_pct, topic_id (fk null), error_code, error_message,
  total_cost_usd, total_duration_sec, started_at, finished_at, created_at
  idx(channel_id, status), idx(status, created_at)

job_steps
  id, job_id (fk), stage (stage), status (job_step_status), attempt,
  max_attempts, input (jsonb), output (jsonb), error_code, error_message,
  retryable (bool), started_at, finished_at, duration_sec
  idx(job_id, stage), uniq(job_id, stage, attempt)

notifications
  id, job_id (fk null), channel_id (fk), event (notification_event),
  provider, recipient, template, body, status (notification_status),
  provider_message_id, error, created_at, delivered_at
  uniq(job_id, event)   # dedup

api_usage
  id, job_id (fk null), stage, provider, model, operation,
  input_tokens, output_tokens, units, seconds, est_cost_usd, created_at
  idx(job_id), idx(created_at)

system_logs
  id, job_id (fk null), level, stage, event, message, context (jsonb),
  created_at
  idx(job_id, created_at), idx(level, created_at)

scheduler_runs
  id, channel_id (fk), run_date (date), lock_key (uniq), jobs_created,
  status, created_at
  uniq(channel_id, run_date)
```

## Phase checklist

Each phase ends with: migrations applied, `pytest` green, `PROJECT_STATUS.md`
updated, git commit tagged `phase-N`, and a **working HTTP endpoint** demoing the
phase (the "endpoint after every phase" requirement).

### PHASE 1 — Architecture ✅ (this deliverable)
- [x] Inspect repo & toolchain
- [x] `ARCHITECTURE.md`, `DATA_FLOW.md`, `API_REQUIREMENTS.md`, `ENVIRONMENT.md`,
      `IMPLEMENTATION_PLAN.md`, `PROJECT_STATUS.md`
- [x] DB schema, folder structure, env design
- [x] git repo initialised, scaffold dirs
- **Endpoint:** n/a (docs). Repo boots to scaffold.

### PHASE 2 — Foundation
- [ ] `docker-compose.yml` (postgres, redis), `.env.example`
- [ ] `api/pyproject.toml`, dependency install, `imageio-ffmpeg` verified
- [ ] `core/config.py`, `core/security.py`, `core/logging.py`, `core/errors.py`
- [ ] `db/base.py`, all SQLAlchemy models, Alembic init + first migration
- [ ] `db/seed.py` (admin user + default channel + default settings)
- [ ] Auth: `POST /api/auth/login`, JWT deps, `GET /api/auth/me`
- [ ] StorageProvider: `local` + `stub` interface
- [ ] Channel + settings CRUD routes
- [ ] `pytest`: config load, migration, auth flow, channel CRUD
- **Endpoint:** `GET /api/health` (db + redis check), `GET /api/channels`

### PHASE 3 — AI pipeline
- [ ] `providers/base.py` + `registry.py` + stubs for AI/Research
- [ ] `AnthropicProvider` (with usage → cost)
- [ ] `services/topics.py` (generate N, score, dedupe via fingerprint)
- [ ] `services/research.py` (+ `tavily` adapter, `stub`)
- [ ] `services/script.py` (structured script + scenes)
- [ ] `services/script_qa.py` (+ auto-revision loop, max retries)
- [ ] routes: `POST /api/channels/{id}/topics:generate`, topic accept/reject,
      `GET /api/topics`, `GET /api/scripts/{id}`
- [ ] `pytest` with stub providers: deterministic topic/script/QA
- **Endpoint:** `POST /api/channels/{id}/topics:generate` → scored topics

### PHASE 4 — Media pipeline
- [ ] VoiceProvider: `stub` (synthetic wav + timings), `elevenlabs`, `openai`
- [ ] ImageProvider: `stub` (Pillow), `openai`; StockProvider: `pexels`, `stub`
- [ ] `services/visuals.py` (per-scene source routing, license capture)
- [ ] `services/subtitles.py` (SRT/VTT from timestamps)
- [ ] `services/timeline.py` (deterministic timeline.json, align to voice)
- [ ] `services/render.py` (FFmpeg: images/clips + voice + ducked music + subs
      + intro/outro; 16:9 / 9:16 / 1:1; 1080p)
- [ ] `ffprobe` validation
- [ ] `pytest`: render a 10s video from stubs, assert playable + duration
- **Endpoint:** `POST /api/jobs/{id}/stages/render:run` (test), returns mp4 key + `GET .../video` streams it

### PHASE 5 — YouTube ✅
- [x] Google OAuth: `GET /api/youtube/oauth/start`, `.../callback`, signed state, token encrypt/refresh
- [x] `services/metadata.py` (titles scored, description, tags, hashtags, chapters from scene timings)
- [x] YouTubeProvider `google`: resumable upload, thumbnail set, playlist, privacy, scheduled publish + `stub`
- [x] `services/thumbnail.py` (concepts → images → deterministic score → select)
- [x] quota tracking + guard (`api_usage` units, `YT_DAILY_QUOTA_UNITS`, `QUOTA_EXCEEDED`)
- [x] `services/publish.py` orchestration (thumbnail→metadata→upload job steps)
- [x] `pytest` (20 total): publish pipeline vs stub, metadata/thumbnail shape, OAuth state roundtrip, quota guard, status endpoint
- **Endpoint:** `GET /api/youtube/status`, `POST /api/jobs/{id}/publish:run`, `POST /api/jobs/{id}/stages/{thumbnail|metadata|upload}:run`, `GET /api/jobs/{id}/upload`

### PHASE 6 — WhatsApp ✅
- [x] NotifierProvider: `console`, `twilio`, `meta_cloud`, `stub` + `registry.get_notifier()`
- [x] 4 templates (job_started, video_ready, published, error) + `notify_events` preferences + `(job_id, event)` dedup
- [x] webhook: `POST /api/webhooks/twilio` (RequestValidator signature) + `GET/POST /api/webhooks/meta` → forward-only status on `notifications`
- [x] pipeline wiring: render→video_ready, upload→published, stage error→error (never fatal)
- [x] `pytest` (29 total): template render, preferences, dedup, no-recipient, webhook status update, meta verify, pipeline emits
- **Endpoint:** `POST /api/notifications/test`, `GET /api/notifications`

### PHASE 7 — Controller / orchestration ✅
- [x] `workflows/pipeline.py` — 16-stage order, stage handlers over pure services, resume-from-stage
- [x] `workflows/retry.py` — per-stage exponential backoff, retryable-codes only; `workflows/controller.py`
- [x] RQ wiring (`workers/queue|tasks|run.py`, `make worker`), `JOBS_ASYNC` toggle (inline by default)
- [x] APScheduler (`scheduler/scheduler.py`): per-channel cron, `scheduler_runs` unique row as dedup lock, `daily_video_limit` accounting
- [x] approval gate (`WAITING_APPROVAL` before UPLOAD) + `:approve|:reject|:retry|:cancel`
- [x] `services/final_qa.py` — 14 deterministic pre-upload checks
- [x] `pytest` (41 total): full AUTO pipeline → mp4 + upload, approval pause/resume, resume-after-draft, retryable recovery, non-retryable + `:retry`, scheduler dedup/limit
- **Endpoint:** `POST /api/jobs`, `POST /api/jobs/{id}:run|:approve|:reject|:retry|:cancel`, `POST /api/scheduler/run`

### PHASE 8 — Dashboard ✅
- [x] Vite + React + TS + Tailwind app, JWT auth, typed API client, sidebar layout
- [x] Overview, Automation, Topics, Scripts, Videos, YouTube, Notifications, Logs, Settings (AI/provider JSON panel), Setup Wizard (11-step live checklist), test-run toggle on job create
- [x] served as static build from FastAPI at `/` (`app/web.py`, SPA fallback); `make web`
- [x] `GET /api/overview`, `GET /api/logs`, `GET /api/usage`; `services/events` -> `system_logs`
- [x] `pytest` (45 total) + live browser walkthrough
- **Endpoint:** dashboard at `/`, `GET /api/overview` stats

### PHASE 9 — Testing
- [ ] unit + integration + pipeline + failure tests; coverage target ~70%
- [ ] `TEST` mode verified end to end; seed/fixtures; CI workflow
- **Endpoint:** `GET /api/health/deep` (all providers self-check)

### PHASE 10 — Production
- [ ] Dockerfiles (api, worker), compose prod profile, entrypoint runs migrations
- [ ] secret-manager notes, backup script (pg_dump + storage), retention job
- [ ] security review pass (checklist in ARCHITECTURE §8), rate limits on, log redaction verified
- [ ] deploy runbook in `docs/DEPLOY.md`
- **Endpoint:** everything, behind auth, on `PUBLIC_HOST`

## Risks / blockers

| Risk | Impact | Plan |
|---|---|---|
| Only Python 3.9.6 on this machine (no brew) | some libs prefer 3.11+ | Pin versions known-good on 3.9; recommend user install 3.11 via pyenv; CI on 3.11 |
| Postgres / Redis not running locally | can't run anything | `docker-compose up db redis` in Phase 2 (Docker is installed) |
| No system ffmpeg | render stage | use `imageio-ffmpeg` bundled binary (Phase 4) |
| Anthropic model name `claude-sonnet-4-6` from stale env | wrong model id | verify against current model list at Phase 3; make it a setting |
| YouTube OAuth app verification | limits real uploads | run in Google "Testing" mode with owner as test user; document verification path |
| WhatsApp template approval lead time | delayed notifications | start with Twilio sandbox / `console`; templates submitted early |
| Live API key committed in Downloads/env | credential exposure | user rotates key; never commit `.env`; `.gitignore` from Phase 2 |
| Video generation cost/latency | expensive per video | default visuals = stock + AI images, not AI video; cost guard + daily limit |
| LLM hallucinated facts | wrong content published | research stage + QA "unsupported claim" check + APPROVAL_REQUIRED default |

## Build-first order

1. Phase 2 foundation (nothing works without config/db/auth/storage).
2. Phase 3 AI pipeline against **stubs** → deterministic tests early.
3. Phase 4 render against stubs → prove the mp4 comes out.
4. Phases 5–6 external integrations.
5. Phase 7 ties it together (this is where "automation" becomes real).
6. Phase 8 dashboard.
7. Phases 9–10 harden + ship.
