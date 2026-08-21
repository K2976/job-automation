# ADR-003: LLM provider abstraction with a deterministic mock default

**Status:** Accepted

## Context
The system must not couple business logic to Gemini or Groq, and must be developable and
testable with no API keys.

## Decision
Define `LLMProvider` (`providers/llm.py`) with domain operations — `analyze_jd`,
`parse_resume`, `rewrite`, `compose_summary`. Three implementations:

- **`MockLLMProvider`** (default): deterministic, offline. Computes JD analysis and resume
  parsing from a shared skill lexicon; produces templated prose.
- **`GeminiLLMProvider`**, **`GroqLLMProvider`**: REST via `httpx` (no vendor SDKs). They
  implement one low-level `_complete`; the base class renders versioned prompts
  (`prompts.py`) and validates JSON into Pydantic schemas.

Selected by `LLM_PROVIDER`.

## Rationale
- The mock is **load-bearing**, not a throwaway: it makes the whole pipeline runnable and
  unit-testable offline, and it keeps the deterministic/LLM split honest.
- Concrete domain methods (vs a generic prompt router) are clearer for a fixed V1 pipeline.

## Consequences
- Adding an LLM task means adding a method to the interface — acceptable for a fixed
  pipeline. Adding a *provider* means one new file implementing `_complete`.
