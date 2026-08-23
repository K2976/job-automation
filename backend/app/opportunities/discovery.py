"""Discovery orchestrator (§17, §46). Sequences the deterministic stages, spends LLM
calls ONLY on the top-N survivors (via pipeline.match_jd — one analyze_jd call each, no
rewrites), and writes real progress/counts to the DiscoveryRun as it goes so the UI polls
instead of holding an HTTP request open (§41). Source failures are isolated and reported;
nothing here retries a CAPTCHA (§7)."""
from __future__ import annotations

from .. import db, matching, pipeline
from ..config import settings
from ..models import (
    DiscoveryRun,
    MatchStatus,
    Opportunity,
    OpportunityStatus,
    RunStatus,
    SearchPreferences,
    _now,
)
from ..providers.llm import LLMError, LLMProvider, get_llm_provider
from ..retrieval import RetrievalIndex
from . import processing
from .sources import get_enabled_sources

# Statuses that mean "the user already dealt with this opp" — don't resurface it (§14).
_TERMINAL = {OpportunityStatus.REJECTED, OpportunityStatus.SKIPPED,
             OpportunityStatus.APPLIED, OpportunityStatus.EXPIRED}


def start_run(candidate_id: int, prefs: SearchPreferences) -> int:
    """Persist prefs (the Discover form *is* the search preferences, §13) and create a
    RUNNING run row. The caller schedules execute_run() in the background."""
    prefs.candidate_id = candidate_id
    db.save_preferences(prefs)
    run = DiscoveryRun(candidate_id=candidate_id, stage="Queued")
    db.insert_run(run)
    return run.id


def execute_run(run_id: int, llm: LLMProvider | None = None) -> DiscoveryRun:
    run = db.get_run(run_id)
    if run is None:
        raise KeyError(f"unknown run {run_id}")
    try:
        _execute(run, llm or get_llm_provider())
        run.status = RunStatus.COMPLETE
    except Exception as e:  # whole-run guard: a failure still leaves a readable run
        run.status = RunStatus.FAILED
        run.error = f"{type(e).__name__}: {e}"
    run.stage = "Done" if run.status == RunStatus.COMPLETE else "Failed"
    run.finished_at = _now()
    db.save_run(run)
    return run


