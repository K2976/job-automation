"""Offline evaluation on the mock provider. These assert the *deterministic* behaviour
(Verified): matching classification, provenance transitions, anti-hallucination,
false-positive guards, retrieval Hit@K. JD-extraction *accuracy* is only recorded (mock
labels vs mock lexicon is circular — see docs/ai-validation-report.md)."""
import pytest

from app.providers.llm import get_llm_provider
from app.text_utils import normalize_skill

from eval_lib import evaluate_jd
from labels import LABELS


@pytest.mark.parametrize("key", list(LABELS))
def test_jd_evaluation(key, candidate_id):
    label = LABELS[key]
    r = evaluate_jd(candidate_id, key, label, get_llm_provider("mock"))

    # role identified
    assert r["role_ok"], f"role: {r['role_extracted']!r}"

    # Verified: labeled skills classify as expected by the deterministic matcher
    assert r["matching"]["strong_ok"], r["matching"]["strong"]
    assert r["matching"]["missing_ok"], r["matching"]["missing"]

    # Verified: no mobile/UI terms leak into non-mobile JD requirements
    assert not r["false_positives"], r["false_positives"]

    # Verified: accept/reject/edit produce the right provenance transitions
    for action, res in r["human_in_the_loop"].items():
        assert res["ok"], (key, action, res)

    # Verified: the résumé never claims a skill the candidate lacks
    assert not r["anti_hallucination"]["claimed_forbidden"], \
        r["anti_hallucination"]["claimed_forbidden"]


def test_cybersecurity_is_honest_gap(candidate_id):
    """The strongest offline anti-hallucination case: the candidate has ~no security
    evidence, so the security résumé must stay honest and score low."""
    r = evaluate_jd(candidate_id, "cybersecurity_engineer",
                    LABELS["cybersecurity_engineer"], get_llm_provider("mock"))
    assert not r["anti_hallucination"]["claimed_forbidden"]
    assert r["validation"]["unsupported"] == 0            # nothing invented
    assert r["ats"]["tailored"] < 0.5                     # honestly low alignment


def test_retrieval_hits_labeled_evidence(candidate_id):
    """Observed: the retriever surfaces the right candidate evidence for clear tech terms."""
    for key in ("data_engineer", "backend_engineer", "ai_ml_engineer"):
        r = evaluate_jd(candidate_id, key, LABELS[key], get_llm_provider("mock"))
        for req, res in r["retrieval"].items():
            assert res["hit@5"], (key, req, res["modes"]["hybrid"])


def test_skill_normalization_rules():
    """§8: related surface forms collapse; distinct technologies do not."""
    assert normalize_skill("Postgres") == normalize_skill("PostgreSQL") == "postgresql"
    assert normalize_skill("PostgreSQL database") == "postgresql"
    # genuinely different technologies must stay distinct
    assert len({normalize_skill("SQL"), normalize_skill("PostgreSQL"),
                normalize_skill("MySQL")}) == 3
