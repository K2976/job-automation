"""Postgres dual-dialect layer (§10, ADR-001). Two levels: the mechanical translation
(placeholder rewrite, DDL translation) runs everywhere; a full conformance run — schema
create + the atomic single-claim under real concurrency — runs only when TEST_DATABASE_URL
points at a live Postgres (mirrors how the Playwright tests skip without Chromium). SQLite
stays the default and is covered by the rest of the suite."""
from __future__ import annotations

import os

import pytest

from app import db


# ------------------------------------------------- mechanical (always runs) #
def test_is_pg_detects_schemes():
    from app.config import settings
    orig = settings.database_url
    try:
        for url, expect in [
            ("data/x.sqlite3", False),
            ("postgres://u:p@h/db", True),
            ("postgresql://u:p@h/db", True),
            ("postgresql+psycopg://u:p@h/db", True),
        ]:
            settings.database_url = url
            assert db._is_pg() is expect, url
    finally:
        settings.database_url = orig


def test_pgconn_rewrites_placeholders():
    calls = []

    class _Fake:
        def execute(self, sql, params=()):
            calls.append(sql)
        def cursor(self):
            raise AssertionError("not needed")

    conn = db._PGConn(_Fake())
    conn.execute("INSERT INTO t(a,b) VALUES (?,?)", (1, 2))
    assert calls == ["INSERT INTO t(a,b) VALUES (%s,%s)"]


def test_pg_ddl_translation():
    stmts = db._pg_ddl(db.SCHEMA)
    joined = "\n".join(stmts)
    assert "AUTOINCREMENT" not in joined                 # translated away
    assert "SERIAL PRIMARY KEY" in joined                # ... to SERIAL
    assert "--" not in joined                            # comments stripped
    assert all(";" not in s for s in stmts)              # one command per chunk
    assert any(s.startswith("CREATE TABLE IF NOT EXISTS application_task") for s in stmts)
    assert any("CREATE UNIQUE INDEX IF NOT EXISTS idx_task_opp" in s for s in stmts)


# ------------------------------------------- live Postgres (opt-in, gated) #
PG_URL = os.environ.get("TEST_DATABASE_URL", "")
pg_only = pytest.mark.skipif(not PG_URL, reason="set TEST_DATABASE_URL to a live Postgres")


@pg_only
def test_postgres_schema_and_atomic_claim():
    """Prove the PG path end to end: build the schema, seed one QUEUED task, and confirm two
    concurrent claims never both win it (the double-submit guard, §15)."""
    from app.config import settings
    from app.models import ApplicationTask, ApplicationStatus as St
    orig = settings.database_url
    settings.database_url = PG_URL
    try:
        # Fresh schema (SERIAL ids restart at 1 after the drop, keeping the FKs below simple).
        with db.get_conn() as conn:
            for t in ("worker", "application_task", "opportunity", "candidate"):
                conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        db.init_db()
        with db.get_conn() as conn:                       # minimal FK parents
            conn.execute("INSERT INTO candidate(name) VALUES (?)", ("t",))          # id 1
            conn.execute("INSERT INTO opportunity(candidate_id,data_json) VALUES (?,?)",
                         (1, "{}"))                                                  # id 1
        tid = db.upsert_task(ApplicationTask(opportunity_id=1, candidate_id=1, status=St.QUEUED))
        assert tid > 0

        a, _ = db.claim_next_task("wa", heartbeat_timeout=45, stale_grace=60)
        b, _ = db.claim_next_task("wb", heartbeat_timeout=45, stale_grace=60)
        assert a is not None and b is None               # exactly one winner
        assert db.get_task(tid).status == St.CLAIMED
    finally:
        settings.database_url = orig
