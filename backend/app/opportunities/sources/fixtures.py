"""Offline fixture source — the FixtureSource is to discovery what MockLLM is to the V1
pipeline: it makes the whole flow runnable and testable with zero network access, and is
the default-enabled source so the V2 flow is demonstrable end-to-end offline.

Reads data/fixtures/opportunities/*.json (each file = a list of raw opportunity dicts)."""
from __future__ import annotations

import json

from ...config import REPO_ROOT
from ...models import SearchPreferences
from .base import OpportunitySource, RawOpportunity

FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "opportunities"


class FixtureSource(OpportunitySource):
    name = "fixtures"

    def __init__(self, directory=None):
        self.directory = directory or FIXTURE_DIR

    def discover(self, prefs: SearchPreferences) -> list[RawOpportunity]:
        out: list[RawOpportunity] = []
        for path in sorted(self.directory.glob("*.json")):
            records = json.loads(path.read_text())
            if isinstance(records, dict):
                records = [records]
            for i, r in enumerate(records):
                out.append(RawOpportunity(
                    source=self.name,
                    source_id=r.get("source_id") or f"{path.stem}-{i}",
                    company=r.get("company", ""),
                    title=r.get("title", ""),
                    location=r.get("location", ""),
                    work_mode=r.get("work_mode", ""),
                    employment_type=r.get("employment_type", ""),
                    salary=r.get("salary", ""),
                    description=r.get("description", ""),
                    source_url=r.get("source_url", ""),
                    application_url=r.get("application_url", ""),
                ))
        return out
