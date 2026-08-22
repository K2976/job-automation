"""Source registry. `get_enabled_sources()` builds the adapters named in
OPPORTUNITY_SOURCES. New adapters register here — the orchestrator never names a source
directly."""
from __future__ import annotations

from ...config import settings
from .base import (  # re-export the adapter contract
    OpportunitySource,
    RawOpportunity,
    SourceBlocked,
    SourceCaptcha,
    SourceError,
    SourceRateLimited,
    SourceResult,
    SourceUnreachable,
    SourceUnsupported,
)
from .fixtures import FixtureSource


def _build(name: str) -> OpportunitySource | None:
    if name == "fixtures":
        return FixtureSource()
    if name == "greenhouse":
        from .greenhouse import GreenhouseSource
        boards = settings.greenhouse_board_list
        return GreenhouseSource(boards) if boards else None
    if name == "lever":
        from .lever import LeverSource
        boards = settings.lever_board_list
        return LeverSource(boards) if boards else None
    return None


def get_enabled_sources(names: list[str] | None = None) -> list[OpportunitySource]:
    """Adapters to query this run. `names` (from preferences) overrides the config default;
    unknown or unconfigured names are silently dropped."""
    wanted = names or settings.opportunity_source_list
    return [s for s in (_build(n) for n in wanted) if s is not None]


__all__ = [
    "OpportunitySource", "RawOpportunity", "SourceResult", "SourceError",
    "SourceBlocked", "SourceCaptcha", "SourceRateLimited", "SourceUnreachable",
    "SourceUnsupported", "FixtureSource", "get_enabled_sources",
]
