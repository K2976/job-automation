# ADR-001: SQLite instead of PostgreSQL for V1

**Status:** Accepted

## Context
`CLAUDE.md` names PostgreSQL as the preferred store. The development machine has no
PostgreSQL and no Docker. `CLAUDE.md` also instructs preferring the least-disruptive
option and updating docs when the architecture genuinely changes.

## Decision
Use stdlib `sqlite3` for V1. Access it directly (no ORM, no repository layer).

## Rationale
- Zero install; the app and tests run anywhere Python does.
- Real SQL still backs the structured-filter and provenance queries the product needs.
- The candidate KB is a single person's profile (dozens of rows) — Postgres buys nothing
  at this scale yet.
- A future migration to Postgres is a migration (swap `db.py`), not an interface we must
  pay for now.

## Consequences
- No concurrent-writer story and no pgvector — both irrelevant at V1 scale.
- `db.py` is the single seam to change when Postgres is warranted (multi-user, scale).
