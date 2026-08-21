# ADR-005: Vite + React + Tailwind frontend instead of Next.js

**Status:** Accepted

## Context
CLAUDE.md §26 names Next.js/TypeScript/React/shadcn as the frontend direction. Part 2
requires a full multi-screen frontend. No frontend framework existed yet (Part 1 shipped a
thin static single-page UI).

## Decision
Build the frontend with **Vite + React + TypeScript + Tailwind CSS v4**, hand-rolling a few
small Tailwind UI primitives instead of pulling the full shadcn/Radix toolchain. FastAPI
serves the built `frontend/dist`, falling back to the legacy `static/index.html` when the
app hasn't been built.

## Rationale
- The product is a **client-only dashboard** talking to a JSON API. Next.js's SSR/RSC/app-
  router machinery buys nothing here and adds ceremony; Vite builds to static files the
  existing FastAPI already serves.
- Faster cold setup, simpler mental model, one build command (`npm run build`).
- Tailwind primitives cover the needed components (buttons, cards, badges, bars) without the
  shadcn init/Radix dependency surface — "shadcn where appropriate" (§26), and here it isn't.
- Same "simpler than the spec, justified, documented" pattern as ADR-001/002/004.

## Consequences
- No SSR/SEO — irrelevant for an authenticated single-user tool.
- TS API types are hand-maintained against the Pydantic models (`src/api/types.ts`). Small
  and stable; if drift becomes a problem, generate from `/openapi.json` with
  openapi-typescript.
- A python-only checkout runs the legacy static UI until `npm run build` is run.