def _execute(run: DiscoveryRun, llm: LLMProvider) -> None:
    candidate_id = run.candidate_id
    prefs = db.get_preferences(candidate_id)

    # Load every existing opp for this candidate ONCE (one query, not one-per-source-id).
    # db opens a fresh connection per call and discovery touches ~1000 rows — against remote
    # Postgres that was 1000 round-trips and minutes of stall; this cache-lookup map is 1 (§30).
    existing = {(o.source, o.source_id): o for o in db.list_opportunities(candidate_id)}

    # 0. Retire opportunities from sources this run isn't querying (e.g. the offline
    # `fixtures` demo rows with example.com links) so they stop cluttering Results once you
    # switch to real sources. EXPIRED is terminal, so they never resurface (§14).
    enabled_names = {s.name for s in get_enabled_sources(prefs.sources or None)}
    for stale in existing.values():
        if stale.source and stale.source not in enabled_names and stale.status not in _TERMINAL:
            stale.status = OpportunityStatus.EXPIRED
            db.save_opportunity(stale)

    # 1. Collect (error-isolated per source) -----------------------------------
    run.stage = "Checking sources"
    db.save_run(run)
    sources = get_enabled_sources(prefs.sources or None)
    raw = []
    for src in sources:
        result = src.run(prefs)
        run.source_health.append(result.health())
        run.sources_checked += 1
        if result.status.value == "AVAILABLE":
            run.sources_successful += 1
            raw.extend(result.opportunities)
        else:
            run.sources_skipped += 1
    run.discovered = len(raw)
    run.stage = "Collecting opportunities"
    db.save_run(run)

    # 2. Normalize + cache lookup ---------------------------------------------
    opps: list[Opportunity] = []
    for r in raw:
        opp = processing.normalize(r, candidate_id)
        cached = existing.get((opp.source, opp.source_id))
        if cached is not None:
            if cached.status in _TERMINAL:
                continue  # already handled by the user — don't resurface
            opp.id = cached.id
            # Reuse prior analysis if the JD is unchanged (§30 caching).
            if cached.requirements is not None and cached.jd_text.strip() == opp.jd_text.strip():
                opp.requirements = cached.requirements
                opp.matches = cached.matches
                opp.gaps = cached.gaps
                opp.match_score = cached.match_score
                opp.job_id = cached.job_id
                opp.status = OpportunityStatus.ANALYZED
        opps.append(opp)

    # 3. Hard filter -----------------------------------------------------------
    kept = [o for o in opps if processing.passes_filters(o, prefs)[0]]
    run.after_filtering = len(kept)
    run.stage = "Filtering"
    db.save_run(run)

    # 4. Deduplicate -----------------------------------------------------------
    deduped = processing.deduplicate(kept)
    run.after_dedup = len(deduped)
    run.stage = "Removing duplicates"
    db.save_run(run)

    # 5. Cheap match (LLM-free) + pick top-N ----------------------------------
    entities = pipeline._supported_entities(candidate_id)
    index = RetrievalIndex(entities)
    skill_set = matching.candidate_skill_set(entities)
    for o in deduped:
        o.cheap_score = processing.cheap_score(o, index, skill_set)
        if o.status == OpportunityStatus.DISCOVERED:
            o.status = OpportunityStatus.FILTERED
    deduped.sort(key=lambda o: o.cheap_score, reverse=True)
    # The user-requested result count (Discover form) sizes the shortlist, clamped to a hard
    # cap; we still deep-analyse at least deep_top_n so the shortlist is chosen from a real
    # ranked pool. Each analysed opp is one LLM call (§8, §41). 0 ⇒ server default.
    shortlist_size = settings.discovery_shortlist_n
    if prefs.result_limit and prefs.result_limit > 0:
        shortlist_size = min(prefs.result_limit, settings.discovery_max_result_limit)
    deep_n = max(settings.discovery_deep_top_n, shortlist_size)
    top = deduped[:deep_n]
    run.stage = "Matching against your profile"
    db.save_run(run)

    # 6. Deep analysis — one analyze_jd per survivor, reusing V1 RAG (§16) -----
    run.stage = "Analyzing top opportunities"
    db.save_run(run)
    for o in top:
        if o.requirements is not None:  # cache hit — skip the LLM call
            run.deeply_analyzed += 1
            continue
        try:
            m = pipeline.match_jd(candidate_id, o.jd_text, llm)
        except LLMError:
            continue  # leave FILTERED; a bad JD/provider blip doesn't sink the run
        o.requirements = m["requirements"]
        o.matches = m["matches"]
        o.gaps = m["gaps"]
        o.match_score = _coverage(m["matches"])
        o.status = OpportunityStatus.ANALYZED
        run.deeply_analyzed += 1
        db.save_run(run)

    # 7. Rank + persist --------------------------------------------------------
    for o in deduped:
        o.opportunity_score = processing.opportunity_score(o, prefs)
        o.id = db.upsert_opportunity(o)

    analyzed = [o for o in deduped if o.status == OpportunityStatus.ANALYZED]
    analyzed.sort(key=lambda o: o.opportunity_score, reverse=True)
    # The shortlist is the top-ranked slice surfaced as this run's results. Opportunities
    # analysed beyond it stay ANALYZED and remain in the full list, but the run points only
    # at the shortlist — so `shortlisted` always equals len(opportunity_ids) (honest count).
    shortlist = analyzed[:shortlist_size]
    run.shortlisted = len(shortlist)
    run.opportunity_ids = [o.id for o in shortlist]  # results, best-first


def _coverage(matches) -> float:
    if not matches:
        return 0.0
    good = sum(1 for m in matches if m.match_status in
               (MatchStatus.STRONG_MATCH, MatchStatus.PARTIAL_MATCH))
    return round(good / len(matches), 4)
