# Résumé generation

## Modification plan first (`planning.build_plan`)
Retrieval does **not** flow straight into generation. First a structured
`ModificationPlan` is produced and persisted for the candidate to review:

- **REWRITE** suggestions for the top-ranked relevant projects — the rewrite is generated
  by the LLM but grounded in *that project's own evidence* (no new facts).
- **ADD_SKILL** suggestions only for `USER_CONFIRMATION_REQUIRED` / `MISSING` requirements,
  each `requires_approval=True` with a reason ("only include if you genuinely have this").
- **emphasize / deemphasize / reorder** guidance (deterministic; drives ordering).

Only REWRITE and ADD_SKILL are approvable, because those are exactly where unsupported
claims could enter.

## Approval (`planning.apply_approval`)
`AI_SUGGESTED → USER_CONFIRMED` (accept) / `USER_EDITED` (edit) / `REJECTED` (reject).
An accepted/edited ADD_SKILL becomes a real KB skill entity with that provenance.

## Generation (`generation.generate_resume`)
Context = candidate identity (preserved verbatim) + JD requirements + ranked relevant
projects + **approved** rewrites + confirmed skills + emphasis order. It:
- includes only JD-relevant, supported skills (irrelevant iOS-only skills are dropped from
  the skills line);
- orders projects by relevance and drops clearly-irrelevant ones;
- uses approved rewrite text where the candidate approved it, else the original summary;
- tags every generated bullet `GENERATED` with `evidence_entity_id` back to its source;
- also builds structured `ResumeSection.entries` (heading / date / subheading / bullets)
  from the same supported evidence — the professional LaTeX layout needs them; the flat
  `bullets` are still filled for the reportlab/HTML/Markdown/preview renderers;
- renders Markdown (`render_markdown`); the structured model also drives HTML, a reportlab
  PDF, and the LaTeX template renderer (see [resume-template-system.md](resume-template-system.md)).

## What it does not do
It never copies the whole KB into every résumé, and never emits a skill the candidate
hasn't got via ORIGINAL evidence or an approved confirmation.
