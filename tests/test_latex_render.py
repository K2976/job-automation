"""LaTeX renderer tests (Part 5). The renderer is deterministic and needs no LLM; PDF
compilation is exercised only when a LaTeX engine is installed (skipped otherwise, so the
suite stays green on machines and CI without TeX)."""
import json
import shutil
from pathlib import Path

import pytest

from app import latex, pipeline
from app.models import (
    Candidate, ResumeBullet, ResumeEntry, ResumeSection, TailoredResume)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_resume.json"
HAS_ENGINE = latex.latex_available()


def _sample() -> TailoredResume:
    return TailoredResume.model_validate_json(FIXTURE.read_text())


# --------------------------------------------------------------- escaping -- #
@pytest.mark.parametrize("raw,expected", [
    ("50%", r"50\%"),
    ("R&D", r"R\&D"),
    ("foo_bar", r"foo\_bar"),
    ("C#", r"C\#"),
    ("C++", "C++"),                       # no special chars — untouched
    ("Node.js", "Node.js"),
    ("$ROOT", r"\$ROOT"),
    ("{a}", r"\{a\}"),
    ("a~b^c", r"a\textasciitilde{}b\textasciicircum{}c"),
    ("a\\b", r"a\textbackslash{}b"),      # backslash escaped exactly once
])
def test_escape(raw, expected):
    assert latex.latex_escape(raw) == expected


def test_escape_does_not_double_escape_backslash():
    # The replacement for "&" contains a backslash; it must not be re-processed.
    assert latex.latex_escape("&") == r"\&"


# ------------------------------------------------------------- rendering -- #
def test_renders_valid_document():
    tex = latex.render_latex(_sample())
    assert r"\documentclass{resume}" in tex
    assert r"\begin{document}" in tex and r"\end{document}" in tex
    assert "Ada Lovelace" in tex


def test_no_placeholder_content_leaks():
    tex = latex.render_latex(_sample())
    for junk in ("PEPPA", "Peppa", "Strange Place", "20xx", "aaa'bbb"):
        assert junk not in tex


def test_special_chars_are_escaped_in_body():
    tex = latex.render_latex(_sample())
    assert r"50\%" in tex and r"R\&D" in tex and r"foo\_bar" in tex
    assert r"C\#" in tex and r"\{analytics\}" in tex
    # a lone unescaped % (comment) is fine, but no raw "&"/"_" from content:
    assert "R&D" not in tex and "foo_bar" not in tex


def test_structured_entry_layout():
    tex = latex.render_latex(_sample())
    assert r"{\bf Acme R\&D}" in tex          # bold heading
    assert r"\hfill {\em 2022 -- Present}" in tex   # right-aligned date
    assert r"{\em Data Engineer}" in tex      # italic subheading


def test_entry_without_date_skips_hfill():
    r = TailoredResume(candidate=Candidate(name="X"), sections=[
        ResumeSection(title="Projects", entries=[
            ResumeEntry(heading="Proj", bullets=[ResumeBullet(text="did a thing")])])])
    tex = latex.render_latex(r)
    assert r"{\bf Proj}" in tex
    assert r"\hfill" not in tex.split(r"\begin{rSection}{Projects}")[1]


def test_empty_section_not_rendered():
    tex = latex.render_latex(_sample())
    assert "Empty Section" not in tex        # section with no entries/bullets is dropped
    assert "Awards" in tex                    # flat-bullet section still renders


def test_flat_bullets_render_when_no_entries():
    tex = latex.render_latex(_sample())
    assert "First Prize, University Hackathon (R&D track)".replace("&", r"\&") in tex


def test_header_links_from_candidate_only():
    tex = latex.render_latex(_sample())
    assert r"\faGithub{ github.com/ada}" in tex
    assert r"\faLinkedin{ linkedin.com/in/ada}" in tex   # scheme + www stripped
    assert r"\faEnvelope{ ada@example.com}" in tex
    assert r"\faMapMarker{ London, UK}" in tex


def test_unknown_template_raises_controlled_error():
    with pytest.raises(latex.TemplateNotFoundError):
        latex.render_latex(_sample(), template="does_not_exist")


# ------------------------------------------------------------ compilation -- #
@pytest.mark.skipif(not HAS_ENGINE, reason="no LaTeX engine (tectonic/pdflatex) installed")
def test_compile_sample_pdf():
    pdf = latex.compile_pdf(latex.render_latex(_sample()))
    assert pdf[:5] == b"%PDF-"


@pytest.mark.skipif(not HAS_ENGINE, reason="no LaTeX engine installed")
def test_compile_generated_resume(candidate_id):
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)
    resume = pipeline.generate_for_job(res["job_id"])["resume"]
    pdf = latex.compile_pdf(latex.render_latex(resume))
    assert pdf[:5] == b"%PDF-"


def test_original_master_profile_renders(candidate_id):
    """§38/§42: the untailored master profile must render through the template too."""
    from app import db, generation
    from app.models import Status
    candidate = db.get_candidate(candidate_id)
    entities = db.get_entities(candidate_id, statuses={Status.ORIGINAL})
    resume = generation.original_resume(candidate, entities)
    tex = latex.render_latex(resume)
    assert candidate.name in tex and r"\documentclass{resume}" in tex
    # original keeps ALL projects (no JD filtering), unlike a tailored view
    assert "PortfolioKit" in tex and "Parkezy" in tex and "Setu AI" in tex


@pytest.mark.skipif(not HAS_ENGINE, reason="no LaTeX engine installed")
def test_original_master_profile_compiles(candidate_id):
    from app import db, generation
    from app.models import Status
    resume = generation.original_resume(
        db.get_candidate(candidate_id),
        db.get_entities(candidate_id, statuses={Status.ORIGINAL}))
    assert latex.compile_pdf(latex.render_latex(resume))[:5] == b"%PDF-"


def test_compile_raises_when_no_engine(monkeypatch):
    monkeypatch.setattr(latex, "_engine", lambda: None)
    with pytest.raises(latex.LatexUnavailableError):
        latex.compile_pdf("\\documentclass{resume}\\begin{document}x\\end{document}")


def test_resume_cls_ships_with_template():
    cls = latex.TEMPLATES_DIR / latex.DEFAULT_TEMPLATE / "resume.cls"
    assert cls.exists(), "resume.cls must ship with the template so it can compile"
