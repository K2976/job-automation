# Dockerized browser worker

The worker image bundles Playwright + Chromium + the app code so the MacBook can run V3
browser automation in a clean, isolated container. It runs **only on the MacBook**, never on
Render (§5, §43).

## Image

`Dockerfile.worker` is built on the official Playwright image pinned to the project's version:

```
mcr.microsoft.com/playwright/python:v1.62.0-noble
```

This must match the installed `playwright` (1.62.0). The image already ships Python, Chromium,
and all OS libraries, so **browser binaries are never installed at container start**. Do not
switch to `latest`.

## Build & test

Prove Playwright + Chromium + the V3 engine work inside the container against the local mock
site (no network, no real job sites):

```bash
./scripts/test-browser-worker.sh
# = docker build -f Dockerfile.worker -t adaptive-resume-worker:local .
#   docker run --rm --init adaptive-resume-worker:local \
#     python -m pytest tests/test_application_playwright.py tests/test_application_engine.py -q
```

## Run

```bash
docker compose up browser-worker      # or ./scripts/run-browser-worker.sh
```

Both read `.env.worker` (see [mac-browser-worker.md](mac-browser-worker.md)).

## Security (§8, §35)

- **No exposed ports.** The worker is an outbound client; the image has no `EXPOSE`, and the
  run commands publish no ports. No Chromium remote-debugging or Playwright control port is
  reachable.
- **Non-root.** Runs as the image's `pwuser`.
- **Container is the isolation boundary.** Chromium runs with `--no-sandbox` *inside* the
  container only (`PLAYWRIGHT_CHROMIUM_ARGS`); the host/test path keeps the sandbox on.
- **Isolated browser context per task**, no cookies shared between applications; the résumé
  PDF is downloaded to a temp file and deleted after each task — the Mac filesystem is never
  exposed to browser content, and no candidate content is shell-executed.
- **One browser, one task at a time** (§35). Tasks drain serially; the context is closed and
  memory freed between them. No concurrency tuning for the demo.

## No bypass (§36)

The image adds no CAPTCHA solver, stealth plugin, fingerprint spoofing, or proxy rotation. If
a site blocks the automation, the task stops and reports `BLOCKED`.
