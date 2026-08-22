"""End-to-end discovery, fully offline (FixtureSource + MockLLM). Proves the V1↔V2 seam
and that run report numbers are real, not hardcoded (§9)."""
from __future__ import annotations

from app import db
from app.config import settings
from app.models import OpportunityStatus, RunStatus, SearchPreferences
from app.opportunities import discovery


def _prefs() -> SearchPreferences:
    return SearchPreferences(
        target_roles=["Engineer", "Developer", "Cybersecurity"],
        experience_level="internship",
        preferred_locations=["India", "Remote"],
        remote_preference="any",
        sources=["fixtures"],
    )


def _run(candidate_id):
    run_id = discovery.start_run(candidate_id, _prefs())
    return discovery.execute_run(run_id)


def test_discovery_end_to_end_counts_are_real(candidate_id):
    run = _run(candidate_id)
    assert run.status == RunStatus.COMPLETE
    # 8 fixtures (6 + 2), senior role filtered, one cross-file duplicate collapsed.
    assert run.discovered == 8
    assert run.after_filtering == 7        # senior data engineer dropped by seniority
    assert run.after_dedup == 6            # backend intern duplicate collapsed
    assert run.deeply_analyzed == 6
    assert run.shortlisted == 6
    assert run.sources_checked == 1 and run.sources_successful == 1
    assert run.source_health[0].source == "fixtures"


def test_discovery_persists_analyzed_opportunities(candidate_id):
    _run(candidate_id)
    opps = db.list_opportunities(candidate_id, statuses=[OpportunityStatus.ANALYZED.value])
    assert len(opps) == 6
    for o in opps:
        assert o.requirements is not None
        assert o.opportunity_score > 0
        assert o.id is not None


def test_discovery_ranks_relevant_roles_above_irrelevant(candidate_id):
    run = _run(candidate_id)
    ordered = [db.get_opportunity(i) for i in run.opportunity_ids]
    titles = [o.title for o in ordered]
    # Backend/Data/AI/ML roles (strong overlap with the iOS+Python+backend profile) should
    # outrank the Cybersecurity intern (weak overlap).
    assert titles.index(next(t for t in titles if "Backend" in t)) < titles.index(
        next(t for t in titles if "Cybersecurity" in t))


def test_rediscovery_reuses_cache_without_duplicating(candidate_id):
    _run(candidate_id)
    first = db.list_opportunities(candidate_id)
    _run(candidate_id)  # same fixtures again
    second = db.list_opportunities(candidate_id)
    assert len(first) == len(second)  # upsert by (candidate, source, source_id), no dupes


def test_shortlist_narrows_below_analyzed(candidate_id):
    from app.config import settings
    old = settings.discovery_shortlist_n
    settings.discovery_shortlist_n = 3
    try:
        run = _run(candidate_id)
        assert run.deeply_analyzed == 6            # all survivors analysed
        assert run.shortlisted == 3                # but only the top 3 surfaced
        assert len(run.opportunity_ids) == 3       # count matches the ids exactly
    finally:
        settings.discovery_shortlist_n = old


def test_rejected_opportunity_not_resurfaced(candidate_id):
    _run(candidate_id)
    opp = db.list_opportunities(candidate_id)[0]
    opp.status = OpportunityStatus.REJECTED
    db.save_opportunity(opp)
    _run(candidate_id)
    refreshed = db.get_opportunity(opp.id)
    assert refreshed.status == OpportunityStatus.REJECTED  # stayed terminal
