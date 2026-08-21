from app import db, matching
from app.models import JDRequirements, MatchStatus, SUPPORTED_STATUSES
from app.providers import get_embedding_provider
from app.retrieval import RetrievalIndex


def _index(candidate_id):
    entities = db.get_entities(candidate_id, statuses=SUPPORTED_STATUSES)
    return entities, RetrievalIndex(entities, get_embedding_provider("local"))


def test_semantic_discriminates(candidate_id):
    _, index = _index(candidate_id)
    hits = index.search("PostgreSQL database and SQL data modelling", top_k=3)
    names = [h.entity.name.lower() for h in hits]
    # a data/backend project should outrank the pure-UI component library
    assert "portfoliokit" not in names[:1]


def test_match_classification(candidate_id):
    entities, index = _index(candidate_id)
    skill_set = matching.candidate_skill_set(entities)
    req = JDRequirements(role="Data Engineer",
                         required_skills=["python", "postgresql", "airflow"],
                         preferred_skills=["spark"])
    matches = {m.requirement: m.match_status
               for m in matching.match_requirements(index, req, skill_set)}
    assert matches["python"] == MatchStatus.STRONG_MATCH
    assert matches["postgresql"] == MatchStatus.STRONG_MATCH
    assert matches["airflow"] == MatchStatus.MISSING       # genuine gap
    assert matches["spark"] == MatchStatus.MISSING


def test_gap_excludes_strong(candidate_id):
    entities, index = _index(candidate_id)
    skill_set = matching.candidate_skill_set(entities)
    req = JDRequirements(required_skills=["python", "kubernetes"])
    matches = matching.match_requirements(index, req, skill_set)
    gaps = {g.requirement for g in matching.analyze_gaps(matches)}
    assert "python" not in gaps        # strong match is not a gap
    assert "kubernetes" in gaps
