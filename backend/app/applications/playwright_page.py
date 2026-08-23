"""PlaywrightPage — the real BrowserPage driver. Satisfies the exact protocol FakePage
does, so the engine is unchanged. Playwright is imported lazily (methods/factory only), so
importing this module never requires the package or a browser — the API service can import
it without Chromium installed.

Driver rules (see docs/browser-agent.md):
- All waiting lives in `click()` (the sync runner can't await); after a control click we
  wait for the page to settle, so the next `inspect()`/`page_text()` reads the new DOM.
- `inspect()` and `find_control()` mint OPAQUE keys into an id→locator map; the engine only
  ever passes those keys back. No CSS selectors or indices cross the protocol boundary.
- CAPTCHA markers are shared with V2 discovery (§23) — one list, not two."""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any

from ..models import FieldType
from ..opportunities.sources._http import _CAPTCHA_MARKERS
from .page import CONTINUE, FieldDescriptor, SUBMIT

_LOGIN_MARKERS = ("please log in", "please sign in", "log in to continue",
                  "sign in to continue", "log in to apply", "sign in to apply",
                  "login required")

_CONTROL_PATTERNS = {
    # NOTE: no inline (?i) — Playwright compiles these to JS regex, which rejects it;
    # pass the flag via re.I so it maps to the JS `i` flag.
    SUBMIT: re.compile(r"\b(submit|apply|send application|send|finish|complete)\b", re.I),
    CONTINUE: re.compile(r"\b(next|continue|proceed|save and continue)\b", re.I),
}

# input types that are controls/hidden, not fillable questions.
_SKIP_INPUT_TYPES = {"submit", "button", "reset", "image", "hidden"}

# JS that reads a field's accessible label from every reasonable source (§19).
_DESCRIBE = """
el => {
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute('type') || '').toLowerCase();
  let label = el.getAttribute('aria-label') || '';
  if (!label && el.id) { const l = document.querySelector('label[for="' + el.id + '"]'); if (l) label = l.innerText; }
  if (!label) { const p = el.closest('label'); if (p) label = p.innerText; }
  if (!label) label = el.getAttribute('placeholder') || '';
  const options = tag === 'select' ? Array.from(el.options).map(o => o.textContent.trim()) : [];
  return { tag, type, label: (label || '').trim(), name: el.getAttribute('name') || '',
           required: !!el.required || el.getAttribute('aria-required') === 'true', options };
}
"""


def _field_type(tag: str, type_attr: str) -> FieldType:
    if tag == "textarea":
        return FieldType.textarea
    if tag == "select":
        return FieldType.select
    try:
        return FieldType(type_attr)
    except ValueError:
        return FieldType.text


class PlaywrightPage:
    def __init__(self, page: Any):
        self.page = page
        self._map: dict[str, Any] = {}
        self._n = 0

    def _key(self, obj: Any) -> str:
        k = f"h{self._n}"
        self._n += 1
        self._map[k] = obj
        return k

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="load")

    def inspect(self) -> list[FieldDescriptor]:
        self._map = {}
        out: list[FieldDescriptor] = []
        for handle in self.page.query_selector_all("input, textarea, select"):
            d = handle.evaluate(_DESCRIBE)
            if d["tag"] == "input" and d["type"] in _SKIP_INPUT_TYPES:
                continue
            out.append(FieldDescriptor(
                key=self._key(handle), label=d["label"], name=d["name"],
                field_type=_field_type(d["tag"], d["type"]),
                required=d["required"], options=d["options"]))
        return out

    def fill(self, key: str, value: str) -> None:
        self._map[key].fill(value)

    def select(self, key: str, value: str) -> None:
        try:
            self._map[key].select_option(label=value)
        except Exception:
            self._map[key].select_option(value)

    def check(self, key: str, checked: bool) -> None:
        (self._map[key].check if checked else self._map[key].uncheck)()

    def upload(self, key: str, path: str) -> None:
        self._map[key].set_input_files(path)

    def click(self, key: str) -> None:
        self._map[key].click()
        # All waiting is here: let navigation / in-page updates settle before the runner
        # re-inspects or reads confirmation text.
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass

    def page_text(self) -> str:
        try:
            return self.page.inner_text("body")
        except Exception:
            return ""

    def captcha_present(self) -> bool:
        low = self.page_text()[:4000].lower()
        return any(m in low for m in _CAPTCHA_MARKERS)

    def login_required(self) -> bool:
        low = self.page_text()[:4000].lower()
        return any(m in low for m in _LOGIN_MARKERS)

    def find_control(self, kinds: list[str]) -> str | None:
        for kind in kinds:
            loc = self.page.get_by_role("button", name=_CONTROL_PATTERNS[kind])
            try:
                if loc.count():
                    return self._key(loc.first)
            except Exception:
                continue
        return None


@contextmanager
def playwright_session(headless: bool = True):
    """Yield a PlaywrightPage in a fresh, isolated browser context (§6) — no cookies shared
    between applications. Chromium is launched per session; the caller runs one task."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            yield PlaywrightPage(page)
        finally:
            context.close()
            browser.close()
