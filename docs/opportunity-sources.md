# Opportunity Sources (V2)

Sources are modular adapters behind one interface (`opportunities/sources/base.py`). Each
returns the same normalized `RawOpportunity` shape and **isolates its own failures** — a
broken source never aborts a discovery run.

## The contract

```python
class OpportunitySource(ABC):
    name: str
    def discover(self, prefs) -> list[RawOpportunity]: ...   # may raise a Source* error
    def run(self, prefs) -> SourceResult:                    # error-isolated; never raises
```

Adapters implement `discover`. The base `run()` wraps it: on success it returns
`SourceResult(status=AVAILABLE, opportunities=...)`; on a `Source*` exception it maps the
exception to a `SourceStatus` and returns an empty result. The orchestrator only ever calls
`run()`.

## Adapters

| Adapter | Source | Auth | Notes |
|---------|--------|------|-------|
| `FixtureSource` | `data/fixtures/opportunities/*.json` | none | **Default, offline.** The discovery analogue of the mock LLM — makes the whole flow runnable and testable with no network. |
| `GreenhouseSource` | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | none | Official public board API; one call per board returns all postings with descriptions. |
| `LeverSource` | `api.lever.co/v0/postings/{company}?mode=json` | none | Official public postings API; flat list with plain-text descriptions. |

Official structured feeds are preferred over scraping (§5). New adapters register in
`sources/__init__.py::_build` — the orchestrator never names a source directly.

## Configuration

```
OPPORTUNITY_SOURCES=fixtures        # comma-separated: fixtures | greenhouse | lever
GREENHOUSE_BOARDS=                  # comma-separated board tokens (e.g. stripe,figma)
LEVER_BOARDS=                       # comma-separated company slugs
```

An HTTP adapter is only built when its board list is non-empty, so listing `greenhouse` in
`OPPORTUNITY_SOURCES` without any `GREENHOUSE_BOARDS` simply disables it. Board APIs are
**company-scoped**, not a global search — you poll specific boards and filter locally
against preferences.

## Source health (§8)

| Status | Meaning |
|--------|---------|
| `AVAILABLE` | returned results |
| `RATE_LIMITED` | HTTP 429 |
| `BLOCKED` | HTTP 403, no CAPTCHA marker |
| `CAPTCHA` | anti-bot/CAPTCHA challenge detected (403 or in body) |
| `UNREACHABLE` | timeout / DNS / connection error |
| `UNSUPPORTED` | bad board token (401/404) or non-JSON response |
| `ERROR` | anything else |

Each run records one `SourceHealth` per source; `GET /api/candidates/{id}/sources` merges
configured sources with the latest run's health for the Sources panel — it **reports**, it
does not re-probe.

## CAPTCHA / blocked policy (§7, §32)

**The system never attempts to bypass a CAPTCHA or anti-bot protection.** On a challenge,
denial, or repeated failure the source is marked (`CAPTCHA` / `BLOCKED` / etc.), skipped for
that run, and reported. It is not retried within the run. Rate limits use bounded, polite
behaviour: a short delay between boards, a per-source timeout, and no uncontrolled request
loops. The `_http.py` helper inspects response bodies for challenge markers so a `200` page
that is actually a CAPTCHA wall is classified as `CAPTCHA`, not treated as content.

## Testing

`FixtureSource` powers the fully-offline discovery tests. `GreenhouseSource` /
`LeverSource` are tested against mocked HTTP (`tests/test_sources_http.py`) — success,
field mapping, rate-limit, CAPTCHA, malformed, and bad-token paths. The core suite never
touches a live API.
