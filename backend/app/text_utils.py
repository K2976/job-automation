"""Deterministic NLP helpers shared by the mock provider, retrieval, matching and ATS.
Keeps the offline path believable without pulling in heavyweight ML deps."""
from __future__ import annotations

import re
from collections import Counter

# Canonical skill/technology lexicon. Aliases map surface forms -> canonical name so
# "Postgres", "PostgreSQL" and "postgresql database" all collapse (CLAUDE.md §8B), but
# genuinely different technologies stay distinct.
_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
    "postgresql database": "postgresql",
    "psql": "postgresql",
    "golang": "go",
    "k8s": "kubernetes",
    "nlp": "natural language processing",
    "gcp": "google cloud",
    "aws cloud": "aws",
    "rest api": "rest",
    "restful": "rest",
    "restful api": "rest",
    "ci/cd": "cicd",
    "ci cd": "cicd",
    "node.js": "node",
    "nodejs": "node",
    "react.js": "react",
    "next.js": "nextjs",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tf": "tensorflow",
    "llms": "llm",
    "large language models": "llm",
    "large language model": "llm",
}

# Canonical terms we recognise. Multi-word entries are matched before single words.
_CANONICAL: set[str] = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "swift",
    "kotlin", "sql", "postgresql", "mysql", "sqlite", "mongodb", "redis", "supabase",
    "fastapi", "flask", "django", "express", "node", "react", "nextjs", "swiftui",
    "rest", "graphql", "grpc", "docker", "kubernetes", "aws", "google cloud", "azure",
    "airflow", "spark", "kafka", "hadoop", "etl", "data pipeline", "data warehouse",
    "dbt", "snowflake", "bigquery", "pandas", "numpy", "scikit-learn", "pytorch",
    "tensorflow", "keras", "machine learning", "deep learning",
    "natural language processing", "computer vision", "llm", "rag", "embeddings",
    "cnn", "1d-cnn", "edge ai", "iot", "mqtt", "cybersecurity", "cicd", "git",
    "linux", "bash", "microservices", "api", "backend", "frontend", "database",
    "artificial intelligence", "data engineering", "data analysis", "feature engineering",
    "model deployment", "vector database", "prompt engineering", "edge impulse",
    "max78000", "esp32", "arduino", "raspberry pi", "real-time", "websocket",
}

# Multi-word terms sorted longest-first for greedy matching.
_MULTIWORD = sorted((t for t in _CANONICAL if " " in t or "-" in t or "/" in t),
                    key=len, reverse=True)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\+\#\.\-]*")

_STOPWORDS = {
    "the", "and", "a", "an", "of", "to", "in", "for", "with", "on", "at", "by",
    "is", "are", "as", "or", "be", "we", "our", "you", "your", "will", "have",
    "has", "this", "that", "from", "into", "using", "use", "used", "work", "working",
    "experience", "years", "year", "team", "role", "job", "candidate", "strong",
    "ability", "including", "such", "etc", "e.g", "i.e", "who", "what", "when",
}


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def content_tokens(text: str) -> list[str]:
    """Tokens minus stopwords/pure-numbers — for keyword scoring."""
    return [t for t in tokenize(text) if t not in _STOPWORDS and not t.isdigit()]


def normalize_skill(term: str) -> str:
    t = (term or "").strip().lower()
    return _ALIASES.get(t, t)


def _present(term: str, low: str, tokens: set[str]) -> bool:
    """Single-token terms must match a whole token (so 'ai' never matches 'maintain');
    multi-token phrases match as substrings."""
    term_tokens = tokenize(term)
    if len(term_tokens) == 1 and "/" not in term and " " not in term:
        return term_tokens[0] in tokens
    return term in low


def extract_skills(text: str) -> list[str]:
    """Pull known skills/technologies out of free text, de-duplicated, canonicalised."""
    low = (text or "").lower()
    tokens = set(tokenize(low))
    found: list[str] = []
    seen: set[str] = set()

    def add(canon: str) -> None:
        if canon not in seen:
            seen.add(canon)
            found.append(canon)

    # aliased/phrase forms first (longest first), then canonical terms
    for term in sorted(_ALIASES, key=len, reverse=True):
        if _present(term, low, tokens):
            add(normalize_skill(term))
    for term in sorted(_CANONICAL, key=len, reverse=True):
        if _present(term, low, tokens):
            add(normalize_skill(term))
    return found


def keyword_overlap(query: str, doc: str) -> float:
    """Jaccard-ish overlap of content tokens — cheap keyword relevance signal."""
    q = set(content_tokens(query))
    d = set(content_tokens(doc))
    if not q:
        return 0.0
    return len(q & d) / len(q)


def term_frequencies(text: str) -> Counter:
    return Counter(content_tokens(text))


# Display casing for canonical skill forms (retrieval uses lowercase; humans don't).
_ACRONYMS = {"sql", "rest", "api", "etl", "aws", "gcp", "iot", "llm", "rag", "cnn",
             "mqtt", "cicd", "grpc", "dbt"}
_PRETTY = {
    "postgresql": "PostgreSQL", "mysql": "MySQL", "sqlite": "SQLite",
    "javascript": "JavaScript", "typescript": "TypeScript", "nextjs": "Next.js",
    "nodejs": "Node.js", "node": "Node.js", "fastapi": "FastAPI", "swiftui": "SwiftUI",
    "github": "GitHub", "scikit-learn": "scikit-learn", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "1d-cnn": "1D-CNN", "max78000": "MAX78000",
    "esp32": "ESP32", "google cloud": "Google Cloud", "edge ai": "Edge AI",
}


def prettify_skill(canon: str) -> str:
    c = canon.lower()
    if c in _PRETTY:
        return _PRETTY[c]
    if c in _ACRONYMS:
        return c.upper()
    return " ".join(w.upper() if w in _ACRONYMS else w.capitalize() for w in c.split())
