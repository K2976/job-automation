"""FastAPI layer. Thin — all logic lives in the pipeline/stage modules; endpoints just
validate input, call the pipeline, and return Pydantic models. Serves a single-page UI
that drives the whole flow (backend-first; a full Next.js frontend is future work)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analysis, db, export, generation, ingestion, kb, latex, pipeline
from .config import REPO_ROOT, settings
from .models import (
    ApprovalAction,
    Candidate,
    EntityType,
    KBEntity,
    MasterProfile,
    Status,
    TailoredResume,
)
from .providers.llm import LLMError, get_llm_provider

STATIC = Path(__file__).parent / "static"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Adaptive Resume Engineer", version="0.1.0", lifespan=lifespan)

# Allow the frontend to call the API when they're deployed on different hosts
# (e.g. Vercel + Render). No cookies/credentials are used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ requests #
class JobIn(BaseModel):
    candidate_id: int
    jd_text: str


class ApprovalIn(BaseModel):
    action: ApprovalAction
    edited_text: str = ""


class EntityUpdateIn(BaseModel):
    name: str | None = None
    content: str | None = None
    domain: str | None = None
    status: Status | None = None


class EntityCreateIn(BaseModel):
    entity_type: EntityType
    name: str
    content: str
    domain: str = ""


# --------------------------------------------------------------------- meta #
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider,
            "embedding_provider": settings.embedding_provider}


@app.get("/api/fixtures/jds")
def sample_jds() -> dict:
    out = {}
    for f in sorted(pipeline.FIXTURES.glob("jd_*.txt")):
        text = f.read_text()
        label = next((ln.strip() for ln in text.splitlines() if ln.strip()), f.stem)
        out[label] = text
    return out


# ---------------------------------------------------------------- candidate #
@app.post("/api/candidates/seed-fixture")
def seed_fixture() -> dict:
    """Dev convenience: load the bundled sample master profile."""
    candidate_id = pipeline.seed_from_fixture()
    return {"candidate_id": candidate_id,
            "candidate": db.get_candidate(candidate_id)}


@app.post("/api/ingest")
async def ingest(file: UploadFile | None = File(default=None),
                 text: str = Form(default="")) -> MasterProfile:
    """Parse a resume (uploaded file or pasted text) into a reviewable profile.
    Does NOT persist — the candidate reviews it before it becomes the master profile."""
    llm = get_llm_provider()
    try:
        if file is not None:
            data = await file.read()
            text = ingestion.extract_text(file.filename or "resume.txt", data)
        elif not text.strip():
            raise HTTPException(400, "Provide a file or a non-empty 'text' form field.")
        return ingestion.ingest_resume_text(text, llm)
    except ingestion.IngestionError as e:
        raise HTTPException(400, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))


@app.post("/api/extract-jd")
async def extract_jd(file: UploadFile = File(...)) -> dict:
    """Extract plain text from an uploaded JD file (PDF/DOCX/TXT) for the JD box."""
    try:
        text = ingestion.extract_text(file.filename or "jd.txt", await file.read())
    except ingestion.IngestionError as e:
        raise HTTPException(400, str(e))
    return {"text": text}


@app.post("/api/candidates")
def create_candidate(profile: MasterProfile) -> dict:
    """Persist a reviewed master profile as the candidate knowledge base."""
    candidate_id = kb.seed_profile(profile)
    return {"candidate_id": candidate_id}


@app.get("/api/candidates/{candidate_id}")
def get_candidate(candidate_id: int) -> dict:
    candidate = db.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    entities = db.get_entities(candidate_id)
    return {"candidate": candidate, "entities": entities}


@app.patch("/api/candidates/{candidate_id}")
def edit_candidate(candidate_id: int, candidate: Candidate) -> dict:
    """Let the candidate correct extracted contact/header info by hand (§5)."""
    if not db.update_candidate(candidate_id, candidate):
        raise HTTPException(404, "candidate not found")
    return {"candidate": db.get_candidate(candidate_id)}


@app.post("/api/candidates/{candidate_id}/entities")
def add_entity(candidate_id: int, body: EntityCreateIn) -> KBEntity:
    """Manually add a profile entity the LLM missed — status ORIGINAL (candidate-entered)."""
    if db.get_candidate(candidate_id) is None:
        raise HTTPException(404, "candidate not found")
    ent = KBEntity(candidate_id=candidate_id, entity_type=body.entity_type,
                   name=body.name, content=body.content, domain=body.domain,
                   status=Status.ORIGINAL, source="manual_entry")
    ent.id = db.insert_entity(ent)
    return ent


@app.patch("/api/entities/{entity_id}")
def edit_entity(entity_id: int, body: EntityUpdateIn) -> KBEntity:
    """Edit an extracted entity. A hand-edit of ORIGINAL info stays candidate-owned."""
    if db.get_entity(entity_id) is None:
        raise HTTPException(404, "entity not found")
    db.update_entity(entity_id, name=body.name, content=body.content,
                     domain=body.domain, status=body.status)
    return db.get_entity(entity_id)


@app.delete("/api/entities/{entity_id}")
def remove_entity(entity_id: int) -> dict:
    if not db.delete_entity(entity_id):
        raise HTTPException(404, "entity not found")
    return {"deleted": entity_id}


# --------------------------------------------------------------------- jobs #
@app.post("/api/jobs")
def create_job(job: JobIn) -> dict:
    if db.get_candidate(job.candidate_id) is None:
        raise HTTPException(404, "candidate not found")
    if not job.jd_text.strip():
        raise HTTPException(400, "jd_text is empty")
    try:
        return pipeline.analyze_job(job.candidate_id, job.jd_text)
    except LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/jobs/{job_id}/plan")
def get_plan(job_id: int) -> dict:
    if db.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    return {"suggestions": db.get_suggestions(job_id)}


@app.post("/api/suggestions/{suggestion_id}/approve")
def approve(suggestion_id: str, body: ApprovalIn) -> dict:
    row = db.get_suggestion(suggestion_id)
    if row is None:
        raise HTTPException(404, "suggestion not found")
    status = pipeline.planning.apply_approval(
        row["candidate_id"], suggestion_id, body.action, body.edited_text)
    return {"suggestion_id": suggestion_id, "status": status}


@app.post("/api/jobs/{job_id}/generate")
def generate(job_id: int) -> dict:
    if db.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    try:
        return pipeline.generate_for_job(job_id)
    except LLMError as e:
        raise HTTPException(502, str(e))


class RoleProfileIn(BaseModel):
    name: str
    job_id: int


@app.post("/api/candidates/{candidate_id}/role-profiles")
def create_role_profile(candidate_id: int, body: RoleProfileIn) -> dict:
    """Save a named, reusable role-specific view (a snapshot of an analyzed job with its
    approved modifications). A view over the master profile — not a separate profile."""
    job = db.get_job(body.job_id)
    if job is None or job["candidate_id"] != candidate_id:
        raise HTTPException(404, "job not found for this candidate")
    rp_id = db.insert_role_profile(candidate_id, body.name, job["role"], body.job_id)
    return {"id": rp_id, "name": body.name, "target_role": job["role"],
            "job_id": body.job_id}


@app.get("/api/candidates/{candidate_id}/role-profiles")
def list_role_profiles(candidate_id: int) -> dict:
    return {"role_profiles": db.list_role_profiles(candidate_id)}


def _resume_for_export(job_id: int) -> TailoredResume:
    """Return the stored generated résumé, generating it once if absent."""
    if db.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    stored = db.get_generation(job_id)
    if stored is None:
        try:
            pipeline.generate_for_job(job_id)   # generates and persists
        except LLMError as e:
            raise HTTPException(502, str(e))
        stored = db.get_generation(job_id)
    return TailoredResume.model_validate_json(stored)


@app.get("/api/jobs/{job_id}/export.pdf")
def export_pdf(job_id: int) -> Response:
    resume = _resume_for_export(job_id)
    pdf = export.build_pdf(resume)
    fname = f"{resume.candidate.name or 'resume'}_{resume.target_role or 'tailored'}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _original_resume(candidate_id: int) -> TailoredResume:
    """The untailored master profile as a renderable résumé (§32) — original stays a
    separate structured state from any tailored view."""
    candidate = db.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    entities = db.get_entities(candidate_id, statuses={Status.ORIGINAL})
    return generation.original_resume(candidate, entities)


def _pdf_response(pdf: bytes, name: str, role: str) -> Response:
    fname = f"{name or 'resume'}_{role or 'resume'}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _latex_pdf(resume: TailoredResume) -> bytes:
    """Compile the LaTeX PDF, translating engine failures into friendly 503s (§35)."""
    try:
        return latex.compile_pdf(latex.render_latex(resume))
    except latex.LatexUnavailableError:
        raise HTTPException(503, "The professional PDF renderer isn't available in this "
                            "environment. Use Download PDF (standard) or Download .tex.")
    except latex.LatexCompileError as e:
        import logging
        logging.getLogger("uvicorn.error").error("LaTeX compile failed: %s", e.log[-2000:])
        raise HTTPException(503, "We couldn't compile the professional PDF from this "
                            "résumé. The content generated fine — try Download PDF (standard).")


@app.get("/api/candidates/{candidate_id}/export.original.tex", response_class=PlainTextResponse)
def export_original_tex(candidate_id: int) -> Response:
    resume = _original_resume(candidate_id)
    return PlainTextResponse(latex.render_latex(resume), headers={
        "Content-Disposition": f'attachment; filename="{resume.candidate.name}_master.tex"'})


@app.get("/api/candidates/{candidate_id}/export.original.pdf")
def export_original_pdf(candidate_id: int) -> Response:
    resume = _original_resume(candidate_id)
    return _pdf_response(_latex_pdf(resume), resume.candidate.name, "master")


@app.get("/api/jobs/{job_id}/export.tex", response_class=PlainTextResponse)
def export_tex(job_id: int) -> Response:
    """LaTeX source rendered from the approved structured résumé. Always available —
    no compiler needed — so the professional template is usable even where PDF
    compilation isn't (§21)."""
    resume = _resume_for_export(job_id)
    tex = latex.render_latex(resume)
    fname = f"{resume.candidate.name or 'resume'}_{resume.target_role or 'tailored'}.tex"
    return PlainTextResponse(tex, headers={
        "Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/jobs/{job_id}/export.latex.pdf")
def export_latex_pdf(job_id: int) -> Response:
    """Professional PDF compiled from the LaTeX template. Best-effort: if no LaTeX engine
    is installed (or compilation fails) we return 503 with a friendly message rather than
    a raw compiler log (§35). The reportlab /export.pdf path stays as a reliable fallback."""
    resume = _resume_for_export(job_id)
    return _pdf_response(_latex_pdf(resume), resume.candidate.name, resume.target_role)


@app.get("/api/jobs/{job_id}/export.html", response_class=HTMLResponse)
def export_html(job_id: int) -> str:
    return export.render_html(_resume_for_export(job_id))


@app.get("/api/jobs/{job_id}/export.md", response_class=PlainTextResponse)
def export_md(job_id: int) -> str:
    return _resume_for_export(job_id).markdown


@app.get("/api/jobs/{job_id}/explain")
def explain(job_id: int, requirement: str) -> dict:
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    from .models import JDRequirements, SUPPORTED_STATUSES
    from .retrieval import RetrievalIndex
    from . import matching
    requirements = JDRequirements.model_validate_json(row["requirements_json"])
    entities = db.get_entities(row["candidate_id"], statuses=SUPPORTED_STATUSES)
    index = RetrievalIndex(entities)
    matches = matching.match_requirements(
        index, requirements, matching.candidate_skill_set(entities))
    return analysis.explain_requirement(requirement, matches)


# ----------------------------------------------------------------------- UI #
# Serve the built React app if present; otherwise fall back to the legacy single-page
# static UI so a python-only checkout (no `npm run build`) still works.
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/")
def index() -> FileResponse:
    built = FRONTEND_DIST / "index.html"
    return FileResponse(built if built.exists() else STATIC / "index.html")
