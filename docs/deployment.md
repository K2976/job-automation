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
   ~15-min idle spin-down. Fine for a single demo session (re-seed on load). For durable
   state (V3.5), the deployment uses an **external Neon Postgres** via `DATABASE_URL` —
   `db.py` is already dual-dialect, so no code swap. See
   [manual-cloud-setup.md](manual-cloud-setup.md) and [database.md](database.md). (The paid
   Render-disk option below still works if you prefer to stay on SQLite.)

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

## Professional PDF (LaTeX) — optional
The default free deploy has **no** LaTeX engine, so `export.latex.pdf` returns a friendly
503 and the reportlab **PDF (standard)** stays the working default — nothing breaks (see
[resume-template-system.md](resume-template-system.md)).

To enable the professional PDF in production, install **tectonic** (single binary, no
apt) in the build and put it on `PATH`, e.g. prepend to the Render `buildCommand`:
```bash
curl -fsSL https://github.com/tectonic-typesetting/tectonic/releases/latest/download/tectonic-x86_64-unknown-linux-gnu.tar.gz \
  | tar xz -C /usr/local/bin && pip install -r requirements.txt
```
Tectonic fetches LaTeX packages on first run, so the first compile after a cold start is
slower; the free tier's ephemeral disk means that cost recurs on each spin-up. For a
snappier/offline option use a Docker runtime with a slim TeX image. Not required for V1 —
reportlab is the reliable fallback.

## Single-host alternative (simplest)
Skip Vercel entirely: `cd frontend && npm run build`, then run the backend — FastAPI serves
`frontend/dist` at `/`. One origin, no CORS, no `VITE_API_BASE`. Good for a self-hosted box.

## V3 browser worker (Playwright)
Application automation (V3) runs a real Chromium via Playwright. **Do not run it in the API
web service**, and do not assume a free-tier web service can host it:

- `playwright` is in `requirements.txt`, but the browser binaries (~150MB) are **not**
  installed by the API build — importing the app never needs them. Install them only where
  the worker runs: `playwright install chromium` (plus `playwright install-deps` on Linux for
  the shared libraries Chromium needs).
- A browser process is memory/CPU-heavy and long-lived relative to an HTTP request. Render's
  **free web tier is not suitable** (limited memory, ephemeral disk, aggressive idle
  suspension that can kill a mid-run task). Run the worker as a **dedicated service** — a
  Render Background Worker / paid instance with the browsers installed, or locally.
- The worker is decoupled by design: the runner is pure over the `BrowserPage` protocol, and
  the queue's page factory is injectable. Locally, discovery/prepare/apply all run in one
  process; in production the browser worker should be split out (see
  [application-automation.md](application-automation.md), [browser-agent.md](browser-agent.md)).
- Tasks run **serially** (one Chromium context at a time) in isolated contexts; no cookies or
  credentials are persisted.
- **Security:** the worker opens `opportunity.application_url` in a real browser, so it is an
  outbound-navigation (SSRF-adjacent) surface. Like the rest of the app it has no built-in
  auth, so the browser worker and its control API **must not be exposed unauthenticated** —
  run it on a private network / behind an auth proxy. It should navigate only URLs sourced
  from discovered opportunities, never arbitrary user input, and its debugging port must never
  be public (§46).
