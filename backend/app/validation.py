"""Post-generation claim validation (CLAUDE.md §22). Every skill/tech claim in the
generated resume is traced back to evidence. Unsupported claims are flagged — never
allowed to pass silently as verified candidate information."""
from __future__ import annotations

import re

from .models import (
    Claim,
    ClaimStatus,
    KBEntity,
    Status,
    TailoredResume,
    ValidationReport,
)
from .text_utils import extract_skills, tokenize

# Which claim status a supporting entity's provenance implies.
_STATUS_TO_CLAIM = {
    Status.ORIGINAL: ClaimStatus.SUPPORTED_BY_ORIGINAL,
    Status.USER_CONFIRMED: ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION,
    Status.USER_EDITED: ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION,
    Status.AI_SUGGESTED: ClaimStatus.AI_SUGGESTED_NOT_APPROVED,
}
# Higher = more concerning; a claim takes the worst status among its skills.
_SEVERITY = {
    ClaimStatus.SUPPORTED_BY_ORIGINAL: 0,
    ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION: 1,
    ClaimStatus.AI_SUGGESTED_NOT_APPROVED: 2,
    ClaimStatus.UNSUPPORTED: 3,
}


def _skill_support(entities: list[KBEntity]) -> dict[str, ClaimStatus]:
    """Best (most authoritative) provenance backing each skill the candidate has."""
    support: dict[str, ClaimStatus] = {}
    for e in entities:
        if e.status == Status.REJECTED:
            continue
        claim_status = _STATUS_TO_CLAIM.get(e.status, ClaimStatus.AI_SUGGESTED_NOT_APPROVED)
        for skill in extract_skills(e.content) + [e.name.lower()]:
            cur = support.get(skill)
            if cur is None or _SEVERITY[claim_status] < _SEVERITY[cur]:
                support[skill] = claim_status
    return support


def _evidence_tokens(entities: list[KBEntity]) -> set[str]:
    toks: set[str] = set()
    for e in entities:
        if e.status != Status.REJECTED:
            toks.update(tokenize(e.content))
    return toks


def _classify(text: str, support: dict[str, ClaimStatus],
              baseline: ClaimStatus) -> tuple[ClaimStatus, str]:
    skills = extract_skills(text)
    if not skills:
        return baseline, "No specific skill claim; backed by linked evidence."
    # A claim takes the worst provenance among the skills it names. Baseline (the linked
    # evidence entity) is only a fallback for skill-less text — a rewrite that introduces
    # an unsupported skill must still be flagged even if its source entity is ORIGINAL.
    worst, worst_skill = ClaimStatus.SUPPORTED_BY_ORIGINAL, ""
    for sk in skills:
        st = support.get(sk, ClaimStatus.UNSUPPORTED)
        if _SEVERITY[st] > _SEVERITY[worst]:
            worst, worst_skill = st, sk
    if worst == ClaimStatus.UNSUPPORTED:
        return worst, f"'{worst_skill}' has no supporting evidence in the profile."
    if worst == ClaimStatus.AI_SUGGESTED_NOT_APPROVED:
        return worst, f"'{worst_skill}' is only an unapproved AI suggestion."
    if worst == ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION:
        return worst, f"'{worst_skill}' backed by candidate confirmation."
    return ClaimStatus.SUPPORTED_BY_ORIGINAL, "Backed by original profile evidence."


def validate_resume(resume: TailoredResume, entities: list[KBEntity]) -> ValidationReport:
    support = _skill_support(entities)
    ev_tokens = _evidence_tokens(entities)
    by_id = {e.id: e for e in entities}
    claims: list[Claim] = []

    # skills line
    for sk in resume.skills:
        status, reason = _classify(sk, support, ClaimStatus.UNSUPPORTED)
        claims.append(Claim(text=f"Skill: {sk}", status=status, reason=reason))

    # bullets — baseline from the linked evidence entity's provenance
    for sec in resume.sections:
        for b in sec.bullets:
            ent = by_id.get(b.evidence_entity_id)
            baseline = _STATUS_TO_CLAIM.get(ent.status if ent else None,
                                            ClaimStatus.UNSUPPORTED)
            status, reason = _classify(b.text, support, baseline)
            claims.append(Claim(text=b.text[:160], status=status,
                                evidence_entity_id=b.evidence_entity_id, reason=reason))

    # invented-metric check: numbers in the summary not present in any evidence
    for num in re.findall(r"\b\d+(?:\.\d+)?%?\b", resume.summary):
        if num.rstrip("%") not in ev_tokens and num not in ev_tokens:
            claims.append(Claim(text=f"Summary metric '{num}'",
                                status=ClaimStatus.UNSUPPORTED,
                                reason="Numeric claim not found in candidate evidence."))

    supported = sum(1 for c in claims if c.status in (
        ClaimStatus.SUPPORTED_BY_ORIGINAL, ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION))
    unsupported = sum(1 for c in claims if c.status == ClaimStatus.UNSUPPORTED)
    needs_approval = sum(1 for c in claims
                         if c.status == ClaimStatus.AI_SUGGESTED_NOT_APPROVED)
    return ValidationReport(claims=claims, supported=supported,
                            unsupported=unsupported, needs_approval=needs_approval)
