# LLM strategy

## Abstraction
`LLMProvider` (`providers/llm.py`) exposes domain operations, not raw prompting:
`analyze_jd`, `parse_resume`, `rewrite`, `compose_summary`. Business logic depends only on
this interface — see [ADR-003](decisions/ADR-003-llm-provider-abstraction.md).

## Providers
| `LLM_PROVIDER` | Impl | Notes |
|---|---|---|
| `mock` (default) | `MockLLMProvider` | deterministic, offline, keyless |
| `gemini` | `GeminiLLMProvider` | REST via httpx, `gemini-1.5-flash` default |
| `groq` | `GroqLLMProvider` | OpenAI-compatible REST, `llama-3.3-70b-versatile` default |

Real providers implement one `_complete`; the base renders versioned prompts
(`prompts.py`) and validates JSON into Pydantic (`_parse_json` strips fences, extracts the
object, `model_validate_json`). Model names come from env/defaults — never hardcoded in
business logic.

## What the LLM is (and isn't) used for
Used for: JD → structured requirements, résumé text → structured profile, prose (project
rewrites, summary). **Not** used for: scoring, classification, provenance, validation, ATS
math, diffing — those are deterministic (CLAUDE.md §9). This split is the reason the system
is testable and its scores are stable across providers.

## Structured output
Anything consumed programmatically goes `LLM → JSON → Pydantic validate → logic`. On
malformed output, `_parse_json` raises `LLMError` (→ HTTP 502) rather than corrupting data.

## The mock, specifically
`MockLLMProvider` computes JD analysis and résumé parsing from the shared skill lexicon
(`text_utils.py`) — required/preferred split via section cues, responsibilities via action
verbs (prose lead-ins filtered), skills via `extract_skills`. Prose ops return grounded
templates. It's a genuine deterministic stand-in, not a stub.

## Reliability
`providers/_http.py` wraps live calls with a per-request timeout (`LLM_TIMEOUT`) and
bounded retry with backoff on 429/5xx/timeouts (`LLM_MAX_RETRIES`, honours `Retry-After`).
Errors never leak the API key. Gemini auth is swappable (`GEMINI_AUTH=query|bearer`) so an
unusual key format is config, not code, and empty-candidate/safety-block responses raise a
clear `LLMError`.

## Cost / fallback
At V1 scale each analysis is a handful of calls. Gemini embeddings are cached in SQLite to
avoid re-embedding identical text. Provider free-tier limits are assumed non-permanent;
switching providers is one env var. Live JD analysis returns messier, free-form skill
strings than the mock's canonical forms — the deterministic downstream tolerates this
(some exact matches soften to semantic matches); quality tuning is a later phase.
