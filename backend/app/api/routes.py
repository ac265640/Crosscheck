"""
FastAPI API routes.
All endpoints are documented here. Business logic lives in the backend modules.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from backend.app.canonicalization.canonicalizer import canonicalize_fact
from backend.app.canonicalization.embedder import embed_text
from backend.app.config import DB_PATH
from backend.app.extraction.fact_extractor import extract_facts_from_chunk
from backend.app.guardrails.evidence_verifier import verify_fact_evidence
from backend.app.ingestion.chunker import chunk_document
from backend.app.ingestion.pdf_parser import (
    detect_body_font_size,
    parse_pdf,
    render_page_as_image,
    render_page_with_highlight,
)
from backend.app.ingestion.table_extractor import (
    build_section_map_from_pages,
    extract_tables_from_pdf,
)
from backend.app.models.schema import Document, Fact, Relationship
from backend.app.reasoning.relationship_engine import reason_about_fact
from backend.app.storage.db import init_db
from backend.app.storage.repository import (
    count_facts_for_document,
    document_exists,
    get_chunk,
    get_chunks_for_document,
    get_document,
    get_fact,
    get_relationships_for_fact,
    insert_chunk,
    insert_document,
    insert_fact,
    list_documents,
    list_facts_for_document,
    list_relationships_by_type,
)
from backend.app.tracing.trace_log import read_recent_traces

router = APIRouter()

# Ensure DB is initialized on import
init_db(DB_PATH)

# Temp upload dir
_UPLOAD_DIR = Path("data/uploads")
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── POST /documents ────────────────────────────────────────────────────────────

@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF. Runs the full pipeline:
    ingest → extract → verify → canonicalize → index → reason.
    Returns document_id and summary counts.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Check if already ingested (idempotent)
    if document_exists(file.filename, DB_PATH):
        raise HTTPException(
            status_code=409,
            detail=f"Document '{file.filename}' already ingested. Delete and re-upload to reprocess.",
        )

    # Save file
    pdf_path = _UPLOAD_DIR / file.filename
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    # Parse PDF
    try:
        pages, page_count = parse_pdf(pdf_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF parsing failed: {e}")

    # Create document record
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename=file.filename,
        uploaded_at=datetime.now(timezone.utc),
        page_count=page_count,
    )
    insert_document(doc, DB_PATH)

    # Build section map for table tagging
    section_map = build_section_map_from_pages(pages)

    # Extract tables
    table_chunks, table_bboxes = extract_tables_from_pdf(
        pdf_path, doc_id, section_map
    )

    # Text chunking (skips spans inside table regions)
    text_chunks = chunk_document(pages, doc_id, table_bboxes)
    all_chunks = text_chunks + table_chunks

    # Insert chunks
    for chunk in all_chunks:
        insert_chunk(chunk, DB_PATH)

    # Build chunk_text_map for verification
    chunk_text_map = {c.id: c.text for c in all_chunks}

    # Extract facts per chunk
    all_facts: list[Fact] = []
    for chunk in all_chunks:
        facts = extract_facts_from_chunk(chunk, file.filename)
        for fact in facts:
            # Verify evidence
            fact = verify_fact_evidence(fact, chunk_text_map.get(chunk.id, ""))
            # Embed and insert
            if fact.verification_status != "extraction_failed":
                emb = embed_text(f"{fact.entity} {fact.attribute}: {fact.value}")
            else:
                emb = None
            insert_fact(fact, emb, DB_PATH)
            all_facts.append(fact)

    # Canonicalize
    for fact in all_facts:
        if fact.verification_status != "extraction_failed":
            chunk = get_chunk(fact.chunk_id, DB_PATH)
            chunk_text = chunk.text if chunk else ""
            canonicalize_fact(fact, chunk_text)

    # Relationship reasoning (against existing store)
    new_relationships: list[Relationship] = []
    for fact in all_facts:
        if fact.verification_status != "extraction_failed":
            rels = reason_about_fact(fact, DB_PATH)
            new_relationships.extend(rels)

    counts = count_facts_for_document(doc_id, DB_PATH)
    return {
        "document_id": doc_id,
        "filename": file.filename,
        "page_count": page_count,
        "chunk_count": len(all_chunks),
        "fact_count": len(all_facts),
        "verified": counts.get("verified", 0),
        "unverified": counts.get("unverified", 0),
        "extraction_failed": counts.get("extraction_failed", 0),
        "new_relationships": len(new_relationships),
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


# ── GET /facts/{id} ────────────────────────────────────────────────────────────

@router.get("/facts/{fact_id}")
def get_single_fact(fact_id: str):
    """A single fact with evidence, source page, bbox."""
    fact = get_fact(fact_id, DB_PATH)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")
    return fact.model_dump()


# ── GET /facts/{id}/relationships ─────────────────────────────────────────────

@router.get("/facts/{fact_id}/relationships")
def get_fact_relationships(fact_id: str):
    """All relationships involving this fact, with the linked fact and explanation."""
    fact = get_fact(fact_id, DB_PATH)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    relationships = get_relationships_for_fact(fact_id, DB_PATH)
    result = []
    for rel in relationships:
        linked_fact_id = rel.fact_id_b if rel.fact_id_a == fact_id else rel.fact_id_a
        linked_fact = get_fact(linked_fact_id, DB_PATH)
        result.append({
            "relationship": rel.model_dump(),
            "linked_fact": linked_fact.model_dump() if linked_fact else None,
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
