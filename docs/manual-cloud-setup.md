# Manual cloud setup

Actions that need your credentials/console — they can't be done from the repo. No secret ever
goes in Git, `.env.example`, or these docs. Production DB is **Neon** (project `job-automation`);
Render runs only the API (it does **not** provision a database — see `render.yaml`).

```
Vercel  →  Render FastAPI  →  Neon PostgreSQL
                              (project: job-automation)
```

## 1 · Neon → get the connection string

1. Neon Console → project **`job-automation`** → **Connection Details**.
2. Copy the **Pooled connection** string (host contains `-pooler`). It looks like:
   `postgresql://<user>:<password>@<ep>-pooler.<region>.aws.neon.tech/<db>?sslmode=require`
   Keep `?sslmode=require` — Neon requires TLS.
3. Do not paste it into chat, commits, or example files.

## 2 · Initialize the schema on Neon

The schema is created automatically on first API boot (`init_db()` in the app lifespan), so
deploying the Render service against `DATABASE_URL` is enough. To initialize/verify manually
from your machine (run in **your** terminal so the secret stays local):

```bash
export DATABASE_URL='<neon pooled connection string>'
python -c "import sys; sys.path.insert(0,'backend'); from app.db import init_db; init_db(); print('schema ready')"
```

## 3 · Verify the Postgres path against Neon (conformance test)

Run the repo's gated conformance test against Neon — it creates the schema and proves the
atomic single-claim under Postgres. Run it in your terminal (the DSN stays local; the test
prints only pass/fail, never the connection string):

```bash
export TEST_DATABASE_URL='<neon pooled connection string>'
pytest tests/test_db_dialect.py -q
```

Expected: the mechanical dialect tests pass **and** `test_postgres_schema_and_atomic_claim`
now runs (no longer skipped) and passes.

## 4 · Render → supply DATABASE_URL and the worker token

Render Dashboard → the `adaptive-resume-api` service → **Environment**:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | the Neon pooled string from step 1 |
| `WORKER_AUTH_TOKEN` | `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `INLINE_APPLICATIONS` | `false` (already in `render.yaml`) |
| `CORS_ORIGINS` | your Vercel URL |

(`render.yaml` marks `DATABASE_URL`, `WORKER_AUTH_TOKEN`, `CORS_ORIGINS` as `sync:false`, so
Render prompts for them and never reads them from the repo.)

## 5 · MacBook worker → same token, never the DB

`cp .env.worker.example .env.worker` and set `API_BASE_URL` (the Render URL) and the **same**
`WORKER_AUTH_TOKEN`. The worker needs **no** `DATABASE_URL` and **no** LLM keys — all state
lives behind the API, and semantic answers are generated server-side (§28).

## 6 · Docker Desktop (for the browser worker)

The worker runs in Docker on the MacBook. Start **Docker Desktop** and wait for
“Engine running”, then:

```bash
./scripts/test-browser-worker.sh     # build image + run V3 browser tests in-container
docker compose up browser-worker     # start the worker for a demo
```

## What is NOT automated here

- Retrieving the Neon connection string (needs the Neon Console or a connected Neon MCP).
- Creating the Render service / Vercel project (done from their dashboards — see
  [render-deployment.md](render-deployment.md), [vercel-deployment.md](vercel-deployment.md)).
- Nothing writes your Neon password anywhere in the repo.
