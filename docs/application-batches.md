# Application Batches & Package Preparation (V2)

An **ApplicationBatch** is a controlled set of selected opportunities the candidate wants to
prepare applications for. It is a first-class concept (`backend/app/models.py`) so a future
V3 submission flow can consume it. V2 prepares packages; it never submits.

## The max-selection invariant (§24)

A batch has `max_opportunities`. This is a **hard ceiling enforced at selection time**:

```
discovered  ≥  viable  ≥  selected  ≤  max_opportunities
```

`batches.set_selection` rejects a selection larger than the maximum with
`BatchLimitExceeded` (HTTP **409**), atomically — nothing is partially applied. There is **no
auto-backfill**: if a selected opportunity later fails, opportunity #(max+1) is *not*
automatically pulled in. This is validation at a trust boundary and is deliberately simple
and deterministic. Selection is idempotent — the client sends the full desired set each call.
Selecting shortlists an opportunity (`SHORTLISTED`); deselecting returns it to `ANALYZED`.

## Package preparation (§26–§27)

`packages.prepare_batch` prepares every selected opportunity via the **unchanged V1
pipeline** — there is no second résumé generator:

```
opportunity.jd_text
   ► pipeline.analyze_job   (creates the V1 Job + modification plan; sets opportunity.job_id)
   ► pipeline.generate_for_job   (tailored résumé + validation + ATS; professional LaTeX/PDF)
   ► llm.compose_cover_letter    (optional, evidence-grounded)
   ► status = READY_TO_APPLY
```

This is where the expensive LLM work happens, and it is proportional to **selected**
opportunities (≤ batch max), not to analysed ones. The tailored résumé is exported through
the existing V1 endpoints (`/api/jobs/{job_id}/export.{tex,latex.pdf,pdf,html,md}`) — the
opportunity carries the `job_id`.

Generation only ever uses `ORIGINAL` evidence and user-confirmed modifications; unapproved
suggestions are simply not applied, and the claim validator flags anything unsupported — so
auto-preparing a package never fabricates claims (V1's human-in-the-loop guarantees hold).

## Cover letter (§27)

Generated from the opportunity JD + the candidate's **own match evidence** only. The prompt
(`prompts.cover_letter`) forbids inventing employers, metrics, achievements, dates, or
relationships, and forbids placeholders. The offline mock produces a deterministic,
grounded letter from the supplied evidence names and skills — nothing about the company or
candidate is invented.

## Tracker (§28)

`POST /api/opportunities/{id}/status` moves an opportunity through the pipeline
(`SHORTLISTED / READY_TO_APPLY / APPLIED / REJECTED / SKIPPED`). `APPLIED` is **manual only** —
V2 never sets it automatically.

## V3 readiness

`ApplicationBatch` (id, candidate, name, max, target_roles, filters, opportunity_ids,
status), each opportunity's `application_url`, `job_id`, and `cover_letter`, and the future
approval policy (`MANUAL / REVIEW_BEFORE_SUBMIT / AUTONOMOUS`, §36) are the interfaces a V3
submission agent will consume. None of that submission behaviour is implemented in V2.
