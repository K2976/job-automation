"""LLM provider abstraction (CLAUDE.md §10). Business logic depends only on this
interface — never on Gemini/Groq directly. The mock provider is fully deterministic and
offline so the whole pipeline runs and is tested with zero API keys."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from .. import prompts
from ..config import settings
from ..models import JDRequirements, MasterProfile
from ..text_utils import (
    content_tokens,
    extract_skills,
    normalize_skill,
    tokenize,
)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def _complete(self, system: str, user: str) -> str:
        """Raw text completion. Real providers implement this."""

    def _complete_json(self, system: str, user: str, schema: Type[T]) -> T:
        raw = self._complete(system + "\n\n" + _JSON_SUFFIX, user)
        return _parse_json(raw, schema)

    # --- domain operations (default impls render prompts + validate output) ----
    def analyze_jd(self, jd_text: str) -> JDRequirements:
        s, u = prompts.jd_analysis(jd_text)
        return self._complete_json(s, u, JDRequirements)

    def parse_resume(self, resume_text: str) -> MasterProfile:
        s, u = prompts.resume_parsing(resume_text)
        return self._complete_json(s, u, MasterProfile)

    def rewrite(self, instruction: str, original: str, evidence: str) -> str:
        s, u = prompts.rewrite(instruction, original, evidence)
        return self._complete(s, u).strip()

    def compose_summary(self, role: str, highlights: list[str]) -> str:
        s, u = prompts.summary(role, highlights)
        return self._complete(s, u).strip()


_JSON_SUFFIX = "Return ONLY valid minified JSON, no markdown fences."


def _parse_json(raw: str, schema: Type[T]) -> T:
    """Robustly pull a JSON object out of an LLM response and validate it."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        return schema.model_validate_json(text)
    except ValidationError as e:
        raise LLMError(f"LLM returned data not matching {schema.__name__}: {e}") from e
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {e}") from e


# --------------------------------------------------------------------------- #
# Mock provider — deterministic, offline, the default.                         #
# --------------------------------------------------------------------------- #
_REQUIRED_CUES = ("require", "must have", "must-have", "you have", "essential",
                  "minimum", "responsibilities")
_PREFERRED_CUES = ("prefer", "nice to have", "nice-to-have", "bonus", "plus",
                   "a plus", "desirable", "good to have")
_ACTION_VERBS = ("build", "design", "develop", "maintain", "implement", "create",
                 "manage", "optimize", "deploy", "analyze", "collaborate", "own",
                 "lead", "architect", "integrate", "scale", "monitor", "ship")
# Prose lead-ins that signal a marketing sentence, not a responsibility bullet.
_PROSE_LEADS = ("we ", "we're", "we are", "our ", "you'll", "you will", "as a",
                "the ideal", "this role", "join ", "about ")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")


