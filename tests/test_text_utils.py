from app.text_utils import (
    extract_skills,
    keyword_overlap,
    normalize_skill,
    prettify_skill,
)


def test_alias_normalization():
    assert normalize_skill("Postgres") == "postgresql"
    assert normalize_skill("k8s") == "kubernetes"


def test_extract_multiword_and_single():
    skills = extract_skills("We use Python, PostgreSQL and build ETL data pipelines.")
    assert "python" in skills
    assert "postgresql" in skills
    assert "etl" in skills


def test_no_short_alias_false_positive():
    # "ai"/"ml" must not be pulled out of ordinary words or product names.
    assert "artificial intelligence" not in extract_skills("Setu AI helps you maintain")
    assert "machine learning" not in extract_skills("a tiny ml code tag")


def test_keyword_overlap():
    assert keyword_overlap("python sql", "python sql pipeline") == 1.0
    assert keyword_overlap("python sql", "swift ios") == 0.0


def test_prettify():
    assert prettify_skill("postgresql") == "PostgreSQL"
    assert prettify_skill("sql") == "SQL"
    assert prettify_skill("machine learning") == "Machine Learning"
