"""SQLite persistence. Direct sqlite3 — no ORM, no repository layer (V1 scale).
See ADR-001 for why SQLite stands in for Postgres here."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable, Optional

from .config import settings
from .models import (
    Candidate,
    EntityType,
    KBEntity,
    ModificationSuggestion,
    ModificationType,
    Status,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, email TEXT, phone TEXT, location TEXT, headline TEXT,
    links_json TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS kb_entity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    data_json TEXT DEFAULT '{}',
    domain TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ORIGINAL',
    source TEXT DEFAULT 'master_resume',
    created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_kb_candidate ON kb_entity(candidate_id);
CREATE INDEX IF NOT EXISTS idx_kb_type ON kb_entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_kb_status ON kb_entity(status);

CREATE TABLE IF NOT EXISTS job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    raw_text TEXT NOT NULL,
    role TEXT DEFAULT '',
    requirements_json TEXT DEFAULT '{}',
    resume_json TEXT DEFAULT '',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS suggestion (
    id TEXT PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job(id),
    candidate_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    target TEXT DEFAULT '',
    current TEXT DEFAULT '',
    suggested TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    requires_approval INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'AI_SUGGESTED',
    edited_text TEXT DEFAULT '',
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sugg_job ON suggestion(job_id);

CREATE TABLE IF NOT EXISTS role_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    name TEXT NOT NULL,
    target_role TEXT DEFAULT '',
    job_id INTEGER REFERENCES job(id),
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    provider TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    PRIMARY KEY (provider, text_hash)
);

-- V2: Opportunity Intelligence -------------------------------------------------
-- Queryable columns for the filter/dedup/cache paths; the full Opportunity model
-- lives in data_json (same lazy pattern as job.resume_json).
CREATE TABLE IF NOT EXISTS opportunity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    source TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    dedup_key TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    data_json TEXT NOT NULL,
    created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_opp_candidate ON opportunity(candidate_id);
CREATE INDEX IF NOT EXISTS idx_opp_dedup ON opportunity(candidate_id, dedup_key);
-- Caching / re-discovery: one canonical row per (candidate, source, source_id).
CREATE UNIQUE INDEX IF NOT EXISTS idx_opp_source
    ON opportunity(candidate_id, source, source_id);

CREATE TABLE IF NOT EXISTS search_preferences (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidate(id),
    data_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    data_json TEXT NOT NULL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_batch_candidate ON application_batch(candidate_id);

CREATE TABLE IF NOT EXISTS discovery_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    data_json TEXT NOT NULL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_run_candidate ON discovery_run(candidate_id);

-- V3: Application Automation ---------------------------------------------------
-- One task per selected opportunity (unique), so a retry mutates the same row and the
-- V2 batch maximum stays true by construction (§29).
CREATE TABLE IF NOT EXISTS application_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunity(id),
    batch_id INTEGER,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id),
    status TEXT NOT NULL DEFAULT 'READY',
    data_json TEXT NOT NULL,
    created_at TEXT, updated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_task_opp ON application_task(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_task_batch ON application_task(batch_id);
CREATE INDEX IF NOT EXISTS idx_task_candidate ON application_task(candidate_id);
"""


def get_conn() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Discovery runs in a BackgroundTask write while the UI polls-reads; wait instead of
    # raising "database is locked". ponytail: single busy_timeout, WAL if contention grows.
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created (SQLite has no IF NOT
    EXISTS for columns). Cheap and idempotent."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(job)")}
    if "resume_json" not in cols:
        conn.execute("ALTER TABLE job ADD COLUMN resume_json TEXT DEFAULT ''")


# ------------------------------------------------------------------ candidate #
def insert_candidate(c: Candidate) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO candidate(name,email,phone,location,headline,links_json) "
            "VALUES (?,?,?,?,?,?)",
            (c.name, c.email, c.phone, c.location, c.headline, json.dumps(c.links)),
        )
        return int(cur.lastrowid)


def get_candidate(candidate_id: int) -> Optional[Candidate]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM candidate WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        return None
    return Candidate(
        id=row["id"], name=row["name"], email=row["email"], phone=row["phone"],
        location=row["location"], headline=row["headline"],
        links=json.loads(row["links_json"] or "[]"),
    )


def list_candidates() -> list[Candidate]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM candidate ORDER BY id").fetchall()
    return [
        Candidate(id=r["id"], name=r["name"], email=r["email"], phone=r["phone"],
                  location=r["location"], headline=r["headline"],
                  links=json.loads(r["links_json"] or "[]"))
        for r in rows
    ]


