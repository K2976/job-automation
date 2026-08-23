# Render deployment (API + Postgres)

Deploys the FastAPI backend and its managed Postgres. The browser worker is **not** here
(§40) — it runs on the MacBook. Extends the base split-deploy notes in [deployment.md](deployment.md).

## Blueprint

`render.yaml` declares a free web service **and** a managed Postgres, and wires
`DATABASE_URL` from the database into the service. Create a **Blueprint** from the repo and
Render reads it.

Entry point (already set): `uvicorn app.api:app --app-dir backend --host 0.0.0.0 --port $PORT`
— binds `0.0.0.0:$PORT`, never localhost (§21). Health check: `/api/health`.

## Environment variables (§22)

Set on the Render service. **Never** print or commit actual values.

| Variable | Notes |
| --- | --- |
| `DATABASE_URL` | From the managed Postgres (blueprint wires it). Omit ⇒ ephemeral SQLite. |
| `INLINE_APPLICATIONS` | **`false`** — the API must only enqueue, never launch Chromium (§5). |
| `WORKER_AUTH_TOKEN` | Shared worker token (`sync:false`). Same value in the MacBook `.env.worker`. |
| `CORS_ORIGINS` | Your Vercel URL (§24). Not a security boundary. |
| `LLM_PROVIDER` | `mock` (default, free) \| `gemini` \| `groq`. |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | Only for the chosen provider (`sync:false`). |
| `GEMINI_AUTH` | `query` (default) \| `bearer`. |
| `OPPORTUNITY_SOURCES` | `fixtures` (default, offline) \| add `greenhouse,lever`. |

## Postgres

Free-tier Render Postgres is time-limited (~30 days) — fine for a demo, upgrade for anything
long-lived. Schema is created automatically at app startup (`init_db()`); no manual migration
step. See [database.md](database.md) to initialize or verify a database manually.

## Free-tier note

Cold start after idle is ~50s; the UI degrades gracefully while waiting. Keep
`LLM_PROVIDER=mock` unless actively demoing a real provider, and set provider-side spend caps
— a public API with live keys can be called by anyone (CORS doesn't stop `curl`).
