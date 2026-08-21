"""Evidence matching + gap analysis. Classification is deterministic (CLAUDE.md §9):
retrieval scores + exact skill presence drive the buckets, not an LLM guess."""
from __future__ import annotations

from .models import (
    GapItem,
    JDRequirements,
    KBEntity,
    MatchStatus,
    RequirementMatch,
)
from .retrieval import RetrievalIndex
from .text_utils import extract_skills, normalize_skill

# Fused-score thresholds. Tunable; kept as named constants, not magic numbers.
STRONG = 0.45
PARTIAL = 0.22
WEAK = 0.10


def candidate_skill_set(entities: list[KBEntity]) -> set[str]:
    """Every skill/technology the candidate has *supported* evidence for."""
    skills: set[str] = set()
    for e in entities:
        skills.update(extract_skills(e.content))
        skills.add(normalize_skill(e.name))
    return skills


def _classify(requirement: str, kind: str, best: float,
              exact: bool) -> tuple[MatchStatus, str]:
    if exact:
        return MatchStatus.STRONG_MATCH, "Directly present in the candidate profile."
    if best >= STRONG:
        return MatchStatus.STRONG_MATCH, "Strong evidence found in candidate experience."
    if best >= PARTIAL:
        return (MatchStatus.PARTIAL_MATCH,
                "Related experience found, but not an exact match to the requirement.")
    if best >= WEAK:
        if kind in ("required", "preferred", "technology"):
            return (MatchStatus.USER_CONFIRMATION_REQUIRED,
                    "Loosely related experience exists; ask the candidate whether this "
                    "specifically applies before claiming it.")
        return MatchStatus.WEAK_MATCH, "Only weakly related experience found."
    return MatchStatus.MISSING, "No supporting evidence in the current profile."


def match_requirements(index: RetrievalIndex, requirements: JDRequirements,
                       skill_set: set[str]) -> list[RequirementMatch]:
    matches: list[RequirementMatch] = []
    jobs: list[tuple[str, str]] = (
        [(s, "required") for s in requirements.required_skills]
        + [(s, "preferred") for s in requirements.preferred_skills]
        + [(r, "responsibility") for r in requirements.responsibilities]
    )
    seen: set[tuple[str, str]] = set()
    for req, kind in jobs:
        key = (normalize_skill(req), kind)
        if not req.strip() or key in seen:
            continue
        seen.add(key)

        scored = index.search(req, top_k=3)
        best = scored[0].score if scored else 0.0
        exact = kind != "responsibility" and normalize_skill(req) in skill_set
        status, reason = _classify(req, kind, best, exact)

        evidence = [s.to_evidence() for s in scored
                    if s.score >= WEAK] if status != MatchStatus.MISSING else []
        matches.append(RequirementMatch(
            requirement=req, kind=kind, match_status=status,
            score=round(best, 4), evidence=evidence, reason=reason))
    return matches


_ACTIONS = {
    MatchStatus.PARTIAL_MATCH: "Reframe existing evidence to foreground this requirement.",
    MatchStatus.WEAK_MATCH: "Strengthen or add supporting detail if applicable.",
    MatchStatus.USER_CONFIRMATION_REQUIRED:
        "Ask the candidate to confirm whether this applies before including it.",
    MatchStatus.MISSING:
        "No evidence — do not fabricate. Flag as a genuine gap or ask the candidate.",
}


def analyze_gaps(matches: list[RequirementMatch]) -> list[GapItem]:
    """Gaps = everything that isn't already a strong match."""
    gaps: list[GapItem] = []
    for m in matches:
        if m.match_status == MatchStatus.STRONG_MATCH:
            continue
        gaps.append(GapItem(
            requirement=m.requirement, kind=m.kind, category=m.match_status,
            reason=m.reason, suggested_action=_ACTIONS.get(m.match_status, "")))
    return gaps
