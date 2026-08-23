#!/usr/bin/env bash
# Prove Playwright + Chromium + the V3 engine run inside the worker container (§7).
# Builds the image, then runs the real-browser conformance suite against the local mock
# site — no network, no job sites. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=adaptive-resume-worker:local

echo "==> Building $IMAGE"
docker build -f Dockerfile.worker -t "$IMAGE" .

echo "==> Running V3 browser tests inside the container"
# --init for clean signal handling of the browser subprocess. No ports published (§8).
docker run --rm --init "$IMAGE" \
  python -m pytest tests/test_application_playwright.py tests/test_application_engine.py -q
