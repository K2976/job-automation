"""The browser abstraction that decouples the automation engine from Playwright (§1, §3).

`BrowserPage` is the whole surface the runner needs; the intelligence never imports
Playwright. `PlaywrightPage` (real driver) and `FakePage` (in-memory, for browser-free
tests) both satisfy it. Field handles (`FieldDescriptor.key`) are OPAQUE, driver-minted
ids — never CSS selectors or indices — so multi-page re-inspection stays robust (§4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..models import FieldType

# Control kinds the runner asks the page to locate, most-specific first.
SUBMIT = "submit"
CONTINUE = "continue"


@dataclass
class FieldDescriptor:
    key: str                       # opaque handle the driver understands
    label: str = ""
    name: str = ""
    field_type: FieldType = FieldType.text
    required: bool = False
    options: list[str] = field(default_factory=list)


@runtime_checkable
class BrowserPage(Protocol):
    def goto(self, url: str) -> None: ...
    def inspect(self) -> list[FieldDescriptor]: ...
    def fill(self, key: str, value: str) -> None: ...
    def select(self, key: str, value: str) -> None: ...
    def check(self, key: str, checked: bool) -> None: ...
    def upload(self, key: str, path: str) -> None: ...
    def click(self, key: str) -> None: ...
    def page_text(self) -> str: ...
    def captcha_present(self) -> bool: ...
    def login_required(self) -> bool: ...
    def find_control(self, kinds: list[str]) -> str | None: ...


# --------------------------------------------------------------------------- #
# FakePage — deterministic, in-memory, no browser. Drives every engine test.   #
# --------------------------------------------------------------------------- #
@dataclass
class _FakeControl:
    kind: str          # SUBMIT | CONTINUE
    key: str


@dataclass
class _FakeScreen:
    fields: list[dict]
    control: str = SUBMIT            # SUBMIT | CONTINUE
    confirmation: str = ""           # page text shown after a submit click
    captcha: bool = False
    login: bool = False
    text: str = ""


class FakePage:
    """An in-memory multi-page form. Construct with a list of screen dicts:

        FakePage([
            {"fields": [{"label": "Email", "name": "email", "type": "email",
                         "required": True}], "control": "continue"},
            {"fields": [...], "control": "submit", "confirmation": "Application submitted"},
        ])
    """

    def __init__(self, screens: list[dict]):
        self.screens = [_FakeScreen(**s) for s in screens]
        self.idx = 0
        self.submitted = False
        self.values: dict[str, str] = {}
        self.uploads: dict[str, str] = {}
        self._keys: dict[str, dict] = {}   # key → field dict on the current screen

    # navigation ---------------------------------------------------------------
    def goto(self, url: str) -> None:
        self.idx = 0
        self.submitted = False

    @property
    def _screen(self) -> _FakeScreen:
        return self.screens[self.idx]

    # inspection ---------------------------------------------------------------
    def inspect(self) -> list[FieldDescriptor]:
        self._keys = {}
        out: list[FieldDescriptor] = []
        for i, f in enumerate(self._screen.fields):
            key = f"s{self.idx}-f{i}"          # opaque, screen-scoped
            self._keys[key] = f
            out.append(FieldDescriptor(
                key=key, label=f.get("label", ""), name=f.get("name", ""),
                field_type=FieldType(f.get("type", "text")),
                required=f.get("required", False), options=f.get("options", []) or []))
        return out

    # actions ------------------------------------------------------------------
    def fill(self, key: str, value: str) -> None:
        self.values[key] = value

    def select(self, key: str, value: str) -> None:
        self.values[key] = value

    def check(self, key: str, checked: bool) -> None:
        self.values[key] = "on" if checked else ""

    def upload(self, key: str, path: str) -> None:
        self.uploads[key] = path

    def click(self, key: str) -> None:
        if key == f"__{SUBMIT}__":
            self.submitted = True
        elif key == f"__{CONTINUE}__" and self.idx < len(self.screens) - 1:
            self.idx += 1

    # observation --------------------------------------------------------------
    def page_text(self) -> str:
        if self.submitted:
            return self._screen.confirmation or "submitted"
        return self._screen.text

    def captcha_present(self) -> bool:
        return self._screen.captcha

    def login_required(self) -> bool:
        return self._screen.login

    def find_control(self, kinds: list[str]) -> str | None:
        if self._screen.control in kinds:
            return f"__{self._screen.control}__"
        return None
