"""Application batches (§23-§25). The batch maximum is a HARD ceiling enforced at
selection time — a trust-boundary invariant, never auto-backfilled (§24). Selecting an
opportunity into a batch shortlists it; deselecting returns it to ANALYZED."""
from __future__ import annotations

from .. import db
from ..models import ApplicationBatch, BatchStatus, OpportunityStatus


class BatchLimitExceeded(ValueError):
    """Raised when a selection would exceed the batch's max_opportunities."""


_SELECTABLE = {OpportunityStatus.DISCOVERED, OpportunityStatus.FILTERED,
               OpportunityStatus.ANALYZED, OpportunityStatus.SHORTLISTED}


def create_batch(candidate_id: int, name: str, max_opportunities: int,
                 target_roles: list[str] | None = None,
                 filters: dict | None = None) -> ApplicationBatch:
    if max_opportunities < 1:
        raise ValueError("max_opportunities must be >= 1")
    batch = ApplicationBatch(
        candidate_id=candidate_id, name=name or f"Batch {max_opportunities}",
        max_opportunities=max_opportunities, target_roles=target_roles or [],
        filters=filters or {})
    batch.id = db.insert_batch(batch)
    return batch


def set_selection(batch_id: int, opportunity_ids: list[int]) -> ApplicationBatch:
    """Set the batch's selected opportunities. Rejects a selection larger than the batch
    maximum (§24). Idempotent: pass the full desired selection each call."""
    batch = db.get_batch(batch_id)
    if batch is None:
        raise KeyError(f"unknown batch {batch_id}")

    ids = list(dict.fromkeys(opportunity_ids))  # de-dup, preserve order
    if len(ids) > batch.max_opportunities:
        raise BatchLimitExceeded(
            f"selected {len(ids)} exceeds batch maximum of {batch.max_opportunities}")

    for oid in ids:
        opp = db.get_opportunity(oid)
        if opp is None or opp.candidate_id != batch.candidate_id:
            raise KeyError(f"opportunity {oid} not found for this candidate")

    prev, now = set(batch.opportunity_ids), set(ids)
    for oid in prev - now:                       # deselected → back to ANALYZED
        opp = db.get_opportunity(oid)
        if opp and opp.status == OpportunityStatus.SHORTLISTED:
            opp.status = OpportunityStatus.ANALYZED
            db.save_opportunity(opp)
    for oid in now:                              # selected → SHORTLISTED
        opp = db.get_opportunity(oid)
        if opp and opp.status in _SELECTABLE and opp.status != OpportunityStatus.SHORTLISTED:
            opp.status = OpportunityStatus.SHORTLISTED
            db.save_opportunity(opp)

    batch.opportunity_ids = ids
    db.save_batch(batch)
    return batch
