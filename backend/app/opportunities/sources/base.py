"""Source adapter contract (§4–§8). Every adapter returns the SAME normalized shape and
isolates its own failures: a broken/blocked/CAPTCHA source must never abort discovery —
it is skipped and reported (§7). Adapters signal *why* they failed by raising one of the
Source* exceptions; the base `run()` maps that to a SourceStatus. Adapters never retry a
CAPTCHA and never attempt to bypass anti-bot protections."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ...models import SearchPreferences, SourceHealth, SourceStatus


@dataclass
class RawOpportunity:
    """What a source yields before normalization/dedup. Free-form; the pipeline cleans it."""
    source: str
    source_id: str
    company: str = ""
    title: str = ""
    location: str = ""
    work_mode: str = ""
    employment_type: str = ""
    salary: str = ""
    description: str = ""
    source_url: str = ""
    application_url: str = ""


@dataclass
class SourceResult:
    source: str
    status: SourceStatus
    opportunities: list[RawOpportunity] = field(default_factory=list)
    detail: str = ""

    def health(self) -> SourceHealth:
        return SourceHealth(source=self.source, status=self.status,
                            discovered=len(self.opportunities), detail=self.detail)


# --- failure signals -------------------------------------------------------- #
class SourceError(Exception):
    status = SourceStatus.ERROR


class SourceBlocked(SourceError):
    status = SourceStatus.BLOCKED


class SourceCaptcha(SourceError):
    status = SourceStatus.CAPTCHA


class SourceUnreachable(SourceError):
    status = SourceStatus.UNREACHABLE


class SourceRateLimited(SourceError):
    status = SourceStatus.RATE_LIMITED


class SourceUnsupported(SourceError):
    status = SourceStatus.UNSUPPORTED


class OpportunitySource(ABC):
    name: str = "base"

    @abstractmethod
    def discover(self, prefs: SearchPreferences) -> list[RawOpportunity]:
        """Fetch raw opportunities. May raise a Source* error to report a skip reason."""

    def run(self, prefs: SearchPreferences) -> SourceResult:
        """Error-isolated entry point used by the orchestrator. Never raises."""
        try:
            opps = self.discover(prefs)
            return SourceResult(self.name, SourceStatus.AVAILABLE, opps)
        except SourceError as e:
            return SourceResult(self.name, e.status, detail=str(e) or e.status.value)
        except Exception as e:  # pragma: no cover - defensive; any adapter bug is isolated
            return SourceResult(self.name, SourceStatus.ERROR, detail=f"{type(e).__name__}: {e}")
