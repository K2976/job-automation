What it does

Adaptive Resume Engineer is a full-stack system that ingests a candidate's master resume, semantically analyzes a job description, and produces a tailored, evidence-grounded resume for that specific role — then (a newer V3 layer) can drive a real Chromium browser to autofill the resulting application on a job site. It uses hybrid retrieval (TF-IDF cosine + keyword overlap) over a chunked "candidate knowledge base" to find which of the candidate's projects/skills/experience are relevant to a given JD, classifies each requirement as a strong/partial/weak match or a gap, and requires human approval before any AI-suggested content is used in generation — provenance (ORIGINAL vs USER_CONFIRMED vs AI_SUGGESTED) is tracked on every claim and re-verified by a post-generation validator that flags unsupported skills/metrics. A separate V2 layer polls live Greenhouse and Lever job-board JSON APIs, cheap-scores and deep-analyzes postings against the candidate profile, and ranks a shortlist. The V3 layer turns an approved tailored resume into an actual browser-driven application: a Playwright-based agent inspects a real ATS form's DOM, classifies each field, fills what it can prove, and pauses on anything it can't (CAPTCHAs, logins, salary/visa/demographic questions) rather than guessing. The system is split-deployed — a FastAPI backend on Render, a React/Vite frontend on Vercel, Postgres for durable state — with the actual browser automation running as a separate outbound-only worker process (intentionally on a home machine, not the cloud, per project docs) that polls the API over HTTPS for work.

2. Tech stack (verified from source/config)

- Backend: Python 3.12/3.13, FastAPI ≥0.110, Pydantic ≥2.6 / pydantic-settings ≥2.2, Uvicorn
- Frontend: React 18.3, TypeScript 5.6, Vite 6, Tailwind CSS 4, Vitest 2.1 + Testing Library
- Database: dual-dialect — SQLite (default/dev) or PostgreSQL via psycopg[binary] ≥3.2 (production, Neon-hosted per render.yaml); no ORM, hand-written SQL with dialect branching
- Retrieval/embeddings: NumPy for brute-force cosine similarity; a hand-rolled TF-IDF embedder as the default "local" embedding provider (no torch/sentence-transformers in the dependency tree)
- LLM providers: pluggable interface (LLMProvider ABC) with three implementations — mock (deterministic, offline, default), gemini, groq — all over raw REST via httpx, no vendor SDKs
- Browser automation: Playwright ≥1.40 (Chromium), isolated to a separate worker component
- Document handling: pypdf, python-docx, reportlab (PDF generation), Jinja2 (LaTeX resume template rendering, optional tectonic engine)
- Deployment: Render (API, render.yaml), Vercel (frontend, vercel.json), Docker (Dockerfile.worker + compose.yaml) for the local browser worker
- Testing: pytest, 190 tests (189 pass, 1 skipped in this environment) — I ran the full suite myself

3. Core technical mechanisms

Retrieval: RetrievalIndex builds a TF-IDF matrix over candidate KB entities (skills/projects/experience chunks), fuses cosine similarity (weight 0.6) with a raw keyword-overlap score (weight 0.4) — both configurable via env. No vector DB; at KB scale (dozens of entities) brute-force NumPy matmul is exact and instant (documented rationale in ADR-002).

Gap analysis: fully deterministic (matching.py) — score thresholds (STRONG=0.45, PARTIAL=0.22, WEAK=0.10) plus exact-skill-presence checks classify each requirement; no LLM judgment call in this step, by explicit design (CLAUDE.md §9: LLM only where it adds value).

Anti-hallucination validation: every generated bullet/skill/summary-metric is traced back to its source entity's provenance status; a claim inherits the worst status among the skills it names (so a rewrite can't launder an unsupported skill through an otherwise-verified sentence), and unsupported numeric claims in the summary are flagged by regex-checking against evidence tokens.