# ------------------------------------------------------------------- kb_entity #
def _row_to_entity(row: sqlite3.Row) -> KBEntity:
    return KBEntity(
        id=row["id"], candidate_id=row["candidate_id"],
        entity_type=EntityType(row["entity_type"]), name=row["name"],
        content=row["content"], data=json.loads(row["data_json"] or "{}"),
        domain=row["domain"], status=Status(row["status"]), source=row["source"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def insert_entity(e: KBEntity) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO kb_entity(candidate_id,entity_type,name,content,data_json,"
            "domain,status,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (e.candidate_id, e.entity_type.value, e.name, e.content,
             json.dumps(e.data), e.domain, e.status.value, e.source,
             e.created_at, e.updated_at),
        )
        return int(cur.lastrowid)


def get_entities(
    candidate_id: int,
    *,
    entity_type: Optional[EntityType] = None,
    statuses: Optional[Iterable[Status]] = None,
) -> list[KBEntity]:
    """Structured filter over the KB — the deterministic half of hybrid retrieval."""
    q = "SELECT * FROM kb_entity WHERE candidate_id=?"
    params: list[Any] = [candidate_id]
    if entity_type is not None:
        q += " AND entity_type=?"
        params.append(entity_type.value)
    if statuses is not None:
        marks = ",".join("?" for _ in statuses)
        q += f" AND status IN ({marks})"
        params.extend(s.value for s in statuses)
    q += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_row_to_entity(r) for r in rows]


def get_entity(entity_id: int) -> Optional[KBEntity]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM kb_entity WHERE id=?", (entity_id,)).fetchone()
    return _row_to_entity(row) if row else None


def update_entity_status(entity_id: int, status: Status) -> None:
    from .models import _now
    with get_conn() as conn:
        conn.execute("UPDATE kb_entity SET status=?, updated_at=? WHERE id=?",
                     (status.value, _now(), entity_id))


def update_entity(entity_id: int, *, name: Optional[str] = None,
                  content: Optional[str] = None, data: Optional[dict] = None,
                  domain: Optional[str] = None, status: Optional[Status] = None) -> bool:
    from .models import _now
    sets, params = ["updated_at=?"], [_now()]
    if name is not None:
        sets.append("name=?"); params.append(name)
    if content is not None:
        sets.append("content=?"); params.append(content)
    if data is not None:
        sets.append("data_json=?"); params.append(json.dumps(data))
    if domain is not None:
        sets.append("domain=?"); params.append(domain)
    if status is not None:
        sets.append("status=?"); params.append(status.value)
    params.append(entity_id)
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE kb_entity SET {','.join(sets)} WHERE id=?", params)
        return cur.rowcount > 0


def delete_entity(entity_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("DELETE FROM kb_entity WHERE id=?",
                            (entity_id,)).rowcount > 0


def update_candidate(candidate_id: int, c: Candidate) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE candidate SET name=?,email=?,phone=?,location=?,headline=?,"
            "links_json=? WHERE id=?",
            (c.name, c.email, c.phone, c.location, c.headline, json.dumps(c.links),
             candidate_id))
        return cur.rowcount > 0


# ------------------------------------------------------------------------- job #
def insert_job(candidate_id: int, raw_text: str, role: str, requirements_json: str) -> int:
    from .models import _now
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO job(candidate_id,raw_text,role,requirements_json,created_at) "
            "VALUES (?,?,?,?,?)",
            (candidate_id, raw_text, role, requirements_json, _now()),
        )
        return int(cur.lastrowid)


def get_job(job_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone()


def save_generation(job_id: int, resume_json: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE job SET resume_json=? WHERE id=?", (resume_json, job_id))


def get_generation(job_id: int) -> Optional[str]:
    row = get_job(job_id)
    if row is None or not row["resume_json"]:
        return None
    return row["resume_json"]


# ------------------------------------------------------------------ suggestion #
def replace_suggestions(job_id: int, candidate_id: int,
                        suggestions: list[ModificationSuggestion]) -> None:
    from .models import _now
    with get_conn() as conn:
        conn.execute("DELETE FROM suggestion WHERE job_id=?", (job_id,))
        conn.executemany(
            "INSERT INTO suggestion(id,job_id,candidate_id,type,target,current,"
            "suggested,reason,requires_approval,status,edited_text,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(s.id, job_id, candidate_id, s.type.value, s.target, s.current,
              s.suggested, s.reason, int(s.requires_approval), s.status.value, "",
              _now()) for s in suggestions],
        )


