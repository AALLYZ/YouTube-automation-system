# Dashboard (web/)

React + Vite + TypeScript + Tailwind admin SPA for the YouTube Automation API.

## Develop

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api -> http://localhost:8090
```

Run the API separately (`cd ../api && make run`).

## Build

```bash
npm run build        # -> web/dist
```

FastAPI serves `web/dist` at `/` automatically when it exists
(`app/web.py`), with SPA fallback for client-side routes. Without a build the
API still runs and `/` returns a JSON pointer.

```bash
cd ../api && make web && make run   # build dashboard, then serve everything on :8090
```

## Pages

Overview · Automation (create/approve/retry/cancel jobs, scheduler tick) ·
Topics · Scripts · Videos · YouTube (OAuth connect) · Notifications (send test) ·
Logs (events + API usage) · Settings (channel + AI/provider config) · Setup Wizard.

Auth: JWT from `POST /api/auth/login`, stored in `localStorage`.
