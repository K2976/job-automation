# Deployment runbook

The one document to follow for a demo. Deploy order first (once), then the per-demo routine.

## One-time deployment order

Follow in sequence — it's circular, so order matters (see also [render-deployment.md](render-deployment.md),
[vercel-deployment.md](vercel-deployment.md)).

1. **PostgreSQL** — create the managed Postgres on Render (or let `render.yaml` create it).
2. **Render API** — deploy the backend; it reads `DATABASE_URL` from the database.
3. **Vercel frontend** — deploy with `VITE_API_BASE` = the Render URL.
4. **CORS** — set `CORS_ORIGINS` = the Vercel URL on Render, redeploy.
5. **Worker token** — set `WORKER_AUTH_TOKEN` on Render (and `INLINE_APPLICATIONS=false`).
6. **MacBook worker** — put the same token in `.env.worker`, build the Docker image.
7. **Smoke test** — run one application through (below).

The browser worker is **never** deployed to Render.

Generate the worker token once:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Before the HR demo

1. **Start Docker Desktop** on the MacBook.
2. **Start the browser worker:**
   ```bash
   docker compose up browser-worker      # or: ./scripts/run-browser-worker.sh
   ```
   (Reads `.env.worker` — `API_BASE_URL`, `WORKER_AUTH_TOKEN`. See [mac-browser-worker.md](mac-browser-worker.md).)
3. **Verify the heartbeat:** the worker logs `-> https://…onrender.com (poll 5s)` and then
   claim attempts. Or check the API directly:
   ```bash
   curl -s https://<api>.onrender.com/api/worker/status
   # {"online": true, "inline": false, ...}
   ```
4. **Open the Vercel site.**
5. **Confirm worker status is Online** — the Applications tab shows a green
   “Automation worker · Online”.

## During the demo

1. **Find opportunities** (Opportunities tab → discovery).
2. **Prepare a batch** and **select** the applications to run (≤ the batch maximum — enforced
   server-side, no backfill).
3. **Create application tasks**, pick an approval mode (Manual / Review / Autonomous), and
   **Start**. Tasks become `QUEUED`.
4. **Monitor task status.** The MacBook worker claims each `QUEUED` task, drives it in a fresh
   Chromium context, and reports back; the UI polls and updates.
5. **Handle intervention** when a task pauses:
   - `REVIEW_REQUIRED` → review the filled answers, then **Approve** to submit.
   - `USER_ACTION_REQUIRED` → answer the flagged (high-impact/unknown) question, re-queue.
   - `LOGIN_REQUIRED` / `BLOCKED` (CAPTCHA) → the automation stops and never bypasses (§34/§36).

Safety that stays true throughout: CAPTCHA is never bypassed; salary/visa/relocation/EEO
questions pause; uncertain submissions become `SUBMISSION_UNCERTAIN` (never auto-`APPLIED`);
a task is only `APPLIED` after a real successful submit.

## After the demo

1. **Stop the worker** — `Ctrl-C` (or `docker compose down`). It finishes the current task,
   then exits cleanly.
2. **The public website stays available.** Application automation simply shows Offline until
   the worker is started again.

## If the worker crashes mid-run

Nothing is stranded. A claimed task whose worker stops heartbeating is recovered on read: it
returns to `QUEUED` if no submit had been granted, or is flagged `SUBMISSION_UNCERTAIN`
(needs review) if it might already have submitted — never blindly retried (§18/§19).
