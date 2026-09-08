# PROJECT STATUS

_Last updated: 2026-09-07 · Current phase: **Phase 1 complete → Phase 2 next**_

## Legend
✅ done · 🔄 in progress · ⬜ not started · ⚠️ blocked

## Phase status

| Phase | Title | Status | Endpoint delivered |
|---|---|---|---|
| 1 | Architecture & planning | ✅ | — (docs) |
| 2 | Foundation (config, db, auth, storage) | ⬜ | `GET /api/health`, `GET /api/channels` |
| 3 | AI pipeline (topic, research, script, QA) | ⬜ | `POST /api/channels/{id}/topics:generate` |
| 4 | Media pipeline (voice, visuals, subs, render) | ⬜ | `POST /api/jobs/{id}/stages/render:run` |
| 5 | YouTube (OAuth, metadata, upload, thumbnail) | ⬜ | `GET /api/youtube/status` |
| 6 | WhatsApp notifications | ⬜ | `POST /api/notifications/test` |
| 7 | Controller / queue / scheduler | ⬜ | `POST /api/jobs`, `GET /api/jobs/{id}` |
| 8 | Admin dashboard | ⬜ | dashboard at `/` |
| 9 | Testing & test mode | ⬜ | `GET /api/health/deep` |
| 10 | Production / deploy / security | ⬜ | full system on `PUBLIC_HOST` |

## Phase 1 — completed

- Inspected working dir (empty), toolchain: Python 3.9.6 only, Node 24, Docker
  29, **no ffmpeg**, **no Homebrew**, git initialised here.
- Reviewed sibling projects (Ebay/Etsy AI agents) → confirmed Python/FastAPI +
  Anthropic + separate JS frontend as the house style.
- Reviewed `~/Downloads/env` → intended stack: Postgres, Redis, Anthropic
  (`claude-sonnet-4-6`), Twilio. **Contains a live Anthropic key — must be
  rotated; will never be committed.**
- Wrote: `ARCHITECTURE.md`, `DATA_FLOW.md`, `API_REQUIREMENTS.md`,
  `ENVIRONMENT.md`, `IMPLEMENTATION_PLAN.md`, this file.
- Decisions locked: FastAPI modular monolith · SQLAlchemy 2.0 + Alembic ·
  Postgres · Redis + RQ · APScheduler · FFmpeg via `imageio-ffmpeg` ·
  React/Vite/Tailwind dashboard · provider abstraction with a `stub` for every
  interface so the pipeline runs offline with zero API keys.
- Created scaffold directories under `api/`, `web/`, `storage/`, `docs/`.

## Open decisions needing user input

1. **Dashboard**: bundled React SPA (planned) vs. a separate Next.js app. Default: React SPA served by FastAPI.
2. **Voice/Image providers to actually fund**: ElevenLabs + OpenAI images assumed. Confirm or name alternatives.
3. **WhatsApp**: Twilio (env hints this) vs Meta Cloud API. Default: Twilio.
4. **Python 3.11 install** on this machine (recommended) — proceed on 3.9 otherwise.
5. Rotate the exposed Anthropic key and provide the new one via `.env` (not committed).

## Next actions (Phase 2)

See `IMPLEMENTATION_PLAN.md` → "PHASE 2 — Foundation" checklist.
