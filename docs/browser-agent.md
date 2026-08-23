# Browser Agent (V3)

The browser agent is decoupled from the intelligence via the `BrowserPage` protocol
(`applications/page.py`). The runner speaks only this protocol; it never imports Playwright.

```python
class BrowserPage(Protocol):
    def goto(url): ...
    def inspect() -> list[FieldDescriptor]: ...      # opaque key per field
    def fill/select/check/upload(key, ...): ...
    def click(key): ...
    def page_text() -> str: ...
    def captcha_present() -> bool: ...
    def login_required() -> bool: ...
    def find_control(kinds) -> str | None: ...        # submit / continue
```

Two implementations satisfy it:

- **`FakePage`** — an in-memory multi-page form. Instant, deterministic, no browser. Drives
  the entire engine test suite.
- **`PlaywrightPage`** — the real driver over a Playwright `Page`, using accessible locators
  (`get_by_label`, `get_by_role`) and reading labels from `<label>`/`aria-label`/
  `placeholder`/`name`.

Both are proven equivalent: `tests/test_application_playwright.py` re-runs the FakePage
scenarios against real Chromium and asserts identical `task.status`.

## Driver rules (why PlaywrightPage is written the way it is)

1. **All waiting lives in `click()`.** The runner is synchronous and cannot `await`.
   `click()` clicks the control and then waits for the page to settle
   (`wait_for_load_state`). Because `click()` is only ever called on a submit/continue
   control, this single point makes multi-page re-inspection read the *new* DOM and
   confirmation detection read the *loaded* confirmation page.
2. **Opaque handles, never selectors.** `inspect()` and `find_control()` mint id→locator
   entries and return the id; the engine passes ids back to `fill/click`. No CSS selector or
   index crosses the protocol boundary, so re-inspection after navigation stays robust.
3. **`find_control` registers its own key.** Controls are not part of `inspect()`'s field
   list, so `find_control` queries by accessible role/name, mints a fresh key, stores the
   locator, and returns it.

## CAPTCHA / anti-bot (§22)

`captcha_present()` scans page text for challenge markers — the **same list V2 discovery
uses** (`opportunities/sources/_http._CAPTCHA_MARKERS`), one source of truth. On a hit the
runner transitions to `BLOCKED`, logs `CAPTCHA_DETECTED`, and stops. The agent never solves,
retries, or otherwise attempts to defeat the challenge. The user may take the application
over manually.

## Isolation (§6)

`playwright_session()` launches Chromium and a **fresh browser context per task**, so no
cookies or state leak between unrelated applications. Nothing sensitive is persisted.

## Sync Playwright in a background task

The worker runs as a FastAPI `BackgroundTask`. Starlette runs sync background tasks in a
threadpool — off the event loop — so the synchronous Playwright API (which refuses to run
inside a running asyncio loop) works without any async plumbing. Tests inject a `FakePage`
factory (`queue.OVERRIDE_FACTORY`) so the API pipeline runs with no browser at all.

## Deployment

`playwright` is a light dependency; the browser binaries (~150MB) are **not** installed in
the API web service — only on the browser worker (`playwright install chromium`). Importing
the app never requires Playwright. See `docs/deployment.md` for the worker constraints.
