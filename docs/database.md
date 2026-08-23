# Database

Two dialects behind one small chokepoint in `backend/app/db.py`. **SQLite is the default**
(offline, zero-infra — see ADR-001). **Postgres** is used when `DATABASE_URL` is a
`postgres://` / `postgresql://` DSN — the durable store for the Render deployment (§10).

## Why Postgres for the deployment

Render's web-service filesystem is ephemeral: a SQLite file resets on every redeploy and
after idle spin-down. Shared state that must survive that goes in managed Postgres. For a
single throwaway demo, ephemeral SQLite still works (re-seed each session) — but the tasks a
worker is processing must be durable, so the deployment uses Postgres.

## What persists

The full domain schema (unchanged across dialects): `candidate`, `kb_entity`, `job`,
`suggestion`, `role_profile`, `embedding_cache`, `opportunity`, `search_preferences`,
`application_batch`, `discovery_run`, `application_task`, and the V3.5 `worker` registry.

## The dialect chokepoint

Everything else in `db.py` is written once against a SQLite-shaped API (`?` params,
`row["col"]`, `cur.lastrowid`). Three functions absorb the differences:

- **`get_conn()`** — returns a connection with sqlite3 semantics on either driver. For
  Postgres it wraps psycopg3 (`_PGConn`) to rewrite `?`→`%s`, yield dict rows, and
  commit+close on `with` exit. (There are no literal `%` in the SQL, so the swap is safe.)
- **`_insert()`** — returns the new id. Postgres appends `RETURNING id`; SQLite uses
  `lastrowid`. The one place auto-increment ids are read.
- **schema + claim branches** — DDL is translated (`INTEGER PRIMARY KEY AUTOINCREMENT` →
  `SERIAL`, comments stripped, one statement per execute); the atomic claim uses
  `FOR UPDATE SKIP LOCKED` on Postgres vs `BEGIN IMMEDIATE` on SQLite. `INSERT OR REPLACE`
  was replaced with portable `ON CONFLICT … DO UPDATE`.

`psycopg[binary]` is imported **only** under a Postgres DSN, so SQLite installs/tests need it
never.

## Migrations / initialization

Schema is idempotent and created on startup via `init_db()` (`app.api` lifespan), and on
first `get_conn()` use in scripts. Every `CREATE` is `IF NOT EXISTS`, so re-running is safe;
Postgres always starts from the full schema, SQLite additionally runs `_migrate()` for columns
added to pre-existing files.

Point at a database and initialize it:

```bash
# SQLite (default)
DATABASE_URL=data/adaptive_resume.sqlite3 \
  python -c "import sys; sys.path.insert(0,'backend'); from app.db import init_db; init_db()"

# Postgres
DATABASE_URL='postgresql://user:pass@host:5432/dbname' \
  python -c "import sys; sys.path.insert(0,'backend'); from app.db import init_db; init_db()"
```

On Render, `init_db()` runs automatically at app startup, so a fresh managed Postgres is
provisioned into the full schema on first boot.

## Verifying the Postgres path

`tests/test_db_dialect.py` unit-tests the mechanical translation (placeholder rewrite, DDL
translation) everywhere. A full schema-create + atomic-claim conformance test runs against a
real Postgres when `TEST_DATABASE_URL` is set, and skips otherwise (the same pattern the
Playwright tests use for Chromium):

```bash
TEST_DATABASE_URL='postgresql://user:pass@host:5432/testdb' pytest tests/test_db_dialect.py
```

## Artifacts (§25)

Résumés/cover letters are generated on demand and not stored on the ephemeral web-service
disk: the tailored résumé PDF is rendered from the persisted `job.resume_json` when the worker
requests `GET /worker/tasks/{id}/resume.pdf` (reportlab, no LaTeX engine needed). The durable
source of truth is the row in Postgres, not a file.
