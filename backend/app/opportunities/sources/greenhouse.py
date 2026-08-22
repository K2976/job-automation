"""Greenhouse public Job Board API (§5 — prefer an official structured feed over scraping).
No auth. One call per board returns every posting with its description:
    GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
Configure board tokens via GREENHOUSE_BOARDS. A bad token → UNSUPPORTED (isolated)."""
from __future__ import annotations

import time

from ...models import SearchPreferences
from .base import OpportunitySource, RawOpportunity, SourceError
from ._http import get_json, plain_text

_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseSource(OpportunitySource):
    name = "greenhouse"

    def __init__(self, boards: list[str]):
        self.boards = boards

    def discover(self, prefs: SearchPreferences) -> list[RawOpportunity]:
        out: list[RawOpportunity] = []
        last_error: SourceError | None = None
        for i, token in enumerate(self.boards):
            if i:
                time.sleep(0.5)  # politeness between boards (§32)
            try:
                data = get_json(_API.format(token=token), params={"content": "true"})
            except SourceError as e:
                last_error = e
                continue
            for job in data.get("jobs", []):
                loc = (job.get("location") or {}).get("name", "")
                url = job.get("absolute_url", "")
                out.append(RawOpportunity(
                    source=self.name, source_id=f"{token}:{job.get('id')}",
                    company=token.replace("-", " ").title(),
                    title=job.get("title", ""), location=loc,
                    description=plain_text(job.get("content", "")),
                    source_url=url, application_url=url))
        # Every board failed and nothing came back → surface the specific skip reason.
        if last_error and not out:
            raise last_error
        return out
