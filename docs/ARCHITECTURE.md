# ARCHITECTURE

## 1. Summary

A **modular monolith** (FastAPI) with **background workers** (RQ + Redis) and a
**React admin dashboard**. One deployable backend process for the API, one or
more worker processes for long-running jobs (script gen, voice, visuals, render,
upload), and an in-process scheduler for automation.

No microservices. Every external capability (LLM, voice, images, video, stock
media, research, storage, YouTube, notifications) sits behind a **provider
interface** so it can be swapped via environment variables without touching
workflow code.

## 2. Technology decisions

| Concern            | Choice                                   | Why |
|--------------------|------------------------------------------|-----|
| Language           | Python 3.9+ (3.11+ recommended)          | Matches user's other projects (Ebay/Etsy agents) |
| API framework      | FastAPI + Uvicorn                        | Async, typed, OpenAPI, matches Etsy backend |
| ORM / migrations   | SQLAlchemy 2.0 + Alembic                 | Mature, explicit schema/versioning |
| Database           | PostgreSQL 14+                           | Relational schema, JSONB for flexible metadata |
| Queue / workers    | Redis + RQ                               | Simplest reliable Python queue; exponential backoff supported |
| Scheduler          | APScheduler (in the API process)         | Cron-like automation, DB-backed job store, dedup via locks |
| Video rendering    | FFmpeg via `imageio-ffmpeg` (bundled binary) | No system install needed; deterministic CLI pipeline |
| Config             | pydantic-settings (`.env`)               | Typed, validated env |
| Secrets at rest    | Fernet (`cryptography`) with `APP_SECRET_KEY` | Encrypt OAuth tokens / provider keys stored in DB |
| Auth               | JWT bearer, single seeded admin (argon2 hash) | Small surface; multi-user later |
| Frontend           | React + Vite + TypeScript + Tailwind     | SPA served as static build by FastAPI in prod; matches Etsy split |
| Tests              | pytest + httpx + pytest-asyncio          | Matches user's other projects |

## 3. Process model

```
                 ┌───────────────────────────────┐
                 │  FastAPI process (api/)        │
   Browser ────▶ │  - REST API + OpenAPI         │
   (dashboard)   │  - Auth                       │
                 │  - APScheduler (automation)   │
                 │  - enqueues jobs ─────────────┼──┐
                 └───────────────────────────────┘  │
                                                    ▼
                       ┌──────────────┐      ┌──────────────┐
                       │  Redis       │◀────▶│  RQ worker(s) │
                       │  (queue)     │      │  run pipeline │
                       └──────────────┘      │  stages       │
                                             └──────┬───────┘
                 ┌───────────────────────────────┐  │
                 │  PostgreSQL  (state, metadata)│◀─┤
                 └───────────────────────────────┘  │
                 ┌───────────────────────────────┐  │
                 │  Storage (local dir or S3)    │◀─┘
                 │  scripts/voice/visuals/video  │
                 └───────────────────────────────┘
```

## 4. Orchestration model

The **`AutomationController`** (`api/app/workflows/controller.py`) owns the
pipeline. It does not call providers directly — it calls **stage services**,
each of which uses a **provider interface**.

Pipeline stages (each = one `job_step`, each independently retryable):

```
TOPIC → RESEARCH → SCRIPT → SCRIPT_QA → VOICE → VISUALS → SUBTITLES
      → TIMELINE → RENDER → THUMBNAIL → METADATA → FINAL_QA
      → APPROVAL_GATE → UPLOAD → NOTIFY → COMPLETE
```

Each stage:
1. Loads job + previous stage output from DB.
2. Runs, writing artifacts to storage and metadata rows to DB.
3. Records `api_usage` (provider, model, tokens, cost, duration).
4. Advances `job.current_stage`, or fails the step with a structured error.
5. On failure: retry with exponential backoff up to `max_retries`, else mark
   `job.status = FAILED` and send an error notification.

`APPROVAL_GATE` sets `job.status = WAITING_APPROVAL` and stops the worker. A
dashboard approve/reject action re-enqueues from `UPLOAD` (or cancels).

## 5. Execution modes

| Mode                | Behaviour |
|---------------------|-----------|
| `AUTO`              | Full pipeline, publishes automatically |
| `APPROVAL_REQUIRED` | Runs through `FINAL_QA`, waits at `APPROVAL_GATE` |
| `MANUAL`            | Only runs stages triggered explicitly from the dashboard |
| `TEST` (flag)       | Any mode, but `UPLOAD` and `NOTIFY(publish)` are skipped/mocked; stub providers allowed so the whole pipeline runs with **zero API keys** |

## 6. Provider abstraction

