"""Versioned prompt templates. Kept in one module so they are easy to review, diff and
test — not scattered through business logic (CLAUDE.md §30). Only the real (Gemini/Groq)
providers render these; the mock provider computes deterministically instead."""
from __future__ import annotations

PROMPT_VERSION = "v1"

_JSON_RULE = (
    "Respond with ONLY a single valid JSON object matching the requested schema. "
    "No markdown, no code fences, no commentary."
)


def jd_analysis(jd_text: str) -> tuple[str, str]:
    system = (
        "You are a precise job-description analyst. Extract structured requirements "
        "from the JD. Do not invent requirements that are not present. " + _JSON_RULE
    )
    user = (
        "Schema keys: role (str), required_skills (str[]), preferred_skills (str[]), "
        "responsibilities (str[]), technologies (str[]), domain_terms (str[]), "
        "keywords (str[]), experience_expectations (str[]).\n\n"
        f"JOB DESCRIPTION:\n{jd_text}"
    )
    return system, user


def resume_parsing(resume_text: str) -> tuple[str, str]:
    system = (
        "You extract a structured professional profile from raw resume text. "
        "Only include information actually present in the text — never fabricate. "
        + _JSON_RULE
    )
    user = (
        "Schema: candidate{name,email,phone,location,headline,links[]}, "
        "skills[{name,category,level}], "
        "projects[{name,summary,description,domain,technologies[],languages[],"
        "responsibilities[],achievements[],metrics[],links[]}], "
        "experience[{company,title,start,end,description,technologies[],highlights[]}], "
        "education[{institution,degree,field,start,end}], "
        "certifications[{name,issuer,year}], achievements[{text}].\n\n"
        f"RESUME TEXT:\n{resume_text}"
    )
    return system, user


def rewrite(instruction: str, original: str, evidence: str) -> tuple[str, str]:
    system = (
        "You rewrite a single resume item for a target role. Use ONLY facts supported "
        "by the provided evidence and original text. Do not add technologies, metrics "
        "or claims that are not supported. Return plain text, one tightened paragraph."
    )
    user = (
        f"INSTRUCTION: {instruction}\n\nORIGINAL:\n{original}\n\n"
        f"SUPPORTING EVIDENCE:\n{evidence}\n\nRewritten item:"
    )
    return system, user


def summary(role: str, highlights: list[str]) -> tuple[str, str]:
    system = (
        "You write a 2-3 sentence professional summary for a resume targeting a role. "
        "Use only the provided highlights. No fabricated numbers or employers."
    )
    user = f"TARGET ROLE: {role}\nHIGHLIGHTS:\n- " + "\n- ".join(highlights) + "\n\nSummary:"
    return system, user
