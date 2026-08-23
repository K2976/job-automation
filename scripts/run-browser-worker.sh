#!/usr/bin/env bash
# Build and start the MacBook browser worker (§26). It connects OUT to the deployed Render
# API, claims tasks, and runs Playwright locally. Reads secrets from .env.worker (gitignored).
# No ports are published — the worker never listens (§8). Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=adaptive-resume-worker:local
ENV_FILE=.env.worker

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.worker.example to $ENV_FILE and fill it in." >&2
  exit 1
fi

echo "==> Building $IMAGE"
docker build -f Dockerfile.worker -t "$IMAGE" .

echo "==> Starting browser worker (Ctrl-C to stop)"
# --init: clean signals to the browser subprocess. --rm: no leftover container.
docker run --rm --init --env-file "$ENV_FILE" "$IMAGE"
