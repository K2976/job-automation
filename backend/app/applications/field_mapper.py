"""Deterministic field mapping (§13, §42). Maps a form field's label/name to a canonical
candidate field via normalization + aliases — NO LLM. Identity/contact fields resolve here
and never reach a provider. The layered strategy is: exact canonical → contiguous-phrase
alias; anything unmatched falls through to the question engine (which may use the LLM only
for genuinely semantic questions)."""
from __future__ import annotations

import re

from ..models import Candidate

# Canonical field keys the mapper can resolve.
FIRST_NAME = "first_name"
LAST_NAME = "last_name"
FULL_NAME = "full_name"
EMAIL = "email"
PHONE = "phone"
LINKEDIN = "linkedin"
GITHUB = "github"
WEBSITE = "website"
CITY = "city"
LOCATION = "location"
RESUME = "resume"
COVER_LETTER = "cover_letter"

# phrase → canonical. Multi-word phrases win over single words (checked longest-first),
# so "first name" resolves to first_name before the bare "name" → full_name.
_ALIASES: dict[str, str] = {
    "first name": FIRST_NAME, "given name": FIRST_NAME, "forename": FIRST_NAME,
    "first": FIRST_NAME,
    "last name": LAST_NAME, "surname": LAST_NAME, "family name": LAST_NAME,
    "last": LAST_NAME,
    "full name": FULL_NAME, "your name": FULL_NAME, "applicant name": FULL_NAME,
    "legal name": FULL_NAME, "name": FULL_NAME,
    "email address": EMAIL, "email": EMAIL, "e mail": EMAIL,
    "phone number": PHONE, "mobile number": PHONE, "telephone": PHONE,
    "contact number": PHONE, "phone": PHONE, "mobile": PHONE,
    "linkedin profile": LINKEDIN, "linkedin url": LINKEDIN, "linkedin": LINKEDIN,
    "github profile": GITHUB, "github url": GITHUB, "github": GITHUB,
    "personal website": WEBSITE, "portfolio url": WEBSITE, "portfolio": WEBSITE,
    "website": WEBSITE, "personal site": WEBSITE,
    "current location": LOCATION, "location": LOCATION, "where are you located": LOCATION,
    "city": CITY, "town": CITY,
    "resume upload": RESUME, "upload resume": RESUME, "resume": RESUME, "cv": RESUME,
    "cover letter": COVER_LETTER,
}

# Precompute (tokens, canonical), longest phrase first.
_ALIAS_SEQ = sorted(
    ((phrase.split(), canon) for phrase, canon in _ALIASES.items()),
    key=lambda pc: len(pc[0]), reverse=True)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _contiguous(hay: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(hay):
        return False
    for i in range(len(hay) - len(needle) + 1):
        if hay[i:i + len(needle)] == needle:
            return True
    return False


def map_field(label: str, name: str = "") -> str | None:
    """Return the canonical field key for a form field, or None if unmapped."""
    hay = _norm(f"{label} {name}").split()
    for tokens, canon in _ALIAS_SEQ:
        if _contiguous(hay, tokens):
            return canon
    return None


def candidate_field_values(candidate: Candidate) -> dict[str, str]:
    """Derive canonical field values from the flat master Candidate. Splits the name and
    pulls LinkedIn/GitHub/website out of the links list — the master profile is never
    modified (§36)."""
    parts = candidate.name.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    city = candidate.location.split(",")[0].strip() if candidate.location else ""

    linkedin = github = website = ""
    for link in candidate.links:
        low = link.lower()
        if "linkedin" in low and not linkedin:
            linkedin = link
        elif "github" in low and not github:
            github = link
        elif not website:
            website = link

    return {
        FIRST_NAME: first, LAST_NAME: last, FULL_NAME: candidate.name,
        EMAIL: candidate.email, PHONE: candidate.phone,
        LINKEDIN: linkedin, GITHUB: github, WEBSITE: website,
        CITY: city, LOCATION: candidate.location,
    }
