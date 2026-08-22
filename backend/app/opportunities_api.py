"""V2 HTTP surface — opportunity discovery, results, batches, tracking, sources. Thin,
like the V1 api.py: validate, call an opportunities.* function, return a Pydantic model.
Discovery is started as a BackgroundTask and polled, so no HTTP request is held open for
a long-running crawl (§41)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from . import db
from .config import settings
from .models import (
    ApplicationBatch,
    DiscoveryRun,
    Opportunity,
    OpportunityStatus,
    SearchPreferences,
)
from .opportunities import batches, discovery, packages, processing
from .opportunities.sources import get_enabled_sources
from .providers.llm import LLMError

router = APIRouter(prefix="/api", tags=["opportunities"])


def _candidate_or_404(candidate_id: int) -> None:
    if db.get_candidate(candidate_id) is None:
        raise HTTPException(404, "candidate not found")


# ------------------------------------------------------------- preferences #
@router.get("/candidates/{candidate_id}/preferences")
def get_preferences(candidate_id: int) -> SearchPreferences:
    _candidate_or_404(candidate_id)
    return db.get_preferences(candidate_id)


@router.put("/candidates/{candidate_id}/preferences")
def put_preferences(candidate_id: int, prefs: SearchPreferences) -> SearchPreferences:
    _candidate_or_404(candidate_id)
    prefs.candidate_id = candidate_id
    db.save_preferences(prefs)
    return prefs


# --------------------------------------------------------------- discovery #
@router.post("/candidates/{candidate_id}/discovery/runs")
def start_discovery(candidate_id: int, prefs: SearchPreferences,
                    background: BackgroundTasks) -> dict:
    """Kick off a discovery run in the background; poll GET /discovery/runs/{id}."""
    _candidate_or_404(candidate_id)
    run_id = discovery.start_run(candidate_id, prefs)
    background.add_task(discovery.execute_run, run_id)
    return {"run_id": run_id, "status": "RUNNING"}


@router.get("/discovery/runs/{run_id}")
def get_run(run_id: int) -> DiscoveryRun:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run


# ------------------------------------------------------------ opportunities #
@router.get("/candidates/{candidate_id}/opportunities")
def list_opportunities(candidate_id: int, status: str | None = None) -> dict:
    _candidate_or_404(candidate_id)
    statuses = [status] if status else None
    opps = db.list_opportunities(candidate_id, statuses=statuses)
    opps.sort(key=lambda o: o.opportunity_score, reverse=True)
    return {"opportunities": opps}


@router.get("/opportunities/{opp_id}")
def get_opportunity(opp_id: int) -> dict:
    opp = db.get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")
    return {"opportunity": opp, "why_apply": processing.why_apply(opp)}


class StatusIn(BaseModel):
    status: OpportunityStatus


@router.post("/opportunities/{opp_id}/status")
def set_status(opp_id: int, body: StatusIn) -> Opportunity:
    """Manual tracker transition (§28) — including APPLIED, which V2 only ever sets here."""
    opp = db.get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")
    opp.status = body.status
    db.save_opportunity(opp)
    return opp


@router.get("/opportunities/{opp_id}/cover-letter")
def get_cover_letter(opp_id: int) -> dict:
    opp = db.get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")
    return {"cover_letter": opp.cover_letter}


# ------------------------------------------------------------------ batches #
class BatchIn(BaseModel):
    name: str = ""
    max_opportunities: int = 10
    target_roles: list[str] = []


class SelectionIn(BaseModel):
    opportunity_ids: list[int]


@router.post("/candidates/{candidate_id}/batches")
def create_batch(candidate_id: int, body: BatchIn) -> ApplicationBatch:
    _candidate_or_404(candidate_id)
    try:
        return batches.create_batch(candidate_id, body.name, body.max_opportunities,
                                    body.target_roles)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/candidates/{candidate_id}/batches")
def list_batches(candidate_id: int) -> dict:
    _candidate_or_404(candidate_id)
    return {"batches": db.list_batches(candidate_id)}


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int) -> ApplicationBatch:
    batch = db.get_batch(batch_id)
    if batch is None:
        raise HTTPException(404, "batch not found")
    return batch


@router.post("/batches/{batch_id}/selection")
def set_selection(batch_id: int, body: SelectionIn) -> ApplicationBatch:
    try:
        return batches.set_selection(batch_id, body.opportunity_ids)
    except batches.BatchLimitExceeded as e:
        raise HTTPException(409, str(e))       # over the hard maximum (§24)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/batches/{batch_id}/prepare")
def prepare_batch(batch_id: int) -> dict:
    if db.get_batch(batch_id) is None:
        raise HTTPException(404, "batch not found")
    try:
        return packages.prepare_batch(batch_id)
    except LLMError as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------------ sources #
@router.get("/candidates/{candidate_id}/sources")
def source_health(candidate_id: int) -> dict:
    """Configured sources merged with the latest run's health (§29) — reported, not
    re-probed, so a blocked source is never hammered just to render this panel."""
    _candidate_or_404(candidate_id)
    enabled = {s.name for s in get_enabled_sources()}
    runs = [r for r in _recent_runs(candidate_id)]
    latest_health: dict[str, dict] = {}
    for run in runs:
        for h in run.source_health:
            latest_health.setdefault(h.source, {"status": h.status.value,
                                                "detail": h.detail, "discovered": h.discovered})
    names = sorted(enabled | set(latest_health) | set(settings.opportunity_source_list))
    return {"sources": [
        {"name": n, "configured": n in enabled,
         **latest_health.get(n, {"status": "UNKNOWN", "detail": "", "discovered": 0})}
        for n in names]}


def _recent_runs(candidate_id: int, limit: int = 5) -> list[DiscoveryRun]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM discovery_run WHERE candidate_id=? ORDER BY id DESC LIMIT ?",
            (candidate_id, limit)).fetchall()
    return [db.get_run(r["id"]) for r in rows]
