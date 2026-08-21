# API reference

Base URL: `http://127.0.0.1:8000`. All bodies are JSON unless noted. Errors return
`{"detail": "..."}` with 400 (bad input), 404 (not found) or 502 (provider failure).

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | — | provider config |
| GET | `/api/fixtures/jds` | — | `{role: jd_text}` sample JDs |
| POST | `/api/candidates/seed-fixture` | — | `{candidate_id, candidate}` |
| POST | `/api/ingest` | multipart `file` **or** form `text` | parsed `MasterProfile` (not persisted) |
| POST | `/api/candidates` | `MasterProfile` | `{candidate_id}` |
| GET | `/api/candidates/{id}` | — | `{candidate, entities}` |
| PATCH | `/api/candidates/{id}` | `Candidate` fields | `{candidate}` |
| POST | `/api/candidates/{id}/entities` | `{entity_type, name, content, domain?}` | created `KBEntity` |
| PATCH | `/api/entities/{id}` | `{name?, content?, domain?, status?}` | updated `KBEntity` |
| DELETE | `/api/entities/{id}` | — | `{deleted}` |
| POST | `/api/jobs` | `{candidate_id, jd_text}` | `{job_id, requirements, matches, gaps, plan}` |
| GET | `/api/jobs/{id}/plan` | — | `{suggestions}` (current statuses) |
| POST | `/api/suggestions/{id}/approve` | `{action, edited_text?}` | `{suggestion_id, status}` |
| POST | `/api/jobs/{id}/generate` | — | `{resume, validation, ats, comparison, matches}` |
| GET | `/api/jobs/{id}/explain?requirement=` | — | evidence trace for a requirement |
| GET | `/api/jobs/{id}/export.pdf` \| `.html` \| `.md` | — | résumé download (generates once if needed) |
| POST | `/api/candidates/{id}/role-profiles` | `{name, job_id}` | saved role view |
| GET | `/api/candidates/{id}/role-profiles` | — | `{role_profiles}` |
| GET | `/` | — | React app (falls back to legacy static UI if unbuilt) |

`action` ∈ `ACCEPT | EDIT | REJECT`. Interactive docs at `/docs` (Swagger, auto-generated
from the Pydantic models).

## Typical flow
```
seed-fixture ─► POST /api/jobs ─► (POST /api/suggestions/{id}/approve …) ─► POST /api/jobs/{id}/generate
```

## Example
```bash
CID=$(curl -s -XPOST localhost:8000/api/candidates/seed-fixture | jq .candidate_id)
curl -s -XPOST localhost:8000/api/jobs -H 'content-type: application/json' \
  -d "{\"candidate_id\":$CID,\"jd_text\":\"Data Engineer. Required: Python, SQL, Airflow\"}"
```
