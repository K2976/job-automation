# Approval Modes (V3)

How much human involvement an application requires (§9, §28). The mode is chosen per
`ApplicationBatch` and inherited by its tasks (§10); it can be overridden per task.

| Mode | Behaviour |
|------|-----------|
| `MANUAL` | The agent fills the form and stops at `REVIEW_REQUIRED`. It never submits — the user submits on the site themselves. |
| `REVIEW_BEFORE_SUBMIT` | The agent fills, stops at `REVIEW_REQUIRED`, and shows a summary. The user clicks **Approve & submit**, which re-drives and submits. |
| `AUTONOMOUS` | The agent submits automatically **iff** it is safe (see predicate). Otherwise it falls back to `REVIEW_REQUIRED` — it never submits unsafely. |

## One fill+validate path, one submit predicate

All three modes run the **identical** fill + classify + validate path. They differ only in
the terminal action. There is no separate autonomous code path that could skip a check.
Autonomous submission is gated by a single predicate, evaluated once (`runner.can_submit`):

```
can_submit = every required question resolved
         AND no question flagged requires_review
         AND the task is not BLOCKED / LOGIN_REQUIRED / USER_ACTION_REQUIRED
```

Even in autonomous mode, a high-impact or unknown required question flips the task to
`USER_ACTION_REQUIRED` and stops it (§11) — autonomous does not mean guessing.

## Pre-submit summary (§27)

For review/manual, `GET /api/applications/{id}/summary` returns the checkpoint:

```
questions, deterministic, llm_generated, user_provided, unresolved, can_submit, status
```

## Batch limit (§29)

V3 never submits more than the V2 batch maximum. There is one `ApplicationTask` per selected
opportunity (a unique constraint), created only up to `max_opportunities`, with **no
backfill** — if 2 of 10 fail, 8 are attempted, and opportunities #11/#12 are never pulled in.
A defensive check in the worker also refuses to submit once the batch's submitted count
reaches the maximum.

## APPLIED (§30)

`Opportunity.status = APPLIED` is set in exactly one place (the worker) and only when a task
reaches `SUBMITTED`/`CONFIRMED`. `SUBMISSION_UNCERTAIN`, `FAILED`, `BLOCKED` never mark an
opportunity applied.
