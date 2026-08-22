# Opportunity Intelligence (V2)

V1 answers *"I have a JD — how do I tailor my résumé for it?"*. V2 answers
*"Which opportunities should I apply to, and why?"* — it discovers roles, analyses them
with the **existing V1 RAG engine**, ranks them, and prepares application packages. It does
**not** submit applications (that is V3).

The central entity is the **Opportunity** (`backend/app/models.py`), not `Job`. A `Job` is a
V1 internal record created only when an opportunity's package is prepared.

## Pipeline

```
preferences ─► sources ─► collect ─► normalize ─► filter ─► dedup ─► cheap match ─► rank
                                                                         │
                                                             top-N ─► deep analysis (V1 RAG)
                                                                         │
                                                                    persist + shortlist
```

Everything left of "deep analysis" is **deterministic and LLM-free** (`opportunities/
processing.py`). Only the top-N survivors reach an LLM, and each costs exactly **one**
`analyze_jd` call — see below.

| Stage | Module | LLM? |
|-------|--------|------|
| Collect (per source, error-isolated) | `opportunities/discovery.py` + `sources/` | no |
| Normalize (company/title/location/URL/dates, tech extraction) | `processing.normalize` | no |
| Hard filter (role, location, seniority, employment type, exclusions, already-seen) | `processing.passes_filters` | no |
| Deduplicate (canonical key keeps seniority distinct) | `processing.deduplicate` | no |
| Cheap match (V1 hybrid index + skill overlap) | `processing.cheap_score` | no |
| Deep analysis (requirements + matches + gaps) | `pipeline.match_jd` | **1 call/opp** |
| Rank (deterministic blend) | `processing.opportunity_score` | no |

## Cost architecture (§3, §34)

The discovery pipeline must never send every scraped opportunity to an LLM. Two safeguards:

1. **Cheap-first funnel.** Cheap filtering + matching cut the set to `DISCOVERY_DEEP_TOP_N`
   (default 15) before any LLM call.
2. **`match_jd`, not `analyze_job`.** `pipeline.analyze_job` also runs `planning.build_plan`,
   which calls `llm.rewrite` **per project** (up to 3×). Using it at discovery would cost
   `N×(1+rewrites)` calls. `pipeline.match_jd` does only `analyze_jd` + deterministic
   matching/gaps — one call per opportunity. The full `analyze_job` (+ rewrites +
   generation) runs only when a package is prepared, i.e. proportional to *selected*
   opportunities (≤ batch max), not *analysed* ones.

Context sent to the LLM is minimised: the opportunity JD only. Candidate evidence is
retrieved locally by the hybrid index; the whole profile is never shipped to a provider.

## V1 reuse (§16)

V2 does not have a second matching system. `match_jd` calls the same `llm.analyze_jd`,
builds the same `RetrievalIndex`, and runs the same `matching.match_requirements` /
`analyze_gaps` as V1. The `why_apply` explanation (`processing.why_apply`) is derived from
those V1 `RequirementMatch` objects. Package preparation calls `pipeline.analyze_job` +
`pipeline.generate_for_job` unchanged — the tailored résumé (and its professional LaTeX
output) is produced by the V1 pipeline.

## Ranking (§18)

`opportunity_score` is a **deterministic, reproducible** blend — documented weights in
`processing._RANK_WEIGHTS`:

```
0.50 · jd_match      (V1 requirement coverage)
0.20 · cheap_score   (retrieval + skill overlap)
0.15 · role_pref     (title matches a target role)
0.15 · location_pref (remote, or matches a preferred location)
```

An LLM contributes inputs (via `jd_match`) but never the final ordering: given the same
stored opportunity and preferences, the score is always identical. It is a decision aid,
not a prediction.

## Opportunity lifecycle (§11)

`DISCOVERED → FILTERED → ANALYZED → SHORTLISTED → TAILORING → READY_TO_APPLY`, plus
terminal `APPLIED / REJECTED / SKIPPED / EXPIRED / BLOCKED`. **V2 never sets `APPLIED`
automatically** — only the user does, via the tracker (§28). Terminal opportunities are not
resurfaced by a later discovery run.

## Caching (§30)

Opportunities are keyed on `(candidate, source, source_id)` (a unique index). Re-discovery
upserts the canonical row instead of duplicating it, and reuses stored `requirements /
matches / gaps` when the normalized JD text is unchanged — so an unchanged opportunity is
never re-analysed by the LLM.

## Background execution (§41)

Discovery can touch the network across several sources, so it runs as a FastAPI
`BackgroundTask`. The API returns a `run_id` immediately; the client polls
`GET /api/discovery/runs/{id}`. Real counts (`discovered / after_filtering / after_dedup /
deeply_analyzed / shortlisted`) are written to the `DiscoveryRun` as each stage completes —
progress is never faked. Known ceiling: on Render's free tier an idle instance can be
suspended mid-run; at fixture+API scale a run is seconds, so this is acceptable (marked in
code). SQLite `busy_timeout` covers the concurrent poll-read / task-write.

## V3 boundary (§35)

The `Opportunity`, `ApplicationBatch`, `application_url` and package structures are shaped so
a future V3 browser agent can consume them. V2 implements **none** of: browser automation,
form filling, automatic submission, or CAPTCHA handling beyond skip-and-report.
