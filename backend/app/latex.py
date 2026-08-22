"""Deterministic structured-résumé → LaTeX → PDF renderer (Part 5).

The LLM never produces LaTeX. It emits the structured `TailoredResume`; this module
maps that model onto a professional Overleaf template (resume.cls) via Jinja2 with
LaTeX-safe delimiters, escapes all candidate text, and — when a LaTeX engine is present —
compiles it to a PDF. `render_latex` is fully deterministic and needs no compiler, so
`.tex` export works everywhere; PDF compilation is best-effort and degrades to a clear
error (see api.export_latex_pdf) when no engine is installed."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import jinja2

from .models import TailoredResume

TEMPLATES_DIR = Path(__file__).parent / "templates"
DEFAULT_TEMPLATE = "kartik_professional"
_COMPILE_TIMEOUT = 60  # seconds — a résumé is tiny; anything longer is a hang.


class TemplateNotFoundError(FileNotFoundError):
    pass


class LatexUnavailableError(RuntimeError):
    """No LaTeX engine (tectonic/pdflatex) is installed."""


class LatexCompileError(RuntimeError):
    """The engine ran but did not produce a PDF. `.log` holds the engine output."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


# --------------------------------------------------------------------------- #
# Escaping — candidate/LLM text is plain text; the template owns the LaTeX.    #
# --------------------------------------------------------------------------- #
_LATEX_MAP = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
    "%": r"\%", "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text: object) -> str:
    """Escape a string for safe insertion as LaTeX body text. Single-pass and
    character-wise, so replacements are never re-escaped (a backslash becomes
    `\\textbackslash{}` exactly once). Handles C++, C#, 50%, R&D, foo_bar, URLs."""
    return "".join(_LATEX_MAP.get(c, c) for c in str(text if text is not None else ""))


def _env(template_dir: Path) -> jinja2.Environment:
    # LaTeX uses { } and % everywhere, so Jinja's defaults would collide. Use the
    # well-known LaTeX-safe delimiters and escape values explicitly via the `e` filter.
    env = jinja2.Environment(
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        trim_blocks=True, lstrip_blocks=True, autoescape=False,
        loader=jinja2.FileSystemLoader(str(template_dir)),
    )
    env.filters["e"] = latex_escape
    return env


# --------------------------------------------------------------------------- #
# Structured résumé -> template context                                       #
# --------------------------------------------------------------------------- #
def _strip_scheme(url: str) -> str:
    for p in ("https://", "http://"):
        if url.startswith(p):
            url = url[len(p):]
    return url.rstrip("/").removeprefix("www.")


def _find(links: list[str], key: str) -> str:
    return next((l for l in links if key in l.lower()), "")


def _contact_lines(candidate) -> tuple[str, str]:
    """Header address lines mixing template LaTeX (faIcons) with escaped candidate text.
    Values are escaped here because the whole line is raw LaTeX — the template must not
    re-escape it. Links come only from candidate data (never invented — §13)."""
    def icon(cmd: str, value: str) -> str:
        return rf"\fa{cmd}{{ {latex_escape(value)}}}" if value else ""

    github, linkedin = _find(candidate.links, "github"), _find(candidate.links, "linkedin")
    top = [icon("Github", _strip_scheme(github)), icon("Linkedin", _strip_scheme(linkedin)),
           icon("Envelope", candidate.email)]
    bottom = [icon("MapMarker", candidate.location), icon("Phone", candidate.phone)]
    return " ".join(p for p in top if p), " ".join(p for p in bottom if p)


def resume_to_context(resume: TailoredResume) -> dict:
    c = resume.candidate
    contact_line, location_line = _contact_lines(c)
    sections = []
    for sec in resume.sections:
        entries = [{
            "heading": e.heading, "subheading": e.subheading, "date": e.date,
            "bullets": [b.text for b in e.bullets if b.text.strip()],
        } for e in sec.entries]
        # Fall back to flat bullets only for sections with no structured entries;
        # entry-based sections already carry their content (avoids double render).
        plain = [b.text for b in sec.bullets if b.text.strip()] if not entries else []
        if entries or plain:
            sections.append({"title": sec.title, "entries": entries, "plain_bullets": plain})
    return {
        "name": c.name, "contact_line": contact_line, "location_line": location_line,
        "summary": resume.summary, "skills": resume.skills, "sections": sections,
    }


def render_latex(resume: TailoredResume, template: str = DEFAULT_TEMPLATE) -> str:
    """Structured résumé -> .tex source. Deterministic; no compiler required."""
    tdir = TEMPLATES_DIR / template
    if not (tdir / "template.tex.j2").exists():
        raise TemplateNotFoundError(f"Unknown résumé template {template!r}")
    return _env(tdir).get_template("template.tex.j2").render(**resume_to_context(resume))


# --------------------------------------------------------------------------- #
# Compilation — best-effort, sandboxed to a temp dir, no shell.               #
# --------------------------------------------------------------------------- #
def _engine() -> tuple[str, str] | None:
    for name in ("tectonic", "pdflatex"):
        path = shutil.which(name)
        if path:
            return name, path
    return None


def latex_available() -> bool:
    return _engine() is not None


def compile_pdf(tex: str, template: str = DEFAULT_TEMPLATE) -> bytes:
    """Compile .tex to PDF bytes. Runs the engine on a temp copy (with the template's
    .cls files) using list-args — never a shell — with shell-escape left off, so
    candidate content can never execute commands (§36)."""
    engine = _engine()
    if engine is None:
        raise LatexUnavailableError(
            "No LaTeX engine found. Install 'tectonic' (recommended) or a TeX distribution.")
    name, path = engine
    tdir = TEMPLATES_DIR / template
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        for cls in tdir.glob("*.cls"):
            shutil.copy(cls, work / cls.name)
        tex_path = work / "resume.tex"
        tex_path.write_text(tex, encoding="utf-8")
        if name == "tectonic":
            cmd = [path, "--chatter", "minimal", "--outdir", str(work), str(tex_path)]
        else:  # pdflatex
            cmd = [path, "-interaction=nonstopmode", "-halt-on-error",
                   "-no-shell-escape", "-output-directory", str(work), str(tex_path)]
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True,
                                  timeout=_COMPILE_TIMEOUT, text=True)
        except subprocess.TimeoutExpired as e:
            raise LatexCompileError("LaTeX compilation timed out", log=str(e)) from e
        pdf = work / "resume.pdf"
        if proc.returncode != 0 or not pdf.exists():
            raise LatexCompileError("LaTeX compilation failed",
                                    log=(proc.stdout or "") + (proc.stderr or ""))
        return pdf.read_bytes()
