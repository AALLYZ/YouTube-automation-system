# DATA FLOW

## End-to-end pipeline

```
[Scheduler tick]  or  [Dashboard: "Create video"]
        │
        ▼
createJob(channel_id, mode, test_run)  ──▶  jobs row (QUEUED)
        │  enqueue RQ: run_pipeline(job_id)
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE: TOPIC                                                     │
│  in : channel config, used topics, avoid list, trends(opt)      │
│  AIProvider.complete → N candidates → score → pick best (or use  │
│  a pre-approved topic from the queue)                            │
│  out: topics rows, job.topic_id                                  │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: RESEARCH (optional per settings)                          │
│  in : topic                                                      │
│  ResearchProvider.search → sources → AIProvider summarise        │
│  out: research row {sources[], facts[], opinions[], assumptions} │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: SCRIPT                                                    │
│  in : topic, research, duration, tone, style, language          │
│  AIProvider.complete → structured script + scene list           │
│  out: scripts row (v1), video_scenes rows                       │
│       {scene, narration, visual_prompt, visual_type, duration}  │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: SCRIPT_QA                                                 │
│  checks: length, grammar, repetition, unsupported claims, hook, │
│          pacing, CTA, prohibited content, copyright             │
│  → {passed, score, issues[], recommendations[]}                 │
│  if !passed and retries<max → AIProvider revise → new script_ver│
│  out: script_versions rows, scripts.status = APPROVED|FAILED    │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: VOICE                                                     │
│  in : final script text (per scene or full)                     │
│  VoiceProvider.synthesize → wav + word/segment timestamps       │
│  out: voiceovers row {provider, voice, duration, path, cost},   │
│       per-scene audio offsets                                   │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: VISUALS                                                   │
│  for each scene: pick source (ai_image | ai_video | stock |     │
│  uploaded) → generate/fetch → store                             │
│  out: visual_assets rows {scene_id, type, source, prompt, path, │
│       license, attribution, rights_verified, cost}              │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: SUBTITLES                                                 │
│  from voice timestamps (or forced-align) → SRT + VTT            │
│  out: storage subtitles/<job>.srt/.vtt ; scenes get caption text│
├─────────────────────────────────────────────────────────────────┤
│ STAGE: TIMELINE                                                  │
│  merge scene durations (align to voice), transitions, music bed,│
│  overlays, aspect ratio → timeline.json (deterministic)         │
│  out: video_projects row {timeline_json, aspect, resolution}    │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: RENDER                                                    │
│  FFmpeg: assemble clips/images + voice + ducked music + subs +  │
│  intro/outro/branding → final_video.mp4                         │
│  out: video_projects {video_path, duration, size, status=READY} │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: THUMBNAIL                                                 │
│  AIProvider → M concepts → ImageProvider render → score → pick  │
│  out: thumbnails rows, video_projects.thumbnail_id              │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: METADATA                                                  │
│  AIProvider → title options(scored) + description + tags +      │
│  hashtags + category + chapters + playlist                      │
│  out: youtube_uploads row (draft) with metadata                 │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: FINAL_QA                                                  │
│  checks: video duration vs target, audio present, subs present, │
│  thumbnail present, metadata complete, no prohibited terms,     │
│  aspect/resolution correct, file playable (ffprobe)             │
│  → {passed, score, issues[]}                                    │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: APPROVAL_GATE (if mode = APPROVAL_REQUIRED)               │
│  job.status = WAITING_APPROVAL → NOTIFY "video ready"           │
│  worker exits. Dashboard approve → re-enqueue at UPLOAD.        │
│  Reject → job.status = CANCELLED (+ optional edit loop)         │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: UPLOAD  (skipped if test_run)                             │
│  YouTubeProvider.upload(mp4, metadata, thumbnail, privacy,      │
│  publish_at) → video_id, url ; set thumbnail ; add to playlist  │
│  out: youtube_uploads {video_id, url, status, published_at}     │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: NOTIFY                                                    │
│  NotifierProvider.send("published", {title, url})               │
│  out: notifications row                                         │
├─────────────────────────────────────────────────────────────────┤
│ STAGE: COMPLETE                                                  │
│  job.status = COMPLETED, totals rolled up (cost, duration)      │
└─────────────────────────────────────────────────────────────────┘
```

## State transitions (job.status)

```
QUEUED ──▶ RUNNING ──▶ WAITING_APPROVAL ──▶ RUNNING ──▶ COMPLETED
   │           │                                │
   │           ├────────▶ FAILED  (retries exhausted)
   └───────────┴────────▶ CANCELLED (user / reject)
```

## Artifact locations (StorageProvider keys)

```
scripts/<job_id>/script_v<n>.json
voiceovers/<job_id>/voiceover.wav
voiceovers/<job_id>/timestamps.json
visuals/<job_id>/scene_<i>.<ext>
subtitles/<job_id>/captions.srt | .vtt
music/<job_id>/bed.<ext>
videos/<job_id>/timeline.json
videos/<job_id>/final_video.mp4
thumbnails/<job_id>/thumb_<i>.png
```

DB stores **only** metadata + storage keys, never file bytes.

## Cost accounting

Every provider call writes one `api_usage` row:
`{job_id, stage, provider, model, input_tokens, output_tokens, units, seconds, est_cost_usd}`.
`GET /jobs/{id}/cost` sums rows grouped by stage → per-video cost breakdown.
Pricing comes from `api/app/core/pricing.py` (editable table), not magic numbers.

## Notification triggers (deduped, respect preferences)

| Event            | When                                   |
|------------------|----------------------------------------|
| `job_started`    | job enters RUNNING (first stage)       |
| `video_ready`    | APPROVAL_GATE reached                  |
| `published`      | UPLOAD succeeds                        |
| `error`          | a step exhausts retries → job FAILED   |

Dedup: one notification per (job_id, event); preferences in `channel_settings.notify_events`.