def get_suggestions(job_id: int) -> list[ModificationSuggestion]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM suggestion WHERE job_id=? ORDER BY rowid",
                            (job_id,)).fetchall()
    out = []
    for r in rows:
        out.append(ModificationSuggestion(
            id=r["id"], type=ModificationType(r["type"]), target=r["target"],
            current=r["current"],
            suggested=r["edited_text"] or r["suggested"],
            reason=r["reason"], requires_approval=bool(r["requires_approval"]),
            status=Status(r["status"]),
        ))
    return out


def get_suggestion(suggestion_id: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM suggestion WHERE id=?",
                            (suggestion_id,)).fetchone()


def update_suggestion(suggestion_id: str, status: Status, edited_text: str = "") -> None:
    with get_conn() as conn:
        conn.execute("UPDATE suggestion SET status=?, edited_text=? WHERE id=?",
                     (status.value, edited_text, suggestion_id))


# ----------------------------------------------------------- role profiles #
def insert_role_profile(candidate_id: int, name: str, target_role: str,
                        job_id: int) -> int:
    from .models import _now
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO role_profile(candidate_id,name,target_role,job_id,created_at) "
            "VALUES (?,?,?,?,?)", (candidate_id, name, target_role, job_id, _now()))
        return int(cur.lastrowid)


def list_role_profiles(candidate_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM role_profile WHERE candidate_id=? "
                            "ORDER BY id DESC", (candidate_id,)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------- embedding cache #
def get_cached_vector(provider: str, text_hash: str) -> Optional[list[float]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT vector_json FROM embedding_cache WHERE provider=? AND text_hash=?",
            (provider, text_hash)).fetchone()
    return json.loads(row["vector_json"]) if row else None


def set_cached_vector(provider: str, text_hash: str, vector: list[float]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache(provider,text_hash,vector_json) "
            "VALUES (?,?,?)", (provider, text_hash, json.dumps(vector)))


# =========================================================================== #
# V2 — Opportunity Intelligence                                                #
# =========================================================================== #
def _opp_from_row(row: sqlite3.Row):
    from .models import Opportunity
    opp = Opportunity.model_validate_json(row["data_json"])
    opp.id = row["id"]
    return opp


def upsert_opportunity(opp) -> int:
    """Insert, or reuse the existing canonical row for (candidate, source, source_id) so a
    re-discovery keeps one record and its cached analysis (§30). Returns the row id.
    Pass an existing source_id-matching opp to refresh cheap fields; analysis is preserved
    by the caller (discovery reuses the stored opp when source_id already exists)."""
    from .models import _now
    opp.updated_at = _now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM opportunity WHERE candidate_id=? AND source=? AND source_id=?",
            (opp.candidate_id, opp.source, opp.source_id)).fetchone()
        if existing:
            opp.id = existing["id"]
            conn.execute(
                "UPDATE opportunity SET dedup_key=?,status=?,data_json=?,updated_at=? "
                "WHERE id=?",
                (opp.dedup_key, opp.status.value, opp.model_dump_json(), opp.updated_at,
                 opp.id))
            return int(opp.id)
        cur = conn.execute(
            "INSERT INTO opportunity(candidate_id,source,source_id,dedup_key,status,"
            "data_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (opp.candidate_id, opp.source, opp.source_id, opp.dedup_key, opp.status.value,
             opp.model_dump_json(), opp.discovered_at, opp.updated_at))
        return int(cur.lastrowid)


def save_opportunity(opp) -> None:
    """Persist changes to an existing opportunity (must have id)."""
    from .models import _now
    opp.updated_at = _now()
    with get_conn() as conn:
        conn.execute(
            "UPDATE opportunity SET dedup_key=?,status=?,data_json=?,updated_at=? WHERE id=?",
            (opp.dedup_key, opp.status.value, opp.model_dump_json(), opp.updated_at, opp.id))


def get_opportunity_by_source(candidate_id: int, source: str, source_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM opportunity WHERE candidate_id=? AND source=? AND source_id=?",
            (candidate_id, source, source_id)).fetchone()
    return _opp_from_row(row) if row else None


def get_opportunity(opp_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM opportunity WHERE id=?", (opp_id,)).fetchone()
    return _opp_from_row(row) if row else None


def list_opportunities(candidate_id: int, *, statuses: Optional[Iterable[str]] = None):
    q = "SELECT * FROM opportunity WHERE candidate_id=?"
    params: list[Any] = [candidate_id]
    if statuses is not None:
        statuses = list(statuses)
        q += f" AND status IN ({','.join('?' for _ in statuses)})"
        params.extend(statuses)
    q += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_opp_from_row(r) for r in rows]


