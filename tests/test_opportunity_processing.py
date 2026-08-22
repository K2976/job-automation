"""Deterministic opportunity processing: normalize, dedup, filter, cheap match, rank (§37)."""
from __future__ import annotations

from app.models import Opportunity, RequirementMatch, MatchStatus, SearchPreferences
from app.opportunities import processing
from app.opportunities.sources.base import (
    OpportunitySource, RawOpportunity, SourceCaptcha, SourceStatus,
)
from app.retrieval import RetrievalIndex


def _raw(**kw) -> RawOpportunity:
    base = dict(source="fixtures", source_id="x", company="Acme", title="Data Engineer",
                location="Bangalore, India", description="Python and SQL data pipelines")
    base.update(kw)
    return RawOpportunity(**base)


# --------------------------------------------------------------- normalize #
def test_normalize_collapses_whitespace_and_extracts_tech():
    opp = processing.normalize(_raw(company="  Acme   Corp ", title="Data   Engineer"), 1)
    assert opp.company == "Acme Corp"
    assert opp.title == "Data Engineer"
    assert "python" in opp.technologies and "sql" in opp.technologies
    assert opp.jd_text.startswith("Data Engineer")


def test_normalize_infers_remote_work_mode():
    opp = processing.normalize(_raw(location="Remote - Anywhere", work_mode=""), 1)
    assert opp.work_mode == "remote"


def test_dedup_key_keeps_seniority_distinct():
    a = processing.normalize(_raw(title="Data Engineer"), 1)
    b = processing.normalize(_raw(title="Senior Data Engineer"), 1)
    assert a.dedup_key != b.dedup_key  # §37: similar-but-distinct titles stay separate


# ------------------------------------------------------------------- dedup #
def test_dedup_collapses_cross_source_and_records_ref():
    a = processing.normalize(_raw(source="greenhouse", source_id="1"), 1)
    b = processing.normalize(_raw(source="lever", source_id="2"), 1)
    out = processing.deduplicate([a, b])
    assert len(out) == 1
    assert "lever" in out[0].source_refs


def test_dedup_keeps_distinct_titles():
    a = processing.normalize(_raw(title="Data Engineer", source_id="1"), 1)
    b = processing.normalize(_raw(title="Senior Data Engineer", source_id="2"), 1)
    assert len(processing.deduplicate([a, b])) == 2


# ------------------------------------------------------------------ filter #
def test_filter_role_and_seniority():
    prefs = SearchPreferences(target_roles=["Data Engineer"], experience_level="internship")
    de = processing.normalize(_raw(title="Data Engineer Intern"), 1)
    senior = processing.normalize(_raw(title="Senior Data Engineer"), 1)
    ios = processing.normalize(_raw(title="iOS Developer"), 1)
    assert processing.passes_filters(de, prefs)[0] is True
    assert processing.passes_filters(senior, prefs)[0] is False   # seniority
    assert processing.passes_filters(ios, prefs)[0] is False       # role mismatch


def test_filter_excluded_company_and_remote_pref():
    prefs = SearchPreferences(excluded_companies=["Acme"])
    assert processing.passes_filters(processing.normalize(_raw(), 1), prefs)[0] is False
    remote_only = SearchPreferences(remote_preference="remote")
    onsite = processing.normalize(_raw(location="Bangalore", work_mode="onsite"), 1)
    assert processing.passes_filters(onsite, remote_only)[0] is False


def test_filter_missing_data_is_not_disqualifying():
    prefs = SearchPreferences(employment_types=["internship"])
    opp = processing.normalize(_raw(employment_type=""), 1)  # unknown type
    assert processing.passes_filters(opp, prefs)[0] is True


# -------------------------------------------------------------- cheap match #
def _index(candidate_id):
    from app import db, matching
    from app.models import SUPPORTED_STATUSES
    ents = db.get_entities(candidate_id, statuses=SUPPORTED_STATUSES)
    return RetrievalIndex(ents), matching.candidate_skill_set(ents)


def test_cheap_score_prefers_relevant_opportunity(candidate_id):
    index, skills = _index(candidate_id)
    relevant = processing.normalize(_raw(
        title="Backend Engineer", description="Python FastAPI PostgreSQL REST APIs"), candidate_id)
    irrelevant = processing.normalize(_raw(
        title="Sales Manager", description="cold calling and quota attainment"), candidate_id)
    assert processing.cheap_score(relevant, index, skills) > \
           processing.cheap_score(irrelevant, index, skills)


# ------------------------------------------------------------------- rank #
def test_opportunity_score_is_deterministic_and_ordered():
    prefs = SearchPreferences(target_roles=["Data Engineer"])
    strong = processing.normalize(_raw(), 1)
    strong.match_score, strong.cheap_score = 0.9, 0.8
    weak = processing.normalize(_raw(source_id="y"), 1)
    weak.match_score, weak.cheap_score = 0.2, 0.1
    s1 = processing.opportunity_score(strong, prefs)
    assert s1 == processing.opportunity_score(strong, prefs)  # reproducible
    assert s1 > processing.opportunity_score(weak, prefs)


# --------------------------------------------------- source error isolation #
def test_source_run_maps_captcha_to_status():
    class Blocked(OpportunitySource):
        name = "blocked"
        def discover(self, prefs):
            raise SourceCaptcha("challenge presented")

    result = Blocked().run(SearchPreferences())
    assert result.status == SourceStatus.CAPTCHA
    assert result.opportunities == []
    assert "challenge" in result.detail
