"""
FastAPI API routes.
All endpoints are documented here. Business logic lives in the backend modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from backend.app.api.jobs import create_job, job_router
from backend.app.config import DB_PATH, PROJECT_ROOT
from backend.app.ingestion.pdf_parser import (
    render_page_as_image,
    render_page_with_highlight,
)
from backend.app.ingestion.pipeline import run_pipeline
from backend.app.storage.db import init_db
from backend.app.storage.repository import (
    count_facts_for_document,
    delete_document,
    document_exists,
    get_chunks_for_document,
    get_document,
    get_fact,
    get_relationships_for_fact,
    get_relationships_for_document,
    list_documents,
    list_facts_for_document,
    list_relationships_by_type,
)
from backend.app.tracing.trace_log import read_recent_traces

router = APIRouter()
router.include_router(job_router)

# Ensure DB is initialized on import
init_db(DB_PATH)

# Temp upload dir — absolute path so it works regardless of uvicorn cwd
_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── POST /documents ────────────────────────────────────────────────────────────

@router.post("/documents")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a PDF. Returns {job_id, status: 'queued'} immediately (< 1s).
    The pipeline runs asynchronously in a BackgroundTask.
    Track progress via:
      GET /jobs/{job_id}/stream  (SSE real-time)
      GET /jobs/{job_id}/status  (poll fallback)
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Check if already ingested (idempotent)
    if document_exists(file.filename, DB_PATH):
        raise HTTPException(
            status_code=409,
            detail=f"Document '{file.filename}' already ingested. Delete and re-upload to reprocess.",
        )

    # Save file to disk before returning
    pdf_path = _UPLOAD_DIR / file.filename
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    # Create job in registry — captures the current event loop
    job = create_job(file.filename)

    def _worker():
        try:
            run_pipeline(pdf_path, file.filename, job, DB_PATH)
        except Exception as e:
            import traceback
            traceback.print_exc()
            job.push("error", -1, f"Ingestion error: {str(e)}")

    background_tasks.add_task(_worker)

    return {
        "job_id": job.job_id,
        "filename": file.filename,
        "status": "queued",
        "message": f"Document '{file.filename}' queued. Track at /jobs/{job.job_id}/stream",
    }


# ── GET /documents ─────────────────────────────────────────────────────────────

@router.get("/documents")
def list_all_documents():
    """List all ingested documents."""
    docs = list_documents(DB_PATH)
    result = []
    for doc in docs:
        counts = count_facts_for_document(doc.id, DB_PATH)
        chunks = get_chunks_for_document(doc.id, DB_PATH)
        result.append({
            "document": doc.model_dump(),
            "chunk_count": len(chunks),
            "fact_count": sum(counts.values()),
            "verified_count": counts.get("verified", 0),
            "unverified_count": counts.get("unverified", 0),
            "failed_count": counts.get("extraction_failed", 0),
        })
    return result


# ── GET /documents/{id}/facts ──────────────────────────────────────────────────

@router.get("/documents/{doc_id}/facts")
def get_document_facts(doc_id: str, status: Optional[str] = Query(None)):
    """List facts for a document. Optional ?status=verified|unverified|extraction_failed filter."""
    doc = get_document(doc_id, DB_PATH)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    facts = list_facts_for_document(doc_id, DB_PATH)
    if status:
        facts = [f for f in facts if f.verification_status == status]
    return [f.model_dump() for f in facts]


# ── DELETE /documents/{id} ───────────────────────────────────────────────────

@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    """Delete a document and all associated chunks, facts, and relationships."""
    doc = get_document(doc_id, DB_PATH)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_document(doc_id, DB_PATH)

    # Clean up uploaded PDF if exists
    pdf_path = _UPLOAD_DIR / doc.filename
    if pdf_path.exists():
        try:
            pdf_path.unlink()
        except OSError:
            pass

    return {"status": "ok", "message": f"Document '{doc.filename}' deleted successfully."}


# ── GET /facts/{id} ────────────────────────────────────────────────────────────

@router.get("/facts/{fact_id}")
def get_single_fact(fact_id: str):
    """A single fact with evidence, source page, bbox."""
    fact = get_fact(fact_id, DB_PATH)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")
    return fact.model_dump()


# ── GET /documents/{id}/relationships ─────────────────────────────────────────

@router.get("/documents/{doc_id}/relationships")
def get_document_relationships(doc_id: str, limit: int = 200):
    """All cross-document relationships involving facts in this document with rich evidence quotes."""
    doc = get_document(doc_id, DB_PATH)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return get_relationships_for_document(doc_id, limit=limit, db_path=DB_PATH)


# ── GET /facts/{id}/relationships ─────────────────────────────────────────────

@router.get("/facts/{fact_id}/relationships")
def get_fact_relationships(fact_id: str):
    """All relationships involving this fact, with full details for both facts and explanations."""
    fact = get_fact(fact_id, DB_PATH)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    doc_a = get_document(fact.document_id, DB_PATH)
    relationships = get_relationships_for_fact(fact_id, DB_PATH)
    result = []
    for rel in relationships:
        linked_fact_id = rel.fact_id_b if rel.fact_id_a == fact_id else rel.fact_id_a
        linked_fact = get_fact(linked_fact_id, DB_PATH)
        doc_b = get_document(linked_fact.document_id, DB_PATH) if linked_fact else None

        fa_dict = fact.model_dump()
        fa_dict["document_filename"] = doc_a.filename if doc_a else None

        fb_dict = linked_fact.model_dump() if linked_fact else None
        if fb_dict and doc_b:
            fb_dict["document_filename"] = doc_b.filename

        result.append({
            "id": rel.id,
            "relationship_type": rel.relationship_type,
            "confidence": rel.confidence,
            "explanation": rel.explanation,
            "relationship": rel.model_dump(),
            "fact_a": fa_dict,
            "fact_b": fb_dict,
            "linked_fact": fb_dict,  # backwards compatibility
        })
    return result


# ── GET /documents/{id}/pages/{page_number}/image ─────────────────────────────

@router.get("/documents/{doc_id}/pages/{page_number}/image")
def get_page_image(
    doc_id: str,
    page_number: int,
    highlight_bbox: Optional[str] = Query(None, description="x0,y0,x1,y1"),
):
    """Rendered page image. Optionally highlights a bounding box."""
    doc = get_document(doc_id, DB_PATH)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    pdf_path = _UPLOAD_DIR / doc.filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on server.")

    try:
        if highlight_bbox:
            coords = [float(x) for x in highlight_bbox.split(",")]
            if len(coords) != 4:
                raise ValueError("bbox must be x0,y0,x1,y1")
            png_bytes = render_page_with_highlight(pdf_path, page_number, tuple(coords))
        else:
            png_bytes = render_page_as_image(pdf_path, page_number)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Rendering failed: {e}")

    return Response(content=png_bytes, media_type="image/png")


# ── GET /trace ─────────────────────────────────────────────────────────────────

@router.get("/trace")
def get_trace(n: int = Query(50, ge=1, le=500)):
    """Recent entries from the LLM trace log."""
    return read_recent_traces(n)


# ── GET /relationships/cases ───────────────────────────────────────────────────

@router.get("/relationships/cases")
def get_required_cases():
    """
    Returns one example of each required relationship type.
    Used by the 'Four required cases' UI tab.
    """
    cases = {}
    for rel_type in ["corroboration", "contradiction", "reconciled_context", "uncertain"]:
        rels = list_relationships_by_type(rel_type, limit=1, db_path=DB_PATH)
        if rels:
            rel = rels[0]
            fact_a = get_fact(rel.fact_id_a, DB_PATH)
            fact_b = get_fact(rel.fact_id_b, DB_PATH)
            cases[rel_type] = {
                "relationship": rel.model_dump(),
                "fact_a": fact_a.model_dump() if fact_a else None,
                "fact_b": fact_b.model_dump() if fact_b else None,
            }
        else:
            cases[rel_type] = None
    return cases
