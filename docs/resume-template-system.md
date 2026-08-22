# Résumé template system (LaTeX)

The final résumé is rendered through a **deterministic structured-résumé → LaTeX →
PDF** layer, so the output looks like a professionally designed document instead of a
generic AI export. The LLM never writes LaTeX — it only produces the structured
`TailoredResume`; Python owns all document structure, escaping, and compilation.

```
TailoredResume (approved, structured)
        │
        ▼
app/latex.py  ──  Jinja2 (LaTeX-safe delimiters) + escaping
        │
        ▼
templates/kartik_professional/template.tex.j2  +  resume.cls
        │
        ▼
   resume.tex  ──►  tectonic / pdflatex  ──►  resume.pdf
```

## Why the LLM does not generate LaTeX
Asking a model for a whole `.tex` document burns tokens, adds latency, and fails
unpredictably (unbalanced braces, invented packages). We separate concerns:

- **LLM** — semantic content: summary, tailored bullets, wording adapted to the JD.
- **Deterministic code** — layout, section ordering, escaping, page geometry, compilation.

## Structured model → template mapping
The renderer consumes the **existing** `TailoredResume` model (no second schema). Part 5
added one thing: `ResumeSection.entries: list[ResumeEntry]` for items that need the
professional layout a flat bullet can't express.

| `ResumeEntry` field | LaTeX (`resume.cls`)              | Source |
|---------------------|-----------------------------------|--------|
| `heading`           | `{\bf …}` bold line               | project name / company / institution |
| `date`              | `\hfill {\em …}` (skipped if blank)| experience/education `start`–`end` |
| `subheading`        | `{\em …}` italic line             | job title / degree, field |
| `bullets[]`         | `\\ - …` lines                    | approved rewrite / original responsibilities / highlights |

`generation.generate_resume` builds `entries` from the *same supported evidence* it
already uses (`_supported_entities` + approved rewrites), and still fills the legacy
`section.bullets` unchanged — so the reportlab PDF, HTML, Markdown, and web preview keep
working with zero edits. Only the LaTeX renderer reads `entries`.

Sections are rendered generically (header, `summary`, `skills`, then each section's
`entries` or flat `bullets`). Empty sections are dropped — no orphan heading. The same
template therefore serves any role (AI/Data/Backend/…); only the content changes.

## LaTeX escaping (`latex.latex_escape`)
Candidate/LLM text is treated as **plain text**. Escaping is single-pass and
character-wise, so a replacement is never re-escaped (`\` → `\textbackslash{}` exactly
once). Covered: `\ { } $ & % # _ ~ ^`. Verified on `C++`, `C#`, `50%`, `R&D`, `foo_bar`,
`$ROOT`, URLs. Raw LaTeX only ever comes from the template and from the header line
builder (`_contact_lines`), which mixes fixed `\fa…` icon commands with *escaped* values.

## `resume.cls`
The template uses `\documentclass{resume}` (Trey Hunner's class, as shipped with the
Peppa Pig Overleaf template). The class file ships **inside the template directory** and
is copied next to the `.tex` at compile time — the compiler always has what it needs. We
do not substitute a different résumé class.

## Compilation (`latex.compile_pdf`)
- Finds an engine via `shutil.which`: **tectonic** (preferred — single binary, fetches
  packages on demand) then **pdflatex**.
- Compiles a temp copy in an isolated temp dir, **list-args, no shell, shell-escape off**,
  60 s timeout — candidate content can never execute commands.
- Returns PDF bytes, or raises `LatexUnavailableError` (no engine) / `LatexCompileError`
  (engine ran, no PDF — carries the log for server-side diagnostics).

## Endpoints & export UI
| Route | Output | Availability |
|-------|--------|--------------|
| `GET /api/jobs/{id}/export.latex.pdf` | professional PDF | needs a LaTeX engine; else friendly **503** |
| `GET /api/jobs/{id}/export.tex`       | LaTeX source     | always |
| `GET /api/jobs/{id}/export.pdf`       | reportlab PDF    | always (reliable fallback) |
| `GET /api/jobs/{id}/export.{html,md}` | HTML / Markdown  | always |

The UI offers **Professional PDF** and **PDF (standard)** side by side plus a `.tex`
link. Per §21 we never silently swap in a different design — if compilation is
unavailable the user gets a clear message and the standard PDF, not a surprise layout.

## Provenance
The renderer renders only what generation already approved. Entry bullets come from
original evidence or `USER_CONFIRMED`/`USER_EDITED` rewrites — never invented. Claim
validation (`validation.validate_resume`) still runs over the résumé and remains
authoritative; the template layer adds no new facts.

## Deployment
Local dev and any box with `tectonic`/`pdflatex` get the professional PDF for free. On
Render's default (free, Python-native) build there is **no** TeX engine, so
`export.latex.pdf` returns the friendly 503 and reportlab remains the working default —
nothing breaks. To enable the professional PDF in production, install tectonic in the
build (see [deployment.md](deployment.md)). We deliberately did **not** add a full
TeX-Live/Docker path — reportlab covers the fallback and keeps the free deploy simple.

## Adding another template
1. `backend/app/templates/<name>/` with `template.tex.j2`, its `*.cls`, and
   `template.schema.json`.
2. Use the LaTeX-safe delimiters (`\VAR{ }`, `\BLOCK{ }`) and the `e` filter on every
   candidate value.
3. `render_latex(resume, template="<name>")` / `compile_pdf(tex, template="<name>")`.

No changes to RAG, JD analysis, matching, planning, or validation are required — the
template layer is the only thing that varies.
