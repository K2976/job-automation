"""Application batch selection (hard max invariant) + package preparation reusing V1 (§37)."""
from __future__ import annotations

import pytest

from app import db
from app.models import OpportunityStatus, SearchPreferences, TailoredResume
from app.opportunities import batches, discovery, packages


def _discover(candidate_id) -> list[int]:
    prefs = SearchPreferences(target_roles=["Engineer", "Developer"],
                              experience_level="internship", sources=["fixtures"])
    run = discovery.execute_run(discovery.start_run(candidate_id, prefs))
    return run.opportunity_ids


def test_batch_rejects_selection_over_maximum(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=2)
    with pytest.raises(batches.BatchLimitExceeded):
        batches.set_selection(batch.id, ids[:3])          # 3 > 2
    # nothing partially applied — selection stays empty
    assert db.get_batch(batch.id).opportunity_ids == []


def test_batch_selection_within_limit_shortlists(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=3)
    batches.set_selection(batch.id, ids[:2])
    assert db.get_batch(batch.id).opportunity_ids == ids[:2]
    for oid in ids[:2]:
        assert db.get_opportunity(oid).status == OpportunityStatus.SHORTLISTED


def test_deselection_returns_to_analyzed(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=5)
    batches.set_selection(batch.id, ids[:2])
    batches.set_selection(batch.id, ids[:1])              # drop the 2nd
    assert db.get_opportunity(ids[1]).status == OpportunityStatus.ANALYZED
    assert db.get_opportunity(ids[0]).status == OpportunityStatus.SHORTLISTED


def test_selection_at_exactly_maximum_ok(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=2)
    batches.set_selection(batch.id, ids[:2])              # exactly max
    assert len(db.get_batch(batch.id).opportunity_ids) == 2


def test_prepare_batch_builds_packages_via_v1(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=2)
    batches.set_selection(batch.id, ids[:2])
    result = packages.prepare_batch(batch.id)
    assert len(result["prepared"]) == 2
    for oid in ids[:2]:
        opp = db.get_opportunity(oid)
        assert opp.status == OpportunityStatus.READY_TO_APPLY
        assert opp.job_id is not None
        assert opp.cover_letter                            # drafted
        # the V1 résumé really was generated and persisted on the job
        stored = db.get_generation(opp.job_id)
        assert TailoredResume.model_validate_json(stored).sections


def test_v2_never_sets_applied_automatically(candidate_id):
    ids = _discover(candidate_id)
    batch = batches.create_batch(candidate_id, "B", max_opportunities=1)
    batches.set_selection(batch.id, ids[:1])
    packages.prepare_batch(batch.id)
    assert db.get_opportunity(ids[0]).status != OpportunityStatus.APPLIED