# --------------------------------------------------------------- search prefs #
def save_preferences(prefs) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_preferences(candidate_id,data_json) VALUES (?,?)",
            (prefs.candidate_id, prefs.model_dump_json()))


def get_preferences(candidate_id: int):
    from .models import SearchPreferences
    with get_conn() as conn:
        row = conn.execute("SELECT data_json FROM search_preferences WHERE candidate_id=?",
                           (candidate_id,)).fetchone()
    if not row:
        return SearchPreferences(candidate_id=candidate_id)
    return SearchPreferences.model_validate_json(row["data_json"])


# --------------------------------------------------------------------- batch #
def insert_batch(batch) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO application_batch(candidate_id,data_json,created_at) VALUES (?,?,?)",
            (batch.candidate_id, batch.model_dump_json(), batch.created_at))
        return int(cur.lastrowid)


def save_batch(batch) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE application_batch SET data_json=? WHERE id=?",
                     (batch.model_dump_json(), batch.id))


def get_batch(batch_id: int):
    from .models import ApplicationBatch
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM application_batch WHERE id=?",
                           (batch_id,)).fetchone()
    if not row:
        return None
    b = ApplicationBatch.model_validate_json(row["data_json"])
    b.id = row["id"]
    return b


def list_batches(candidate_id: int):
    from .models import ApplicationBatch
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM application_batch WHERE candidate_id=? "
                           "ORDER BY id DESC", (candidate_id,)).fetchall()
    out = []
    for r in rows:
        b = ApplicationBatch.model_validate_json(r["data_json"])
        b.id = r["id"]
        out.append(b)
    return out


# ------------------------------------------------------------- discovery run #
def insert_run(run) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO discovery_run(candidate_id,data_json,created_at) VALUES (?,?,?)",
            (run.candidate_id, run.model_dump_json(), run.created_at))
        run.id = int(cur.lastrowid)
        return run.id


def save_run(run) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE discovery_run SET data_json=? WHERE id=?",
                     (run.model_dump_json(), run.id))


def get_run(run_id: int):
    from .models import DiscoveryRun
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM discovery_run WHERE id=?", (run_id,)).fetchone()
    if not row:
        return None
    r = DiscoveryRun.model_validate_json(row["data_json"])
    r.id = row["id"]
    return r


# ------------------------------------------------------- V3 application tasks #
def _task_from_row(row):
    from .models import ApplicationTask
    t = ApplicationTask.model_validate_json(row["data_json"])
    t.id = row["id"]
    return t


def upsert_task(task):
    """Insert, or return the existing task for this opportunity (unique) so a retry mutates
    one row instead of spawning a sibling (§29). Returns the row id."""
    from .models import _now
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM application_task WHERE opportunity_id=?",
            (task.opportunity_id,)).fetchone()
        if existing:
            task.id = existing["id"]
            conn.execute(
                "UPDATE application_task SET batch_id=?,status=?,data_json=?,updated_at=? "
                "WHERE id=?",
                (task.batch_id, task.status.value, task.model_dump_json(), _now(), task.id))
            return int(task.id)
        cur = conn.execute(
            "INSERT INTO application_task(opportunity_id,batch_id,candidate_id,status,"
            "data_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (task.opportunity_id, task.batch_id, task.candidate_id, task.status.value,
             task.model_dump_json(), task.created_at, _now()))
        return int(cur.lastrowid)


def save_task(task) -> None:
    from .models import _now
    with get_conn() as conn:
        conn.execute(
            "UPDATE application_task SET batch_id=?,status=?,data_json=?,updated_at=? WHERE id=?",
            (task.batch_id, task.status.value, task.model_dump_json(), _now(), task.id))


def get_task(task_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM application_task WHERE id=?", (task_id,)).fetchone()
    return _task_from_row(row) if row else None


def get_task_for_opportunity(opportunity_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM application_task WHERE opportunity_id=?",
                           (opportunity_id,)).fetchone()
    return _task_from_row(row) if row else None


def list_tasks(*, candidate_id: int | None = None, batch_id: int | None = None):
    q, params = "SELECT * FROM application_task WHERE 1=1", []
    if candidate_id is not None:
        q += " AND candidate_id=?"; params.append(candidate_id)
    if batch_id is not None:
        q += " AND batch_id=?"; params.append(batch_id)
    q += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_task_from_row(r) for r in rows]


def count_submitted_tasks(batch_id: int) -> int:
    """How many tasks in a batch have really been submitted — enforces the batch cap (§29)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status FROM application_task WHERE batch_id=?", (batch_id,)).fetchall()
    return sum(1 for r in rows if r["status"] in ("SUBMITTED", "CONFIRMED"))
