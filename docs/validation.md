# Claim validation (anti-hallucination)

A separate post-generation step (`validation.validate_resume`) — the generation model is
never blindly trusted (CLAUDE.md §22).

## Claim extraction
Claims = each skill on the skills line, each generated bullet (with its linked evidence
entity), and numeric metrics in the summary.

## Support classification
Every skill the candidate has is mapped to its **best** backing provenance across all
non-rejected entities (`_skill_support`):

| Evidence provenance | Claim status |
|---|---|
| `ORIGINAL` | `SUPPORTED_BY_ORIGINAL` |
| `USER_CONFIRMED` / `USER_EDITED` | `SUPPORTED_BY_USER_CONFIRMATION` |
| `AI_SUGGESTED` (unapproved) | `AI_SUGGESTED_NOT_APPROVED` |
| none | `UNSUPPORTED` |

A claim takes the **worst** status among the skills it names. A rewrite that sneaks in an
unsupported skill is flagged even though its source project is `ORIGINAL` — baseline
provenance only applies to skill-less text.

## Metric check
Numbers in the summary that don't appear anywhere in the candidate's evidence tokens are
flagged `UNSUPPORTED` (catches invented metrics).

## Output
`ValidationReport` with per-claim status/reason and counts (`supported`,
`needs_approval`, `unsupported`). The UI colour-codes these; unsupported claims are never
allowed to read as verified facts. Tests: `tests/test_validation_ats.py`.
