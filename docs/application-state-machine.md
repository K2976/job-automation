# Application State Machine (V3)

`ApplicationTask.status` moves only along explicit legal edges
(`applications/state_machine.py`). An illegal transition raises `IllegalTransition` rather
than corrupting state.

## States (§8)

```
READY                 created, not yet queued
QUEUED / PAUSED       waiting to run / held
OPENING               browser opening the application URL
INSPECTING            reading the current page's form
FILLING               mapping + filling fields
REVIEW_REQUIRED       filled; awaiting human approval (manual/review, or unsafe autonomous)
USER_ACTION_REQUIRED  an unknown / high-impact question needs the user
LOGIN_REQUIRED        the site needs authentication (handoff, no credential capture)
BLOCKED               CAPTCHA / anti-bot — stopped, never bypassed
FAILED                unexpected/unsupported form, browser error, etc.
SUBMITTED             submit performed
CONFIRMED             submission confirmed by the page
SUBMISSION_UNCERTAIN  submitted but no confirmation found — NOT counted as applied
CANCELLED             user cancelled
```

## Legal transitions (abridged)

```
READY        → QUEUED | PAUSED | CANCELLED
QUEUED       → OPENING | PAUSED | CANCELLED
OPENING      → INSPECTING | BLOCKED | LOGIN_REQUIRED | FAILED
INSPECTING   → FILLING | BLOCKED | LOGIN_REQUIRED | FAILED
FILLING      → INSPECTING (next page) | REVIEW_REQUIRED | USER_ACTION_REQUIRED
             | BLOCKED | LOGIN_REQUIRED | FAILED | SUBMITTED | SUBMISSION_UNCERTAIN
REVIEW_REQUIRED      → SUBMITTED | SUBMISSION_UNCERTAIN | FILLING | FAILED | CANCELLED
USER_ACTION_REQUIRED → QUEUED | FILLING | CANCELLED | FAILED
LOGIN_REQUIRED       → QUEUED | FILLING | CANCELLED | FAILED
BLOCKED      → QUEUED (bounded retry) | CANCELLED     # retry re-queues; never bypasses
SUBMITTED    → CONFIRMED | SUBMISSION_UNCERTAIN
SUBMISSION_UNCERTAIN → CONFIRMED | FAILED
FAILED       → QUEUED (bounded retry)
CONFIRMED, CANCELLED → (terminal)
```

## Re-drive semantics

A re-drive (approve→submit, or a bounded retry) begins a fresh attempt: the runner resets
per-attempt state and re-opens/re-fills deterministically. Terminal tasks
(`CONFIRMED/SUBMITTED/SUBMISSION_UNCERTAIN/FAILED/CANCELLED`) are never re-driven implicitly;
a retry first re-queues a `FAILED`/`BLOCKED` task. `USER_PROVIDED` and reviewed
`LLM_GENERATED` answers are carried across the re-drive.

## Which states set APPLIED

Only `SUBMITTED` and `CONFIRMED` (`APPLIED_STATUSES`) cause the worker to set
`Opportunity.status = APPLIED`. Everything else — including `SUBMISSION_UNCERTAIN` — leaves
the opportunity un-applied (§30, §31).
