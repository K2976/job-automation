# Vercel deployment (frontend)

Deploys the React/Vite static frontend. Extends the base notes in [deployment.md](deployment.md).

## Deploy

Import the repo into Vercel. `vercel.json` builds `frontend/` with output `frontend/dist`.

## Environment variables (§23)

Only **public** build-time config belongs here:

| Variable | Notes |
| --- | --- |
| `VITE_API_BASE` | The Render API URL, e.g. `https://adaptive-resume-api.onrender.com`. |

`VITE_*` values are **inlined into the client bundle** and visible to anyone. Therefore:

> **Never** put `WORKER_AUTH_TOKEN`, `GEMINI_API_KEY`, `GROQ_API_KEY`, or `DATABASE_URL` in
> Vercel env vars. Those are server-only and live on Render.

`VITE_API_BASE` is baked in at `npm run build`, so changing the backend URL later means
**redeploying the frontend**.

## After deploy

Note the `*.vercel.app` URL and set it as `CORS_ORIGINS` on the Render API, then redeploy the
API (see [render-deployment.md](render-deployment.md)). The worker-status badge on the
Applications tab reads `GET /api/worker/status` (public, no token) to show Online/Offline.
