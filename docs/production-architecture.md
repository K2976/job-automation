# Production architecture (V3.5)

The public product is fully hosted. The heavy browser automation runs on the MacBook only
while a demo is active. The two are decoupled: the site works whether or not the MacBook is on.

```
                         HR / USER
                             │
                             ▼
                      ┌─────────────┐
                      │   Vercel    │  React/Vite static frontend
                      └──────┬──────┘
                             │ HTTPS
                             ▼
                      ┌─────────────┐
                      │   Render    │  FastAPI backend (never launches Chromium)
                      │   FastAPI   │
                      └──────┬──────┘
                ┌────────────┼─────────────┐
                ▼            ▼             ▼
           PostgreSQL   task state     LLM APIs
                │
                │  ApplicationTask = QUEUED
                ▼
        ┌─────────────────────┐
        │      MY MACBOOK      │  outbound-only, authenticated
        │  Docker → Playwright │  claims + runs + reports tasks
        │  → Chromium worker   │
        └─────────┬───────────┘
                  ▼
          Target job website
```

## The boundary (do not blur it)

| Public production (always on) | Demo-only local (MacBook) |
| --- | --- |
| Vercel frontend | Docker + Playwright + Chromium |
| Render FastAPI API | The browser worker (`worker/worker.py`) |
| Render managed PostgreSQL | — |

- The MacBook is **not** the website server. The public site stays up when it's off.
- Only V3 browser automation is unavailable while the worker is offline — discovery, resume
  generation, and everything else keep working (the UI shows the worker as Offline, §31/§32).
- The worker makes an **outbound** authenticated connection to the Render API to get and
  update tasks. It never listens on a port; no Playwright/Chromium port is exposed (§8).

## Where each responsibility lives

- **Render API** owns all state: creates `ApplicationTask` rows, hands them out atomically,
  records outcomes, and is the **only** place `Opportunity → APPLIED` is set (§30). It also
  enforces the V2 batch maximum server-side (§20) and proxies semantic LLM answers so
  provider keys stay centralized (§28).
- **MacBook worker** does browser work only: navigate, detect fields, fill deterministically,
  upload, inspect, submit. It runs the *existing* V3 runner unchanged against real Chromium.

## Request/response contract

See [worker-api.md](worker-api.md) for the `/worker` endpoints, the bearer-token auth, the
atomic claim, heartbeats, and stale-task recovery. See [database.md](database.md) for the
SQLite/Postgres dialect split, and [deployment-runbook.md](deployment-runbook.md) for the
step-by-step demo procedure.