class MockLLMProvider(LLMProvider):
    name = "mock"

    def _complete(self, system: str, user: str) -> str:  # pragma: no cover - unused path
        return user

    def analyze_jd(self, jd_text: str) -> JDRequirements:
        lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]
        all_skills = extract_skills(jd_text)

        required, preferred = [], []
        section = "required"
        for ln in lines:
            low = ln.lower()
            if any(c in low for c in _PREFERRED_CUES):
                section = "preferred"
            elif any(c in low for c in _REQUIRED_CUES):
                section = "required"
            for sk in extract_skills(ln):
                bucket = preferred if section == "preferred" else required
                if sk not in bucket and sk not in (preferred if bucket is required else required):
                    bucket.append(sk)
        # skills mentioned but never bucketed -> required
        for sk in all_skills:
            if sk not in required and sk not in preferred:
                required.append(sk)

        responsibilities = [
            ln.lstrip("-•* ").strip() for ln in lines
            if any(v in ln.lower() for v in _ACTION_VERBS) and len(ln.split()) > 3
            and not ln.lower().startswith(_PROSE_LEADS)
        ][:10]

        role = ""
        for ln in lines[:5]:
            if any(w in ln.lower() for w in ("engineer", "developer", "scientist",
                                             "analyst", "architect", "manager")):
                role = ln
                break
        role = role or (lines[0] if lines else "")

        freq = {}
        for t in content_tokens(jd_text):
            freq[t] = freq.get(t, 0) + 1
        keywords = [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:20]]

        domain_terms = [d for d in all_skills if d in (
            "data engineering", "machine learning", "natural language processing",
            "computer vision", "edge ai", "iot", "cybersecurity", "backend",
            "artificial intelligence", "rag", "llm", "data analysis")]

        return JDRequirements(
            role=role, required_skills=required, preferred_skills=preferred,
            responsibilities=responsibilities, technologies=all_skills,
            domain_terms=domain_terms, keywords=keywords,
            experience_expectations=[ln for ln in lines
                                     if re.search(r"\d+\+?\s*year", ln.lower())][:3],
        )

    def parse_resume(self, resume_text: str) -> MasterProfile:
        from ..models import (Candidate, ExperienceItem, ProjectItem, SkillItem)
        lines = [ln.rstrip() for ln in resume_text.splitlines()]
        nonempty = [ln.strip() for ln in lines if ln.strip()]
        email = (_EMAIL_RE.search(resume_text) or [None])
        email = email.group(0) if hasattr(email, "group") else ""
        phone_m = _PHONE_RE.search(resume_text)
        name = nonempty[0] if nonempty else ""
        candidate = Candidate(name=name, email=email,
                              phone=phone_m.group(0).strip() if phone_m else "")

        skills = [SkillItem(name=s) for s in extract_skills(resume_text)]

        # crude section split on PROJECTS / EXPERIENCE headings
        projects, experience = [], []
        section, buf, header = None, [], ""

        def flush():
            if not buf:
                return
            text = " ".join(buf)
            techs = extract_skills(text)
            if section == "projects":
                projects.append(ProjectItem(name=header or "Project",
                                            description=text, technologies=techs))
            elif section == "experience":
                experience.append(ExperienceItem(company=header or "Experience",
                                                 description=text, technologies=techs))

        for ln in nonempty[1:]:
            low = ln.lower()
            if low.startswith(("project", "projects")):
                flush(); section, buf, header = "projects", [], ""
                continue
            if low.startswith(("experience", "work experience", "employment")):
                flush(); section, buf, header = "experience", [], ""
                continue
            if section and not header and len(ln.split()) <= 8:
                header = ln
            elif section:
                buf.append(ln)
        flush()

        return MasterProfile(candidate=candidate, skills=skills,
                             projects=projects, experience=experience)

    def rewrite(self, instruction: str, original: str, evidence: str) -> str:
        focus = extract_skills(instruction + " " + evidence)
        supported = [f for f in focus if f in set(map(normalize_skill,
                     tokenize(original + " " + evidence))) or f in evidence.lower()]
        base = original.strip().rstrip(".")
        if supported:
            tail = ", ".join(dict.fromkeys(supported[:4]))
            return f"{base}; emphasising {tail} aligned to the target role."
        return base + "."

    def compose_summary(self, role: str, highlights: list[str]) -> str:
        top = ", ".join(dict.fromkeys(
            [s for h in highlights for s in extract_skills(h)][:5])) or "software engineering"
        lead = f"{role} with hands-on experience in {top}."
        extra = " ".join(h.rstrip(".") + "." for h in highlights[:2])
        return (lead + " " + extra).strip()


# --------------------------------------------------------------------------- #
def get_llm_provider(name: str | None = None) -> LLMProvider:
    provider = (name or settings.llm_provider or "mock").lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "gemini":
        from .gemini_llm import GeminiLLMProvider
        return GeminiLLMProvider()
    if provider == "groq":
        from .groq_llm import GroqLLMProvider
        return GroqLLMProvider()
    raise LLMError(f"Unknown LLM_PROVIDER: {provider!r} (expected mock|gemini|groq)")