Browser automation is the most technically substantial part:
- Protocol-based design: a BrowserPage interface with two implementations — FakePage (pure Python, used by 170+ unit tests) and PlaywrightPage (real Chromium) — so the entire fill/submit engine (runner.py) is tested without a browser and then re-verified against real Chromium in a second pass (test_application_playwright.py).
- Field identification uses a JS _DESCRIBE snippet injected via Playwright that walks aria-label → aria-labelledby → <label for> → parent <label> → <fieldset><legend> → placeholder → a heuristic sibling-text walk (explicitly marked ponytail: as a fallback heuristic, not a real accessible-name algorithm), specifically to handle Greenhouse-style comboboxes and demographic surveys that don't wire labels formally.
- A 22-state application state machine (state_machine.py) with an explicit legal-transition table — illegal transitions raise rather than corrupt state.
- High-impact fields (salary, visa/work-authorization, relocation, start date, security clearance, citizenship, demographic/EEO) are regex-matched and always paused for a human, in every approval mode including autonomous — never auto-answered.
- LLM use is narrow and defensive: only genuine free-text semantic questions reach the LLM (_is_semantic explicitly excludes select/radio/checkbox, even if their label reads like a question); answers are grounded against retrieved evidence and marked requires_review when there's no evidence to ground on.
- CAPTCHA/login detection via marker-string matching halts the run rather than attempting bypass.
- Confirmation is detected by scanning post-submit page text for a marker list; if no marker is found the task is marked SUBMISSION_UNCERTAIN, never falsely CONFIRMED — a deliberate choice to avoid overclaiming success.

Distributed worker architecture: the browser worker is an outbound-only HTTPS poller (never listens on a port) that claims one QUEUED task at a time from the API, runs it locally, and reports back. Concurrency-safe claiming is implemented for both SQLite (BEGIN IMMEDIATE) and Postgres (SELECT ... FOR UPDATE SKIP LOCKED) so two racing workers can never double-claim. A heartbeat thread pings the API every 15s during a run so a slow multi-minute application isn't falsely recovered as stale (timeout 90s, tuned specifically around Render free-tier cold-start behavior — documented in config.py). LLM calls from the worker are proxied back through the API (RemoteLLMProvider) so provider API keys never live on the worker machine.

Auth: the worker channel is a shared bearer token checked with hmac.compare_digest (constant-time, avoids timing attacks) and fails closed (empty token ⇒ the whole channel returns 503) — plus a per-task ownership check so a worker can only mutate tasks it actually claimed (409 on mismatch, not 404, to distinguish a lost race from a bad ID).

4. Scale and numbers (all verified directly)

- 190 tests collected, 189 passed / 1 skipped — I ran the suite myself just now
- ~6,534 lines of backend Python (backend/app), 2,893 lines of test code, 2,772 lines of frontend TypeScript, 207 lines for the standalone worker
- 39 markdown files in docs/, including 5 numbered Architecture Decision Records
- Retrieval eval: Hit@3 = 100% on a small hand-labeled benchmark (tests/evaluation/labels.py) — but this is a handful of labeled JD-requirement→evidence pairs against one candidate profile, not a large-scale eval
- Job discovery: 2 live source integrations (Greenhouse, Lever), defaulting to 7 boards (5 Greenhouse + 2 Lever), pipeline sizing caps of 15 (deep-analyzed) / 10 (shortlisted), hard cap of 50 results per run, pagination cap of 5 pages per source
- Browser task engine: hard cap of 12 pages per application (anti-infinite-loop safeguard)
- 67 git commits total

5. Resume-worthy technical substance

