# Deployment — frontend on Vercel, backend on Render

The app is a static React frontend + a FastAPI backend. They can run on one host (FastAPI
serves the built frontend) or split across two (Vercel + Render). This covers the split.

## ⚠️ Read first — three things that will bite you

1. **A public backend with live keys = anyone can spend your LLM quota.** The API has no
   auth (out of V1 scope). **CORS is not a security boundary** — it only restrains
   browsers, not `curl`. Mitigations: keep `LLM_PROVIDER=mock` as the deployed default and
   flip to `groq`/`gemini` only while actively demoing, **and** set provider-side spend
   caps. `render.yaml` defaults to `mock` for exactly this reason.
2. **`VITE_API_BASE` is build-time.** Vite inlines it at `npm run build`. Changing the
   backend URL later means **rebuilding/redeploying the frontend**.
3. **SQLite on Render free tier is ephemeral.** It resets on every redeploy and after the
   ~15-min idle spin-down. Fine for a single demo session (re-seed on load). For
   persistence, attach a paid disk (below).

## Deploy order (it's circular — follow this sequence)

```
1. Deploy backend to Render        → get https://<api>.onrender.com
2. Set VITE_API_BASE=<api-url> in Vercel, deploy frontend → get https://<app>.vercel.app
3. Set CORS_ORIGINS=<app-url> on Render, redeploy backend
```

### 1 · Backend on Render
- New **Blueprint** from this repo — Render reads `render.yaml` (web service, Python,
  `uvicorn app.api:app --app-dir backend --host 0.0.0.0 --port $PORT`).
- It deploys with `LLM_PROVIDER=mock` (zero cost). To use a real provider, set in the
  dashboard: `LLM_PROVIDER=groq` (+ `GROQ_API_KEY`) or `gemini` (+ `GEMINI_API_KEY`,
  `GEMINI_AUTH=query`). Secrets are `sync:false` — set them in the dashboard, never in the
  repo.
- Cold start on free tier is ~50s after idle; the UI degrades gracefully while waiting.

### 2 · Frontend on Vercel
- Import the repo. Vercel reads `vercel.json` (builds `frontend/`, output `frontend/dist`).
- Set env var **`VITE_API_BASE`** = your Render URL (e.g. `https://adaptive-resume-api.onrender.com`).
- Deploy → note the `*.vercel.app` URL.

### 3 · Close the CORS loop
- On Render set `CORS_ORIGINS=https://<app>.vercel.app` (comma-separate multiple), redeploy.
- Verify: open the Vercel app, seed a candidate, analyze a JD — network calls should hit
  the Render URL with no CORS errors.

## Persistent data (optional, paid)
Add to `render.yaml` and set `DATABASE_URL` to the mount path:
```yaml
    disk:
      name: data
      mountPath: /var/data
      sizeGB: 1
    envVars:
      - key: DATABASE_URL
        value: /var/data/adaptive_resume.sqlite3
```
This requires a paid Render instance. Larger scale → Postgres (swap `db.py`; see
[ADR-001](decisions/ADR-001-sqlite-over-postgres.md)) — not needed for V1.

## Single-host alternative (simplest)
Skip Vercel entirely: `cd frontend && npm run build`, then run the backend — FastAPI serves
`frontend/dist` at `/`. One origin, no CORS, no `VITE_API_BASE`. Good for a self-hosted box.