Interfaces in `api/app/providers/base.py`:

```
AIProvider          complete(messages, model, temperature, ...) -> {text, usage, cost}
ResearchProvider    search(query, depth, max_sources) -> [Source]
VoiceProvider       synthesize(text, voice, speed, ...) -> {audio_path, duration, timestamps, cost}
ImageProvider       generate(prompt, style, aspect, ...) -> {path, cost, license}
VideoClipProvider   generate(prompt, duration, ...) -> {path, cost, license}
StockMediaProvider  search(query, kind) -> [{path, license, attribution}]
StorageProvider     put(local, key) -> uri ; get(key) -> local ; url(key)
YouTubeProvider     upload(video, metadata, thumbnail, privacy, publish_at) -> {video_id, url}
NotifierProvider    send(recipient, template, vars) -> {message_id, status}
```

Selection via env: `AI_PROVIDER=anthropic`, `VOICE_PROVIDER=elevenlabs`,
`IMAGE_PROVIDER=stub`, etc. A `stub` implementation exists for every interface
so the system is runnable and testable offline.

Planned concrete adapters:

- AI: `anthropic` (default), `openai`, `gemini`, `stub`
- Research: `tavily`, `brave`, `serpapi`, `stub`
- Voice: `elevenlabs`, `openai`, `local` (pyttsx3), `stub` (synthetic silence + timing)
- Image: `openai`, `stability`, `replicate`, `stub` (Pillow text card)
- Video clip: `replicate`, `stub`
- Stock: `pexels`, `pixabay`, `stub`
- Storage: `local` (default), `s3`
- YouTube: `google` (official Data API v3), `stub`
- Notifier: `twilio` (WhatsApp), `meta_cloud`, `console`, `stub`

## 7. Failure points & mitigations

| Failure point | Mitigation |
|---|---|
| LLM rate limit / 5xx | RQ retry, exponential backoff, provider fallback list |
| LLM invalid JSON | Strict schema parse + one self-repair retry, then fail step |
| Voice provider timeout | Per-call timeout, retry, fallback to `local`/`stub` in TEST |
| FFmpeg render error | Validate timeline + asset existence pre-render; capture stderr into step error; retry once |
| Missing asset file | Pre-flight check each stage; fail fast with `MISSING_ASSET` |
| YouTube quota (10k units/day, upload ≈ 1600) | Track units in `api_usage`; refuse upload when projected over quota; backoff to next day |
| YouTube OAuth token expired | Auto-refresh; if refresh fails → `AUTH_ERROR`, notify, pause automation |
| WhatsApp 24h window / template rejection | Use approved templates only; on failure log + continue (never block publish) |
| Worker crash mid-stage | Stages are idempotent-ish; job resumable from `current_stage`; RQ job TTL + heartbeat |
| Duplicate scheduled jobs | Scheduler acquires a Postgres advisory lock per channel+date |
| Disk fills with media | Retention job prunes artifacts of `COMPLETED` jobs older than N days (configurable) |
| Secret leakage in logs | Central log filter redacts known secret patterns; provider errors sanitised |

## 8. Security

- All provider calls server-side only. No keys in frontend bundle.
- Provider keys and YouTube OAuth tokens encrypted (Fernet) in DB; `.env` holds only `APP_SECRET_KEY` + bootstrap keys.
- JWT auth on every non-public route; admin seeded from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
- Webhook endpoints (WhatsApp status) verify signature / token.
- Rate limiting (slowapi) on auth + job-creation routes.
- Input validation via Pydantic on every route.
- File handling: generated keys only, no user-controlled paths; storage root jail.
- CORS locked to dashboard origin.

## 9. Copyright / licensing

- No scraping of copyrighted media. Stock only via APIs that grant a license (Pexels/Pixabay) with attribution stored per asset.
- Every `visual_asset` / `music_track` row stores `source`, `license`, `attribution`, `rights_verified` (bool). Render refuses assets with `rights_verified = false` unless `allow_unverified_media = true` in channel settings.
- Music: default "none"; generated or user-uploaded or explicitly-licensed only.
- Thumbnails/scripts: QA stage flags potential trademarked names / defamation / medical-legal-financial claims for human review.

## 10. What runs sync vs async

| Sync (API request) | Async (RQ worker) |
|---|---|
| Auth, CRUD, settings, dashboard reads | Topic generation batch |
| Enqueue job, cancel job, approve/reject | Research, script, script QA |
| Topic accept/reject | Voice synthesis |
| Serve logs / status | Image/video generation, stock fetch |
| | Subtitle generation, timeline build |
| | FFmpeg render |
| | Thumbnail generation, metadata generation |
| | Final QA, YouTube upload, notifications |