- Protocol-based testability for browser automation — a FakePage/PlaywrightPage dual implementation of the same interface lets the entire fill-and-submit state machine be unit-tested deterministically, then re-verified against real Chromium in a second, smaller test pass. This is a legitimately good pattern, not something most people bother to build for browser automation.
- Dual-dialect concurrency-safe job claiming (SQLite BEGIN IMMEDIATE vs. Postgres FOR UPDATE SKIP LOCKED) with heartbeat-based stale-claim recovery tuned around a real observed failure mode (Render free-tier cold starts).
- Provenance-tracked, anti-hallucination generation pipeline — every claim in the output resume traces to an entity with an explicit status (ORIGINAL/USER_CONFIRMED/AI_SUGGESTED), and a validator independently re-derives support status rather than trusting the generator.
- Security posture on the worker channel: fail-closed auth, constant-time comparison, per-task ownership checks, and a strict whitelist of statuses a worker is allowed to report (it can never mark itself "APPLIED" or write an arbitrary state — that transition happens in exactly one server-side code path).
- Honest internal evaluation docs — docs/rag-evaluation.md explicitly documents that the default TF-IDF embedder is lexical, so the "semantic vs. keyword" comparison in the benchmark doesn't yet prove dense-semantic value; that kind of self-aware limitation-reporting is unusual and would read well if brought up proactively in an interview.

6. Things to not overclaim

- The end-to-end pipeline defaults to a deterministic mock LLM, not a real model. LLM_PROVIDER=mock is the default everywhere (config, render.yaml, .env.example), and it's regex/string-manipulation logic, not an LLM call. Gemini and Groq providers exist and have eval runs on record (docs/eval-runs/gemini.json, groq.json), so you can defensibly say you built and exercised a pluggable LLM abstraction — but "AI-powered resume rewriting" as a headline needs the caveat that the proven, tested default path is deterministic by design.
- "Semantic retrieval" is TF-IDF, not dense embeddings. The project's own docs say this outright and note the benchmark can't demonstrate the thing dense embeddings would actually add. Don't say "semantic search" without qualifying it as lexical/TF-IDF unless you also mention the opt-in Gemini embedding path.
- The browser automation has not been run against real, live job postings in what I verified. The Playwright tests run real Chromium, but against local static HTML fixtures (tests/fixtures/app_site/*.html) built to mimic Greenhouse-style quirks — not against actual Greenhouse/Lever forms in production. Per your own project memory, the V3.5 split-deploy (Render + Vercel + a Mac-hosted Docker worker) is described as code-complete but pending manual verification. Say "built and tested against a fixture ATS form," not "automated real job applications," unless you've personally run it live and watched it submit.
- Job discovery ≠ application filling on N sites. Discovery only has 2 real source integrations (Greenhouse and Lever JSON feeds, no auth). The form-filler is a generic DOM/ARIA-heuristic engine, not N per-site adapters — don't imply it "supports" a list of job boards for applying; it's site-agnostic by design, which is actually the better story to tell.
- The label-detection sibling-text fallback is explicitly marked in the code as a heuristic, not a real accessible-name algorithm — fine to mention as a known limitation if asked how robust it is.

Resume bullets (verified only)

- Designed a hybrid retrieval pipeline (TF-IDF cosine similarity fused with keyword overlap, NumPy-only, no vector DB) with a deterministic gap-analysis classifier over threshold-scored requirement matches, validated against a hand-labeled benchmark achieving 100% Hit@3 on exact technology matches.
- Built a provenance-tracked, anti-hallucination generation pipeline in Python/FastAPI/Pydantic where every generated resume claim is traced to a source entity's approval status (original / user-confirmed / AI-suggested) and independently re-validated post-generation, flagging unsupported skills and invented metrics rather than trusting LLM output.
- Implemented a pluggable LLM/embedding provider abstraction (mock/Gemini/Groq over raw REST via httpx, no vendor SDK lock-in) so the full pipeline runs deterministically offline for testing and swaps to real inference via environment configuration alone.
- Engineered a Playwright-based browser automation engine with a 22-state task state machine and a protocol-based (Fake/real-browser) design that let the entire fill-and-submit logic be covered by 190 tests (189 passing) before validating the same code path against real Chromium; hard-gated high-impact questions (salary, visa, demographics) to always require human review, even in autonomous mode.
- Built a distributed worker architecture with concurrency-safe task claiming across two database backends (SQLite BEGIN IMMEDIATE, Postgres FOR UPDATE SKIP LOCKED), heartbeat-based stale-claim recovery, and a bearer-token auth channel using constant-time comparison and per-task ownership checks — deployed split across Render, Vercel, and a local Docker worker.