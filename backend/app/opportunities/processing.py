"""Deterministic opportunity processing (§12, §14, §15, §18, §31) — NO LLM here.
normalize → dedup → hard filter → cheap match → rank. Each stage is pure and testable;
the orchestrator (discovery.py) sequences them and only then spends LLM calls on the
survivors."""
from __future__ import annotations

import re

from ..models import Opportunity, RequirementMatch, MatchStatus, SearchPreferences
from ..retrieval import RetrievalIndex
from ..text_utils import extract_skills, normalize_skill
from .sources.base import RawOpportunity

# Ranking weights (§18) — configurable product indicator, documented not magic.
_RANK_WEIGHTS = {"jd_match": 0.50, "cheap": 0.20, "role": 0.15, "location": 0.15}
# Obvious-seniority markers used for cheap experience filtering (§14).
_SENIOR_MARKERS = ("senior", "sr.", "staff", "principal", "lead", "manager",
                   "head of", "director", "vp ", "iii", "ii ")
_REMOTE_RE = re.compile(r"\bremote\b", re.I)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _key_part(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# --------------------------------------------------------------- normalize #
def normalize(raw: RawOpportunity, candidate_id: int) -> Opportunity:
    company = _collapse(raw.company)
    title = _collapse(raw.title)
    location = _collapse(raw.location)
    desc = (raw.description or "").strip()

    work_mode = (raw.work_mode or "").strip().lower()
    if not work_mode:
        blob = f"{title} {location} {desc[:400]}"
        if _REMOTE_RE.search(blob):
            work_mode = "remote"
        elif _HYBRID_RE.search(blob):
            work_mode = "hybrid"

    jd_text = f"{title}\n{company} — {location}\n\n{desc}".strip()
    # dedup key keeps seniority (title kept whole) so "Senior X" != "X" (§37).
    dedup_key = "|".join((_key_part(company), _key_part(title), _key_part(location)))

    return Opportunity(
        candidate_id=candidate_id, source=raw.source, source_id=raw.source_id,
        source_url=raw.source_url.strip(),
        application_url=(raw.application_url or raw.source_url).strip(),
        dedup_key=dedup_key, company=company, title=title, location=location,
        work_mode=work_mode, employment_type=_collapse(raw.employment_type).lower(),
        salary=_collapse(raw.salary), description_raw=desc, jd_text=jd_text,
        technologies=extract_skills(f"{title} {desc}"),
    )


# ------------------------------------------------------------------- dedup #
def deduplicate(opps: list[Opportunity]) -> list[Opportunity]:
    """One canonical Opportunity per dedup_key; other sources recorded in source_refs (§12).
    Distinct titles (incl. seniority) stay separate because the key keeps the whole title."""
    canonical: dict[str, Opportunity] = {}
    for opp in opps:
        key = opp.dedup_key
        if key not in canonical:
            canonical[key] = opp
            continue
        c = canonical[key]
        if opp.source not in c.source_refs and opp.source != c.source:
            c.source_refs.append(opp.source)
        if not c.application_url and opp.application_url:
            c.application_url = opp.application_url
    return list(canonical.values())


# ------------------------------------------------------------------ filter #
def _matches_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(_key_part(t) and _key_part(t) in low for t in terms)


def passes_filters(opp: Opportunity, prefs: SearchPreferences) -> tuple[bool, str]:
    """Cheap hard filters (§14). Returns (kept, reason_if_dropped). Unknown fields on the
    opportunity are treated as 'not disqualifying' — we never drop on missing data."""
    title_l = opp.title.lower()

    if prefs.excluded_companies and _matches_any(opp.company, prefs.excluded_companies):
        return False, "excluded company"
    if prefs.excluded_roles and _matches_any(opp.title, prefs.excluded_roles):
        return False, "excluded role"
    if prefs.target_roles and not _matches_any(opp.title, prefs.target_roles):
        return False, "role does not match target roles"

    exp = prefs.experience_level.lower()
    if exp in ("intern", "internship", "entry", "entry level", "entry-level", "junior"):
        if any(m in title_l for m in _SENIOR_MARKERS):
            return False, "seniority above target experience level"

    remote_pref = (prefs.remote_preference or "any").lower()
    if remote_pref == "remote" and opp.work_mode not in ("remote", ""):
        return False, "not remote"
    if remote_pref == "onsite" and opp.work_mode == "remote":
        return False, "remote but onsite preferred"
    if prefs.preferred_locations and opp.work_mode != "remote":
        if opp.location and not _matches_any(opp.location, prefs.preferred_locations):
            return False, "location not in preferred locations"

    if prefs.employment_types and opp.employment_type:
        if not _matches_any(opp.employment_type, prefs.employment_types):
            return False, "employment type not preferred"

    return True, ""


# -------------------------------------------------------------- cheap match #
def cheap_score(opp: Opportunity, index: RetrievalIndex, skill_set: set[str]) -> float:
    """LLM-free relevance (§15): best V1 retrieval hit for the JD + candidate/opp skill
    overlap. Reuses the exact hybrid index V1 uses — no second matching system (§16)."""
    scored = index.search(opp.jd_text, top_k=3)
    retrieval_best = scored[0].score if scored else 0.0
    opp_skills = {normalize_skill(s) for s in opp.technologies}
    overlap = len(opp_skills & skill_set) / len(opp_skills) if opp_skills else 0.0
    return round(0.6 * retrieval_best + 0.4 * overlap, 4)


# ------------------------------------------------------------------- rank #
def _requirement_coverage(matches: list[RequirementMatch]) -> float:
    if not matches:
        return 0.0
    good = sum(1 for m in matches if m.match_status in
               (MatchStatus.STRONG_MATCH, MatchStatus.PARTIAL_MATCH))
    return good / len(matches)


def opportunity_score(opp: Opportunity, prefs: SearchPreferences) -> float:
    """Final deterministic ranking blend (§18). Reproducible: given the same stored opp +
    prefs it always yields the same number, even though an LLM produced `matches`."""
    jd_match = opp.match_score
    role = 1.0 if not prefs.target_roles or _matches_any(opp.title, prefs.target_roles) else 0.5
    if opp.work_mode == "remote" or not prefs.preferred_locations:
        location = 1.0
    elif opp.location and _matches_any(opp.location, prefs.preferred_locations):
        location = 1.0
    else:
        location = 0.6
    parts = {"jd_match": jd_match, "cheap": opp.cheap_score, "role": role,
             "location": location}
    return round(sum(parts[k] * w for k, w in _RANK_WEIGHTS.items()), 4)
