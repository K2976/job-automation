# Worker API

The `/worker` channel the MacBook browser worker uses to receive and update tasks. It is
separate from the public `/api` surface, guarded by a shared bearer token, and never exposes
internal DB operations. Source: `backend/app/worker_api.py`.

## Authentication (§13)

Every `/worker/*` request needs `Authorization: Bearer <WORKER_AUTH_TOKEN>`.

- The token is compared in constant time.
- **Fail closed:** if `WORKER_AUTH_TOKEN` is unset on the server, the whole channel returns
  `503` — it is never accidentally open.
- The token lives only in the Render config and the MacBook `.env.worker`. It is never sent
  to the frontend, never a `VITE_*` var, and never the Gemini/Groq key.

Per-task **ownership**: `complete`, `fail`, `events`, and the task heartbeat require the
caller's `worker_id` to match the task's claimer, so a worker can only touch the task it
actually claimed (§14).

## Endpoints

| Method + path | Purpose |
| --- | --- |
| `POST /worker/heartbeat` | Liveness ping (idle or busy) → drives the online/offline badge. |
| `POST /worker/tasks/claim` | Atomically claim the oldest `QUEUED` task. `204` if none. |
| `POST /worker/tasks/{id}/heartbeat` | Per-task liveness while running. |
| `POST /worker/tasks/{id}/events` | Append progress log lines (field names only, no values). |
| `POST /worker/tasks/{id}/complete` | Report the outcome; owns the `APPLIED` flip + cap check. |
| `POST /worker/tasks/{id}/fail` | Report a caught driver/browser crash. |
| `GET  /worker/tasks/{id}/resume.pdf` | Download the tailored résumé to upload. |
| `POST /worker/llm/answer` | Server-side semantic answer (keeps provider keys centralized). |
| `GET  /api/worker/status` | **Public** (no token) liveness for the frontend badge. |

## Claim response

`claim` returns the task, a serializable **context bundle** (candidate field values, top
evidence, JD text, supported skills, cover letter, role, and a `resume_url`), and a `submit`
flag. The worker has no DB access, so everything it needs to fill the form travels in this
response; the résumé is downloaded from `resume_url` (trap #1).

## Atomic claim (§15)

One `QUEUED` task goes to exactly one worker. Racing claims serialize:

- **SQLite:** `BEGIN IMMEDIATE` takes the write lock up front; the loser sees no `QUEUED` row.
- **Postgres:** `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` locks the chosen row so a concurrent
  claim skips it. Never a silent double-claim.

`submit` is decided once at claim time: granted for `AUTONOMOUS`, or for a `REVIEW` task the
user approved — and only if the batch is still under its maximum (§20). A granted decision is
persisted (`submit_granted`) so stale recovery knows the task might have submitted.

## Reportable statuses (§30)

`complete` accepts only: `REVIEW_REQUIRED`, `USER_ACTION_REQUIRED`, `LOGIN_REQUIRED`,
`BLOCKED`, `FAILED`, `SUBMITTED`, `CONFIRMED`, `SUBMISSION_UNCERTAIN`. The worker can **never**
write `APPLIED` (derived server-side, `SUBMITTED`/`CONFIRMED` only) or any arbitrary state.
Identity fields (opportunity/candidate/batch/approval mode) are always taken from the server's
task, never from the worker's payload.

## Heartbeat & stale recovery (§17, §18)

Workers heartbeat whether idle or busy, so the badge shows Online between tasks. A claimed
task is **stale** when its claim is older than a grace period *and* its worker's heartbeat has
expired. Recovery (run on read, no separate scheduler):

- no submit granted → back to `QUEUED` (safe to re-run),
- submit granted → `SUBMISSION_UNCERTAIN` + review (never auto-retried — could double-submit).

Timeouts: `WORKER_HEARTBEAT_TIMEOUT` (default 45s), `WORKER_STALE_GRACE` (default 60s).

## Security tests

`tests/test_worker_api.py` covers: unauthenticated reject, wrong-token reject, fail-closed
when unconfigured, atomic single-claim, ownership isolation, the `APPLIED` invariant, the
batch cap at claim, and both stale-recovery branches.
