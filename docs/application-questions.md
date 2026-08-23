# Application Questions (V3)

Every form field is turned into a structured `ApplicationQuestion` with an answer and its
provenance (`applications/questions.py`). An LLM is spent only on genuine semantic free-text.

## Answer sources

| Source | Meaning |
|--------|---------|
| `CANDIDATE_PROFILE` | identity/contact field filled from the master profile |
| `APPLICATION_PACKAGE` | tailored résumé file or the V2 cover letter |
| `DETERMINISTIC_RULE` | derived deterministically |
| `LLM_GENERATED` | semantic answer produced by the LLM and **validated** |
| `USER_PROVIDED` | the user supplied it (e.g. a high-impact question) |
| `UNRESOLVED` | no safe answer yet — pauses the task |

## Classification order (first match wins)

1. **Résumé upload** → the tailored package artifact (`field_mapper` + file type). §14.
2. **High-impact question** → `requires_review`, `UNRESOLVED`. Salary, work authorization /
   visa, relocation, availability / start date, clearance, citizenship, demographics/EEO.
   Never auto-answered, in **any** mode (§11).
3. **Cover letter field** → the V2-generated cover letter.
4. **Identity/contact field** → the profile value (`field_mapper.candidate_field_values`).
   Missing-but-required → review.
5. **Semantic free-text** (textarea, or a label like "why…", "describe…", "what makes…") →
   the LLM (§16), then validation (below).
6. **Dropdown / radio / checkbox, required & unmapped** → review — never guess a choice.
7. **Unmapped text field** → review if required, else skipped.

## Field mapping (deterministic, §13)

`field_mapper` normalizes the field label + name and matches against an alias table using
contiguous-phrase matching, longest phrase first (so "first name" → `first_name` before the
bare "name" → `full_name`). First/last name are split from the flat `Candidate.name`;
LinkedIn/GitHub/website are pulled from `Candidate.links`. No LLM, no giant static
dictionary of every website's fields.

## LLM answer + validation (§16–§18)

The LLM receives only the **question + JD context + top candidate evidence** — never the
whole database. It returns structured JSON:

```json
{ "answer": "...", "source_evidence": [], "confidence": 0.0, "requires_review": false }
```

Before the answer is filled, it is validated (`questions._answer_supported`): every
skill/technology named in the answer must be backed by the candidate's supported skills or
the evidence provided. If the model flags review, the answer is empty, or a claim is
unsupported → `requires_review` and the task pauses. This reuses V1's skill lexicon — the
same anti-hallucination primitive as résumé validation, not a parallel system.

## Pausing & resuming

A required question that is `requires_review` or has no answer makes the task
`USER_ACTION_REQUIRED`. The user answers via `POST /api/applications/{id}/answers`
(`USER_PROVIDED`) and re-runs. On a re-drive the runner **carries over** `USER_PROVIDED` and
already-reviewed `LLM_GENERATED` answers by field identity — so a user's answer is never
lost and a reviewed answer is never silently regenerated (matters under a real provider).
