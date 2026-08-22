"""Human-reviewed ground truth for the evaluation set, against the bundled master
profile (data/fixtures/master_profile.json — iOS dev with Python/SQL/PostgreSQL/FastAPI/
Supabase/REST/1D-CNN/Edge-AI evidence; projects Parkezy, Setu AI, PortfolioKit).

Skill strings are canonical lowercase (as text_utils.extract_skills / normalize_skill
produce them). This is a *small, deliberate* benchmark — not automated ground truth."""
from __future__ import annotations

# Candidate entity names, for retrieval Hit@K labelling.
PARKEZY = "Parkezy"
SETU = "Setu AI"
FREELANCE = "iOS Developer at Freelance"

LABELS: dict[str, dict] = {
    "data_engineer": {
        "jd_file": "jd_data_engineer.txt",
        "role_substr": "Data Engineer",
        # requirements a competent analyst SHOULD extract (recall target)
        "expect_required": {"python", "sql", "postgresql", "etl", "rest"},
        # must NOT be extracted as requirements (JD never mentions mobile/UI)
        "expect_absent": {"swiftui", "swift"},
        # given the candidate, these must classify STRONG if extracted
        "expect_strong": {"python", "sql", "postgresql", "rest"},
        # candidate has no evidence — must classify MISSING if extracted
        "expect_missing": {"airflow", "spark", "dbt", "etl"},
        # requirement -> candidate entities that should retrieve in top-k
        "expect_evidence": {
            "postgresql": {PARKEZY, FREELANCE},
            "rest": {PARKEZY},
            "1d-cnn": {SETU},
        },
    },
    "ai_ml_engineer": {
        "jd_file": "jd_ai_ml_engineer.txt",
        "role_substr": "AI/ML Engineer",
        "expect_required": {"python", "machine learning", "deep learning", "rest"},
        "expect_absent": {"swiftui", "postgresql"},
        "expect_strong": {"python"},
        "expect_missing": {"pytorch", "tensorflow"},
        "expect_evidence": {
            "python": {SETU},
            "feature engineering": {SETU},
            "edge ai": {SETU},
        },
    },
    "backend_engineer": {
        "jd_file": "jd_backend_engineer.txt",
        "role_substr": "Backend Engineer",
        "expect_required": {"python", "fastapi", "rest", "postgresql"},
        "expect_absent": {"swiftui", "machine learning"},
        "expect_strong": {"python", "fastapi", "rest", "postgresql"},
        "expect_missing": {"docker", "microservices"},
        "expect_evidence": {
            "fastapi": {PARKEZY, FREELANCE},
            "postgresql": {PARKEZY, FREELANCE},
        },
    },
    "cybersecurity_engineer": {
        "jd_file": "jd_cybersecurity_engineer.txt",
        "role_substr": "Cybersecurity",
        # The candidate has ~zero security evidence. A real LLM should extract these;
        # the deterministic mock lexicon lacks most (a documented finding, not a bug).
        "expect_required": {"penetration testing", "vulnerability assessment",
                            "burp suite", "web security", "networking", "linux"},
        "expect_absent": {"swiftui", "fastapi", "postgresql"},
        # candidate genuinely has none of the security skills -> nothing strong here
        # (python is only nice-to-have; treated separately)
        "expect_strong": set(),
        "expect_missing": {"linux", "penetration testing", "burp suite",
                           "vulnerability assessment", "networking", "web security"},
        "expect_evidence": {},  # no candidate evidence should strongly match
        # anti-hallucination: the generated résumé must not claim these
        "must_not_claim": {"linux", "penetration testing", "burp suite",
                           "vulnerability assessment", "networking", "owasp"},
    },
}
