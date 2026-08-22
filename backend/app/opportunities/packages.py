"""Application package preparation (§26-§27). Reuses the V1 resume pipeline unchanged —
analyze_job + generate_for_job produce the tailored résumé (and its professional LaTeX
output); packaging never builds a second resume system. Optionally drafts a cover letter
from candidate evidence only. This is where the expensive LLM work happens, and it is
proportional to *selected* opportunities (≤ batch max), not to *analysed* ones."""
from __future__ import annotations

from .. import db, pipeline
from ..models import BatchStatus, Opportunity, OpportunityStatus
from ..providers.llm import LLMProvider, get_llm_provider


def _evidence_text(opp: Opportunity) -> str:
    """Grounding for the cover letter: top real evidence snippets from the match analysis."""
    lines: list[str] = []
    for m in opp.matches:
        for e in m.evidence[:1]:
            lines.append(f"{e.name}: {e.snippet}")
    return "\n".join(dict.fromkeys(lines))[:1200]


def prepare_opportunity(opp: Opportunity, llm: LLMProvider,
                        cover_letter: bool = True) -> dict:
    """Prepare one opportunity's package: tailored résumé (via V1) + optional cover letter.
    Sets job_id and moves the opportunity to READY_TO_APPLY. V2 never sets APPLIED (§28)."""
    if opp.job_id is None:
        result = pipeline.analyze_job(opp.candidate_id, opp.jd_text, llm)
        opp.job_id = result["job_id"]
        opp.requirements = result["requirements"]
        opp.matches = result["matches"]
        opp.gaps = result["gaps"]

    opp.status = OpportunityStatus.TAILORING
    db.save_opportunity(opp)

    gen = pipeline.generate_for_job(opp.job_id, llm)  # persists résumé on the job

    if cover_letter:
        role = (opp.requirements.role if opp.requirements else "") or opp.title
        opp.cover_letter = llm.compose_cover_letter(
            opp.company, role, opp.jd_text, _evidence_text(opp))

    opp.status = OpportunityStatus.READY_TO_APPLY
    db.save_opportunity(opp)
    return {"opportunity_id": opp.id, "job_id": opp.job_id,
            "status": opp.status.value, "has_cover_letter": bool(opp.cover_letter)}


def prepare_batch(batch_id: int, llm: LLMProvider | None = None,
                  cover_letter: bool = True) -> dict:
    """Prepare packages for every selected opportunity in the batch."""
    batch = db.get_batch(batch_id)
    if batch is None:
        raise KeyError(f"unknown batch {batch_id}")
    llm = llm or get_llm_provider()

    prepared = []
    for oid in batch.opportunity_ids:
        opp = db.get_opportunity(oid)
        if opp is None:
            continue
        prepared.append(prepare_opportunity(opp, llm, cover_letter=cover_letter))

    batch.status = BatchStatus.READY
    db.save_batch(batch)
    return {"batch_id": batch_id, "prepared": prepared, "status": batch.status.value}
