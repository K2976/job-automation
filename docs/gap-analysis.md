# Evidence matching & gap analysis

## Matching (`matching.match_requirements`)
For each JD requirement (required skills, preferred skills, responsibilities) we retrieve
the top evidence and classify deterministically from two signals:
- **exact**: the normalised requirement is in the candidate's skill set
  (`candidate_skill_set` — skills extracted from all supported evidence).
- **best**: the top fused retrieval score.

```
exact                         → STRONG_MATCH
best ≥ 0.45                    → STRONG_MATCH
0.22 ≤ best < 0.45            → PARTIAL_MATCH
0.10 ≤ best < 0.22 (skill)    → USER_CONFIRMATION_REQUIRED
0.10 ≤ best < 0.22 (resp.)    → WEAK_MATCH
best < 0.10                    → MISSING
```
Thresholds are named constants in `matching.py` (tunable). Each match carries a `reason`
and its supporting `EvidenceRef`s.

## Why `USER_CONFIRMATION_REQUIRED` exists
It's the "you might have this, but the profile isn't specific enough" bucket. Loosely
related evidence exists, so instead of claiming or discarding, the system **asks the
candidate**. This is the honest middle ground between STRONG and MISSING.

## Gaps (`matching.analyze_gaps`)
Everything that isn't a STRONG match is a gap, categorised by its match status, each with a
`suggested_action`:
- `PARTIAL_MATCH` → reframe existing evidence to foreground the requirement.
- `USER_CONFIRMATION_REQUIRED` → ask the candidate to confirm before including.
- `MISSING` → do **not** fabricate; flag as a genuine gap or ask.

## Scoring (JD alignment)
See [validation.md](validation.md) for the claim validator and `analysis.ats_report` for
the JD-alignment score (weighted skill/keyword/requirement/project coverage). Scores are
product indicators, not guarantees.
