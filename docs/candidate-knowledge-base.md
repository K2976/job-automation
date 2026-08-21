# Candidate knowledge base

The résumé is **not** stored as one blob. It's decomposed into retrievable entities
(`kb.seed_profile`), each carrying provenance and metadata.

## Entities
`EntityType`: `skill · project · experience · education · certification · achievement`.

Each becomes a `KBEntity` row (`models.py`, `db.kb_entity`):

| Field | Purpose |
|---|---|
| `entity_type`, `name` | structured filtering, display |
| `content` | the text embedded + keyword-searched |
| `data` (JSON) | type-specific fields (technologies, responsibilities, metrics…) |
| `domain` | structured filter |
| `status` | provenance (see below) |
| `source` | `master_resume`, `user_confirmation`, … |

`content` is built per type (`kb._project_content`, `_experience_content`) so retrieval
sees a meaningful, self-contained chunk — including responsibilities, achievements and
technologies for projects. Skill `content` is the skill **name only** (a category code like
`ml` must never be mistaken for a skill mention).

## Provenance
`Status` on every entity. New candidate-confirmed skills (from approved suggestions) are
inserted via `kb.add_confirmed_skill` with `USER_CONFIRMED`/`USER_EDITED` — **never**
`ORIGINAL`. This keeps the "verified vs confirmed vs missing" distinction honest.

## Metadata for RAG
Retrieved results retain `entity_id`, `entity_type`, `name`, `status`, `score` and a
snippet (`retrieval.ScoredEntity.to_evidence` → `EvidenceRef`) so every piece of evidence
is traceable back to a provenance-tagged source — no anonymous chunks.

## Role profiles (future)
One master profile can back many role-specific views. V1 realises a view per Job (analysis
+ approved modifications persisted per `job_id`); a named, reusable "Role Profile" entity is
a natural V1.x extension over the same KB.
