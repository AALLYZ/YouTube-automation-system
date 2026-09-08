# API / SERVICE REQUIREMENTS

Legend: **Required** = pipeline can't reach production without it ·
**Optional** = has a working `stub`/free alternative · **Free tier** available?

## Core infrastructure

| Service | Purpose | Required | Notes / limits |
|---|---|---|---|
| PostgreSQL 14+ | State, metadata | **Required** | Local Docker or managed (Neon/Supabase/RDS) |
| Redis 6+ | RQ queue, scheduler locks | **Required** | Local Docker or managed (Upstash) |
| FFmpeg | Video render | **Required** | Auto-provided by `imageio-ffmpeg` pip pkg (bundled binary); no system install |

## AI / LLM

| Provider | Used for | Required | Pricing model | Limits |
|---|---|---|---|---|
| Anthropic Claude | topics, research summary, script, QA, metadata, thumbnail concepts | **Required** (default) | per-token (input/output) | tier rate limits (RPM/TPM); handle 429 |
| OpenAI | alt LLM + TTS + images | Optional | per-token / per-char / per-image | — |
| Google Gemini | alt LLM | Optional | per-token | — |

Default model: from `MODEL` env (`claude-sonnet-4-6` in the sample env — verify
against current Anthropic model list at build time; `api/app/core/pricing.py`
holds the price table).

## Research

| Provider | Required | Free tier | Notes |
|---|---|---|---|
| Tavily | Optional | yes (1k/mo) | LLM-oriented search, clean results — recommended |
| Brave Search API | Optional | yes (2k/mo) | — |
| SerpAPI | Optional | limited | expensive at scale |
| `stub` | — | — | returns empty sources; script proceeds "no-research" |

## Voice-over

| Provider | Required | Pricing | Notes |
|---|---|---|---|
| ElevenLabs | Optional (recommended) | per-character, monthly quota | best quality; provides word timestamps |
| OpenAI TTS | Optional | per-character | 6 voices, no word timestamps (segment only) |
| Local (pyttsx3 / say) | Optional | free | robotic; offline dev |
| `stub` | — | free | synthetic silence sized to word count + fake timestamps; keeps pipeline runnable |

## Visuals

| Provider | Kind | Required | Pricing |
|---|---|---|---|
| OpenAI Images (gpt-image-1) | AI image | Optional | per-image by size |
| Stability AI | AI image | Optional | per-image credits |
| Replicate | AI image / AI video (e.g. SDXL, video models) | Optional | per-second GPU |
| Pexels API | stock photo/video | Optional | **free**, attribution, generous limits |
| Pixabay API | stock photo/video | Optional | **free** |
| `stub` | — | — | Pillow-rendered caption card per scene (offline) |

## Video clip generation (optional, expensive)

| Replicate video models | Optional | per-second GPU, slow | only when `visual_type = "ai_video"` |

## YouTube

| Item | Detail |
|---|---|
| API | YouTube Data API v3 (`youtube.upload`, `youtube.readonly`, `youtube.force-ssl`) |
| Auth | OAuth 2.0 (Web app client) — consent screen, redirect URI `${PUBLIC_HOST}/api/youtube/oauth/callback` |
| Quota | 10,000 units/day default. **Video insert ≈ 1,600 units** → ~6 uploads/day before requesting more. thumbnails.set ≈ 50. Track in `api_usage`. |
| Verification | App may need Google OAuth verification for many users; fine for single-owner use in "Testing" mode (add self as test user) |
| Scheduled publish | upload as `private` + set `status.publishAt` (RFC3339) |
| Required | **Required** for the "upload" half; pipeline runs fully without it in TEST mode |

## WhatsApp notifications

| Option | Required | Notes |
|---|---|---|
| Twilio API for WhatsApp | Optional (env has `TWILIO_*`) | Sandbox for dev (join code); production needs a WhatsApp sender + approved templates. Webhook for delivery status. |
| Meta WhatsApp Cloud API | Optional | free tier of conversations; needs Business verification, phone number, template approval |
| `console` / `stub` | — | logs the message; default for dev |

Notifications must **never block** the pipeline — failures are logged only.

## Storage

| Option | Required | Notes |
|---|---|---|
| Local filesystem (`storage/`) | default | fine for single-node dev/prod |
| S3 / R2 / Spaces | Optional | set `STORAGE_PROVIDER=s3` + bucket creds for multi-node or durability |

## Summary: minimum to run each mode

- **Offline dev / tests**: Postgres + Redis only. All providers = `stub`. Full pipeline runs, produces a real (if ugly) mp4.
- **Realistic TEST run**: + Anthropic + (ElevenLabs or OpenAI TTS) + (Pexels or OpenAI images). No YouTube/WhatsApp.
- **Production**: + Google OAuth (YouTube) + (Twilio or Meta) WhatsApp + optionally S3.
