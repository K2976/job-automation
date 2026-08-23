# Application Automation (V3)

V3 automates applying for `READY_TO_APPLY` opportunities from V2. It is **deterministic-first
browser automation**: Playwright and the DOM/accessibility tree do the work; the LLM is used
only where a question genuinely needs semantic interpretation. Browser automation is a
supporting infrastructure layer, not the intelligence layer.

```
V2 Opportunity (READY_TO_APPLY, has tailored résumé + cover letter)
        ↓  create ApplicationTask (one per opportunity, ≤ batch max)
Browser worker (Playwright, isolated context per task)
        ↓  inspect → map fields deterministically → LLM only for semantic questions
        ↓  validate answers → apply approval policy
        ↓  submit (only when permitted) → detect confirmation
Opportunity.status = APPLIED  (only on a real submission)
```

## What V3 reuses (never re-implements, §47)

| Need | Reused from |
|------|-------------|
| Tailored résumé (uploaded file) | V1 `generate_for_job` → reportlab PDF (`export.build_pdf`) |
| Cover letter | V2 `packages` (generated once, stored on the opportunity) |
| Candidate evidence for answers | V1 `RetrievalIndex` / match evidence |
| Answer anti-hallucination | V1 skill lexicon (`text_utils`, same as validation) |
| Opportunity / ApplicationBatch / batch max | V2 models + invariant |

## Deterministic-first (§3)

Identity/contact fields (name, email, phone, LinkedIn, GitHub, city), résumé upload and the
cover letter are filled **without any LLM** (`field_mapper`, `questions`). The LLM answers
only free-text semantic questions ("why this role", "describe a project"), and its answer is
validated against candidate evidence before it is filled (`docs/application-questions.md`).
High-impact questions (salary, visa, relocation, demographics) are **never auto-answered** —
they pause the task in every mode, autonomous included.

## Layers

```
applications_api.py          thin HTTP surface (queue + controls)
applications/queue.py        create tasks (≤ max), build context, run serially, set APPLIED
applications/runner.py       orchestrator over BrowserPage — pure, no Playwright, no DB
applications/questions.py    field → ApplicationQuestion (+ LLM fallback + validation)
applications/field_mapper.py deterministic label/name → candidate field
applications/state_machine.py legal transitions
applications/page.py         BrowserPage protocol + FakePage (browser-free)
applications/playwright_page.py  real Playwright driver
```

The runner is pure over `(task, page, context)`, so it runs identically against `FakePage`
(tests, no browser) and `PlaywrightPage` (real Chromium). See `docs/browser-agent.md`.

## Safety & data integrity (§36, §46)

- The **master profile is never modified** during an application. Answers live on the
  `ApplicationTask`, never written back as candidate evidence.
- **No passwords or session cookies are stored.** A site requiring auth → `LOGIN_REQUIRED`
  (handoff), not credential capture. Browser contexts are isolated per task (no shared
  cookies).
- **CAPTCHAs are never bypassed** — detected → `BLOCKED`, reported, not retried (§22).
- Logs record field **names**, never values, and never secrets (§33).
- `APPLIED` is set in exactly one place — the worker, only for `SUBMITTED`/`CONFIRMED`.
  `SUBMISSION_UNCERTAIN` never counts as applied (§30, §31).

## V3 boundaries (§52)

No CAPTCHA bypass, no anti-bot evasion, no fabricated answers, no password storage, no live
browser-viewer UI, no screenshot-driven LLM control, no auto-backfill beyond the batch limit.
