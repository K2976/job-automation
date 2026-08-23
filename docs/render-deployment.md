# Render deployment (API only; Postgres is Neon)

Deploys the FastAPI backend. The database is an **external** Neon Postgres (project
`job-automation`) — Render does **not** provision it. The browser worker is **not** here
(§40) — it runs on the MacBook. Extends [deployment.md](deployment.md); DB setup is in
[manual-cloud-setup.md](manual-cloud-setup.md).

## Blueprint

`render.yaml` declares a free web service (no `databases:` block). `DATABASE_URL` is
`sync:false` — you paste the Neon pooled connection string into the dashboard. Create a
**Blueprint** from the repo and Render reads it.

Entry point (already set): `uvicorn app.api:app --app-dir backend --host 0.0.0.0 --port $PORT`
— binds `0.0.0.0:$PORT`, never localhost (§21). Health check: `/api/health`.

## Environment variables (§22)

Set on the Render service. **Never** print or commit actual values.

| Variable | Notes |
| --- | --- |
| `DATABASE_URL` | The Neon pooled connection string (external, `sync:false`). Omit ⇒ ephemeral SQLite. |
| `INLINE_APPLICATIONS` | **`false`** — the API must only enqueue, never launch Chromium (§5). |
| `WORKER_AUTH_TOKEN` | Shared worker token (`sync:false`). Same value in the MacBook `.env.worker`. |
| `CORS_ORIGINS` | Your Vercel URL (§24). Not a security boundary. |
| `LLM_PROVIDER` | `mock` (default, free) \| `gemini` \| `groq`. |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | Only for the chosen provider (`sync:false`). |
| `GEMINI_AUTH` | `query` (default) \| `bearer`. |
| `OPPORTUNITY_SOURCES` | `fixtures` (default, offline) \| add `greenhouse,lever`. |

## Postgres (Neon, external)

The database is Neon (project `job-automation`), supplied via `DATABASE_URL` — Render does not
create it. Schema is created automatically at app startup (`init_db()`); no manual migration
step. Getting the Neon connection string and verifying it is in
[manual-cloud-setup.md](manual-cloud-setup.md); the dialect details are in
[database.md](database.md).

## Free-tier note

Cold start after idle is ~50s; the UI degrades gracefully while waiting. Keep
`LLM_PROVIDER=mock` unless actively demoing a real provider, and set provider-side spend caps
— a public API with live keys can be called by anyone (CORS doesn't stop `curl`).
