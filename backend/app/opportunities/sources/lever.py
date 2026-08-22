"""Lever public Postings API (§5). No auth. One call per company:
    GET https://api.lever.co/v0/postings/{company}?mode=json
Returns a flat list of postings with plain-text descriptions. Configure company slugs
via LEVER_BOARDS."""
from __future__ import annotations

import time

from ...models import SearchPreferences
from .base import OpportunitySource, RawOpportunity, SourceError
from ._http import get_json

_API = "https://api.lever.co/v0/postings/{company}"


class LeverSource(OpportunitySource):
    name = "lever"

    def __init__(self, boards: list[str]):
        self.boards = boards

    def discover(self, prefs: SearchPreferences) -> list[RawOpportunity]:
        out: list[RawOpportunity] = []
        last_error: SourceError | None = None
        for i, company in enumerate(self.boards):
            if i:
                time.sleep(0.5)
            try:
                postings = get_json(_API.format(company=company), params={"mode": "json"})
            except SourceError as e:
                last_error = e
                continue
            if not isinstance(postings, list):
                continue
            for p in postings:
                cats = p.get("categories") or {}
                url = p.get("hostedUrl", "")
                out.append(RawOpportunity(
                    source=self.name, source_id=f"{company}:{p.get('id')}",
                    company=company.replace("-", " ").title(),
                    title=p.get("text", ""), location=cats.get("location", ""),
                    work_mode=(p.get("workplaceType") or "").lower(),
                    employment_type=cats.get("commitment", ""),
                    description=p.get("descriptionPlain") or p.get("description", ""),
                    source_url=url, application_url=p.get("applyUrl") or url))
        if last_error and not out:
            raise last_error
        return out
